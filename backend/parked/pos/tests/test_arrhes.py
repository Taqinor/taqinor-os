"""NTRET5 — Arrhes / acompte sur commande comptoir (article en rupture de
stock ou sur-mesure).

Couvre : encaisser des arrhes passe la vente en EN_ATTENTE_SOLDE (marchandise
bloquée), le solde doit être réglé exactement pour débloquer la remise (le
stock est alors décrémenté), le reçu d'arrhes est distinct du ticket final
(refusé tant que la vente n'est pas VALIDEE), l'override admin débloque la
remise sans changer le statut et journalise un motif obligatoire.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.pos import services
from apps.pos.models import LigneVenteComptoir, VenteComptoir
from apps.stock.models import Categorie, Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ArrhesServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret5', 'NTRET5 Co')
        self.user = make_user(self.co, 'caissier-ntret5')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Acc')
        self.produit = Produit.objects.create(
            company=self.co, nom='Onduleur sur-mesure', prix_vente=Decimal('500'),
            prix_achat=Decimal('300'), quantite_stock=5, categorie=categorie)

    def _vente(self, prix='500'):
        vente = VenteComptoir.objects.create(
            company=self.co, reference=f'VC-ARR-{prix}',
            client=self.client_obj, created_by=self.user)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=1, prix_unitaire_ttc=Decimal(prix))
        return vente

    def test_encaisser_arrhes_sets_en_attente_solde_no_stock_decrement(self):
        vente = self._vente()
        services.encaisser_arrhes(
            vente=vente, montant_arrhes=Decimal('150'),
            paiement={'mode': 'carte', 'montant': '150'}, user=self.user)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, VenteComptoir.Statut.EN_ATTENTE_SOLDE)
        self.assertEqual(vente.montant_arrhes, Decimal('150.00'))
        self.assertFalse(vente.marchandise_remise)
        self.assertIsNotNone(vente.facture)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 5)  # inchangé

    def test_encaisser_arrhes_paiement_must_match_exactly(self):
        vente = self._vente()
        with self.assertRaises(services.ArrhesError):
            services.encaisser_arrhes(
                vente=vente, montant_arrhes=Decimal('150'),
                paiement={'mode': 'carte', 'montant': '100'}, user=self.user)

    def test_encaisser_arrhes_must_be_strictly_less_than_total(self):
        vente = self._vente()
        with self.assertRaises(services.ArrhesError):
            services.encaisser_arrhes(
                vente=vente, montant_arrhes=Decimal('500'),
                paiement={'mode': 'carte', 'montant': '500'}, user=self.user)

    def test_solde_restant_arrhes(self):
        vente = self._vente()
        services.encaisser_arrhes(
            vente=vente, montant_arrhes=Decimal('150'),
            paiement={'mode': 'carte', 'montant': '150'}, user=self.user)
        self.assertEqual(services.solde_restant_arrhes(vente), Decimal('350.00'))

    def test_encaisser_solde_decrements_stock_and_validates(self):
        vente = self._vente()
        services.encaisser_arrhes(
            vente=vente, montant_arrhes=Decimal('150'),
            paiement={'mode': 'carte', 'montant': '150'}, user=self.user)
        services.encaisser_solde_arrhes(
            vente=vente, paiement={'mode': 'carte', 'montant': '350'},
            user=self.user)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, VenteComptoir.Statut.VALIDEE)
        self.assertTrue(vente.marchandise_remise)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 4)

    def test_encaisser_solde_wrong_amount_refused(self):
        vente = self._vente()
        services.encaisser_arrhes(
            vente=vente, montant_arrhes=Decimal('150'),
            paiement={'mode': 'carte', 'montant': '150'}, user=self.user)
        with self.assertRaises(services.ArrhesError):
            services.encaisser_solde_arrhes(
                vente=vente, paiement={'mode': 'carte', 'montant': '300'},
                user=self.user)

    def test_remettre_marchandise_override_requires_motif(self):
        vente = self._vente()
        services.encaisser_arrhes(
            vente=vente, montant_arrhes=Decimal('150'),
            paiement={'mode': 'carte', 'montant': '150'}, user=self.user)
        with self.assertRaises(services.ArrhesError):
            services.remettre_marchandise_override(
                vente=vente, user=self.user, motif='')

    def test_remettre_marchandise_override_journalise_and_keeps_statut(self):
        vente = self._vente()
        services.encaisser_arrhes(
            vente=vente, montant_arrhes=Decimal('150'),
            paiement={'mode': 'carte', 'montant': '150'}, user=self.user)
        services.remettre_marchandise_override(
            vente=vente, user=self.user, motif='Client fidèle, urgence chantier')
        vente.refresh_from_db()
        self.assertTrue(vente.marchandise_remise)
        # Statut INCHANGÉ : le solde reste dû malgré la remise anticipée.
        self.assertEqual(vente.statut, VenteComptoir.Statut.EN_ATTENTE_SOLDE)

        from apps.audit.models import AuditLog
        self.assertTrue(
            AuditLog.objects.filter(company=self.co)
            .filter(detail__icontains='Override admin').exists())

    def test_receipt_arrhes_distinct_from_final_ticket(self):
        from apps.pos import receipt
        vente = self._vente()
        services.encaisser_arrhes(
            vente=vente, montant_arrhes=Decimal('150'),
            paiement={'mode': 'carte', 'montant': '150'}, user=self.user)
        html = receipt.receipt_arrhes_html(vente)
        self.assertIn("Reçu d'arrhes", html)
        self.assertIn('150.00', html)
        self.assertIn('350.00', html)  # solde restant


class ArrhesApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret5-api', 'NTRET5 API Co')
        self.user = make_user(self.co, 'ntret5-api-user')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Acc')
        self.produit = Produit.objects.create(
            company=self.co, nom='Pompe sur-mesure', prix_vente=Decimal('800'),
            prix_achat=Decimal('500'), quantite_stock=3, categorie=categorie)

    def _vente_id(self, api):
        create_resp = api.post(
            '/api/django/pos/ventes/', {'client': self.client_obj.id}, format='json')
        vente_id = create_resp.data['id']
        api.post(
            f'/api/django/pos/ventes/{vente_id}/lignes/',
            {'produit': self.produit.id, 'quantite': 1, 'prix_unitaire_ttc': '800'},
            format='json')
        return vente_id

    def test_arrhes_then_ticket_final_blocked_until_solde(self):
        api = auth(self.user)
        vente_id = self._vente_id(api)

        arrhes_resp = api.post(
            f'/api/django/pos/ventes/{vente_id}/arrhes/',
            {'montant_arrhes': '200', 'paiement': {'mode': 'carte', 'montant': '200'}},
            format='json')
        self.assertEqual(arrhes_resp.status_code, 200, arrhes_resp.data)
        self.assertEqual(arrhes_resp.data['statut'], 'en_attente_solde')

        # Reçu d'arrhes disponible immédiatement.
        arrhes_pdf = api.get(f'/api/django/pos/ventes/{vente_id}/ticket-arrhes-pdf/')
        self.assertEqual(arrhes_pdf.status_code, 200)

        # Ticket FINAL refusé tant que le solde n'est pas réglé.
        ticket_pdf = api.get(f'/api/django/pos/ventes/{vente_id}/ticket-pdf/')
        self.assertEqual(ticket_pdf.status_code, 400)

        solde_resp = api.post(
            f'/api/django/pos/ventes/{vente_id}/solde-arrhes/',
            {'paiement': {'mode': 'carte', 'montant': '600'}}, format='json')
        self.assertEqual(solde_resp.status_code, 200, solde_resp.data)
        self.assertEqual(solde_resp.data['statut'], 'validee')

        ticket_pdf_after = api.get(f'/api/django/pos/ventes/{vente_id}/ticket-pdf/')
        self.assertEqual(ticket_pdf_after.status_code, 200)

    def test_montant_arrhes_and_marchandise_remise_not_directly_patchable(self):
        api = auth(self.user)
        vente_id = self._vente_id(api)
        resp = api.patch(
            f'/api/django/pos/ventes/{vente_id}/',
            {'montant_arrhes': '999', 'marchandise_remise': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        vente = VenteComptoir.objects.get(id=vente_id)
        self.assertIsNone(vente.montant_arrhes)
        self.assertFalse(vente.marchandise_remise)
