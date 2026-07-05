"""YSTCK6 — Annulation d'une réception CONFIRMÉE : contre-passation au lieu
d'un blocage en dur (SAP 102).

Couvre :
  * annuler une réception CONFIRME sort exactement les quantités reçues via
    un MouvementStock SORTIE référencé `ANNUL-<REC>` (traçable) ;
  * corrige `quantite_recue` sur les lignes BCF concernées ;
  * rétrograde le statut du BCF de RECU à ENVOYE si le BCF n'est plus
    entièrement reçu ;
  * ré-annuler une réception déjà ANNULE lève ValueError (rien à rejouer) ;
  * le stock ne descend jamais sous zéro (garde XSTK8) ;
  * une réception BROUILLON garde le chemin historique (simple passage à
    ANNULE, aucune contre-passation).

Run:
    python manage.py test \
        apps.stock.test_ystck6_annulation_reception_confirmee -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, MouvementStock, Produit,
    ReceptionFournisseur,
)
from apps.stock.services import (
    annuler_reception_confirmee, confirm_reception_fournisseur,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ystck6Base(TestCase):
    def setUp(self):
        self.company = _company('ystck6-co')
        self.user = _user(
            self.company, 'ystck6-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur YSTCK6')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur YSTCK6', sku='OND-YSTCK6',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'),
            quantite_stock=0)

    def _bcf_et_reception_confirmee(self, quantite=10):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-YSTCK6-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne_cmd = bc.lignes.create(
            produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal('100'))
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-YSTCK6-1',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        rec.lignes.create(
            ligne_commande=ligne_cmd, produit=self.produit, quantite=quantite)
        confirm_reception_fournisseur(rec, self.user)
        bc.refresh_from_db()
        return bc, ligne_cmd, rec


class TestContrePassation(Ystck6Base):
    def test_annuler_sort_exactement_les_quantites_recues(self):
        bc, ligne_cmd, rec = self._bcf_et_reception_confirmee(quantite=10)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)

        annuler_reception_confirmee(rec, self.user)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)
        mvt = MouvementStock.objects.get(
            produit=self.produit, reference=f'ANNUL-{rec.reference}')
        self.assertEqual(mvt.type_mouvement, MouvementStock.TypeMouvement.SORTIE)
        self.assertEqual(mvt.quantite, 10)

    def test_corrige_quantite_recue_et_statut_bcf(self):
        bc, ligne_cmd, rec = self._bcf_et_reception_confirmee(quantite=10)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.RECU)

        annuler_reception_confirmee(rec, self.user)

        ligne_cmd.refresh_from_db()
        self.assertEqual(ligne_cmd.quantite_recue, 0)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ENVOYE)

    def test_reception_passe_a_annule(self):
        bc, ligne_cmd, rec = self._bcf_et_reception_confirmee(quantite=10)
        annuler_reception_confirmee(rec, self.user)
        rec.refresh_from_db()
        self.assertEqual(rec.statut, ReceptionFournisseur.Statut.ANNULE)

    def test_reannuler_une_reception_deja_annulee_leve(self):
        bc, ligne_cmd, rec = self._bcf_et_reception_confirmee(quantite=10)
        annuler_reception_confirmee(rec, self.user)
        with self.assertRaises(ValueError):
            annuler_reception_confirmee(rec, self.user)
        # Rien rejoué : le stock reste à 0, pas de second mouvement.
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)
        self.assertEqual(
            MouvementStock.objects.filter(
                produit=self.produit,
                reference=f'ANNUL-{rec.reference}').count(), 1)

    def test_stock_jamais_negatif_si_deja_consomme_ailleurs(self):
        bc, ligne_cmd, rec = self._bcf_et_reception_confirmee(quantite=10)
        # Une partie du stock reçu a déjà été consommée ailleurs entre-temps.
        self.produit.quantite_stock = 3
        self.produit.save(update_fields=['quantite_stock'])

        annuler_reception_confirmee(rec, self.user)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)
        self.assertGreaterEqual(self.produit.quantite_stock, 0)


class TestVueApiAnnuler(Ystck6Base):
    def test_annuler_reception_confirmee_via_api(self):
        bc, ligne_cmd, rec = self._bcf_et_reception_confirmee(quantite=5)
        resp = self.api.post(
            f'/api/django/stock/receptions-fournisseur/{rec.id}/annuler/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rec.refresh_from_db()
        self.assertEqual(rec.statut, ReceptionFournisseur.Statut.ANNULE)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)

    def test_annuler_reception_brouillon_chemin_historique_inchange(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-YSTCK6-2',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-YSTCK6-2',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        resp = self.api.post(
            f'/api/django/stock/receptions-fournisseur/{rec.id}/annuler/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rec.refresh_from_db()
        self.assertEqual(rec.statut, ReceptionFournisseur.Statut.ANNULE)
        self.assertEqual(
            MouvementStock.objects.filter(produit=self.produit).count(), 0)
