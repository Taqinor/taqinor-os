"""NTRET23 — Click & Collect : réservation expirée auto-libérée.

Couvre : le délai configuré (Paramètres POS) pose l'expiration à la création,
délai absent = jamais d'expiration (comportement historique inchangé), une
réservation expirée À_PRÉPARER est simplement annulée (stock jamais sorti),
une réservation expirée PRÊTE ré-incrémente EXACTEMENT le stock sorti à la
préparation, et le balayage est idempotent (un re-run immédiat ne retrouve
rien à libérer).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.parametres.models_pos import ParametresPos
from apps.pos import services
from apps.pos.models import CommandeRetrait, LigneCommandeRetrait
from apps.stock.models import Categorie, Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class ReservationExpirationTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret23', 'NTRET23 Co')
        self.user = make_user(self.co, 'magasinier-ntret23')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Régulateur', prix_vente=Decimal('300'),
            prix_achat=Decimal('150'), quantite_stock=15, categorie=categorie)

    def _commande(self, reference='RET-100001', quantite=3):
        commande = CommandeRetrait.objects.create(
            company=self.co, reference=reference, client=self.client_obj,
            created_by=self.user)
        LigneCommandeRetrait.objects.create(
            commande=commande, produit=self.produit, quantite=quantite)
        return commande

    # ── Pose de l'expiration à la création ──────────────────────────────────

    def test_poser_expiration_sans_config_ne_pose_rien(self):
        commande = self._commande()
        services.poser_expiration_reservation(commande)
        commande.refresh_from_db()
        self.assertIsNone(commande.date_expiration_reservation)

    def test_poser_expiration_avec_config(self):
        profile = ParametresPos.get(self.co)
        profile.delai_expiration_click_collect_jours = 3
        profile.save(update_fields=['delai_expiration_click_collect_jours'])
        commande = self._commande()
        avant = timezone.now()
        services.poser_expiration_reservation(commande)
        commande.refresh_from_db()
        self.assertIsNotNone(commande.date_expiration_reservation)
        attendu = avant + timedelta(days=3)
        self.assertLess(
            abs((commande.date_expiration_reservation - attendu).total_seconds()), 5)

    # ── Libération d'une réservation expirée ────────────────────────────────

    def test_liberer_a_preparer_expiree_annule_sans_toucher_au_stock(self):
        commande = self._commande()
        commande.date_expiration_reservation = timezone.now() - timedelta(hours=1)
        commande.save(update_fields=['date_expiration_reservation'])
        services.liberer_reservation_expiree(commande)
        commande.refresh_from_db()
        self.assertEqual(commande.statut, CommandeRetrait.Statut.ANNULE)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 15)  # jamais sorti

    def test_liberer_pret_expiree_reincremente_le_stock_exact(self):
        commande = self._commande(quantite=3)
        services.marquer_pret(commande=commande, user=self.user)
        commande.refresh_from_db()
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 12)  # sorti à la préparation

        commande.date_expiration_reservation = timezone.now() - timedelta(hours=1)
        commande.save(update_fields=['date_expiration_reservation'])
        services.liberer_reservation_expiree(commande)

        commande.refresh_from_db()
        self.assertEqual(commande.statut, CommandeRetrait.Statut.ANNULE)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 15)  # ré-incrémenté exact

    def test_liberer_reservation_non_expiree_ne_fait_rien(self):
        commande = self._commande()
        commande.date_expiration_reservation = timezone.now() + timedelta(days=1)
        commande.save(update_fields=['date_expiration_reservation'])
        count = services.liberer_reservations_expirees(company=self.co)
        self.assertEqual(count, 0)
        commande.refresh_from_db()
        self.assertEqual(commande.statut, CommandeRetrait.Statut.A_PREPARER)

    def test_liberer_reservation_retiree_deja_terminale_ignoree(self):
        commande = self._commande()
        services.marquer_pret(commande=commande, user=self.user)
        commande.refresh_from_db()
        services.remettre_commande(
            commande=commande, code_saisi=commande.code_retrait, user=self.user)
        commande.refresh_from_db()
        commande.date_expiration_reservation = timezone.now() - timedelta(hours=1)
        commande.save(update_fields=['date_expiration_reservation'])

        count = services.liberer_reservations_expirees(company=self.co)
        self.assertEqual(count, 0)
        commande.refresh_from_db()
        self.assertEqual(commande.statut, CommandeRetrait.Statut.RETIRE)

    def test_balayage_idempotent_un_re_run_ne_retrouve_rien(self):
        commande = self._commande(quantite=3)
        services.marquer_pret(commande=commande, user=self.user)
        commande.refresh_from_db()
        commande.date_expiration_reservation = timezone.now() - timedelta(hours=1)
        commande.save(update_fields=['date_expiration_reservation'])

        count1 = services.liberer_reservations_expirees(company=self.co)
        self.assertEqual(count1, 1)
        self.produit.refresh_from_db()
        stock_apres_premier = self.produit.quantite_stock

        count2 = services.liberer_reservations_expirees(company=self.co)
        self.assertEqual(count2, 0)
        self.produit.refresh_from_db()
        # Aucun deuxième retour de stock — le compte reste identique.
        self.assertEqual(self.produit.quantite_stock, stock_apres_premier)

    def test_creer_commande_retrait_via_perform_create_pose_expiration(self):
        """L'action de création réelle (vue) pose l'expiration automatiquement
        quand un délai est configuré — pas seulement l'appel service direct."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        profile = ParametresPos.get(self.co)
        profile.delai_expiration_click_collect_jours = 5
        profile.save(update_fields=['delai_expiration_click_collect_jours'])

        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        res = api.post('/api/django/pos/retraits/', {'client': self.client_obj.id})
        self.assertEqual(res.status_code, 201, res.data)
        commande = CommandeRetrait.objects.get(id=res.data['id'])
        self.assertIsNotNone(commande.date_expiration_reservation)
