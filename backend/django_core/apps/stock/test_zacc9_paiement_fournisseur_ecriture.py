"""ZACC9 — Comptabilisation + garde de sur-paiement du règlement fournisseur
(parité Register Payment).

Couvre :
  * un paiement > solde dû est refusé (400) sur
    `factures-fournisseur/{id}/paiements/` (POST) ;
  * un paiement valide poste une écriture comptable équilibrée réduisant le
    solde du bon montant (débit 4411 / crédit trésorerie), UNIQUEMENT quand
    `COMPTA_AUTO_ECRITURES` est actif (comportement historique OFF par
    défaut) ;
  * re-poster (rejouer l'événement) le même paiement n'écrit jamais deux
    fois (idempotence côté récepteur compta) ;
  * cross-company : une facture d'une autre société → 404.

Run:
    python manage.py test \
        apps.stock.test_zacc9_paiement_fournisseur_ecriture -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import FactureFournisseur, Fournisseur
from apps.compta.models import EcritureComptable
from apps.compta import services as compta_services

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


class Zacc9Base(TestCase):
    def setUp(self):
        self.company = _company('zacc9-co')
        self.user = _user(
            self.company, 'zacc9-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZACC9')
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-ZACC9-1',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('100'), montant_tva=Decimal('20'),
            montant_ttc=Decimal('120'),
            statut=FactureFournisseur.Statut.A_PAYER)

    def _paiements_url(self):
        return (f'/api/django/stock/factures-fournisseur/'
                f'{self.facture.id}/paiements/')


class TestGardeSurPaiement(Zacc9Base):
    def test_paiement_superieur_au_solde_du_refuse(self):
        resp = self.api.post(self._paiements_url(), {
            'montant': '150', 'mode': 'virement'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_paiement_egal_au_solde_du_accepte(self):
        resp = self.api.post(self._paiements_url(), {
            'montant': '120', 'mode': 'virement'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_paiement_partiel_puis_depassement_du_reste_refuse(self):
        resp1 = self.api.post(self._paiements_url(), {
            'montant': '100', 'mode': 'virement'}, format='json')
        self.assertEqual(resp1.status_code, 201, resp1.data)
        # Reste dû = 20 ; tenter 50 doit être refusé.
        resp2 = self.api.post(self._paiements_url(), {
            'montant': '50', 'mode': 'virement'}, format='json')
        self.assertEqual(resp2.status_code, 400, resp2.data)


@override_settings(COMPTA_AUTO_ECRITURES=True)
class TestEcritureComptable(Zacc9Base):
    def test_paiement_valide_poste_ecriture_equilibree(self):
        resp = self.api.post(self._paiements_url(), {
            'montant': '120', 'mode': 'virement'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ecr = EcritureComptable.objects.get(
            company=self.company, source_type='paiement_fournisseur')
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.total_credit, Decimal('120'))
        fourn = ecr.lignes.get(compte__numero='4411')
        self.assertEqual(fourn.debit, Decimal('120'))

    def test_reduit_le_solde_du_bon_montant(self):
        self.api.post(self._paiements_url(), {
            'montant': '50', 'mode': 'virement'}, format='json')
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.solde_du, Decimal('70'))

    def test_rejouer_le_meme_paiement_necrit_pas_deux_fois(self):
        resp = self.api.post(self._paiements_url(), {
            'montant': '120', 'mode': 'virement'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        from apps.stock.models import PaiementFournisseur
        paiement = PaiementFournisseur.objects.get(facture=self.facture)
        # Rejoue directement le service compta (simule un ré-abonné) :
        # idempotence garantie par `_ecriture_existante`.
        compta_services.ecriture_pour_paiement_fournisseur(paiement)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.company,
                source_type='paiement_fournisseur').count(), 1)


class TestOffParDefaut(Zacc9Base):
    def test_sans_toggle_aucune_ecriture(self):
        self.assertFalse(compta_services.auto_ecritures_actif())
        resp = self.api.post(self._paiements_url(), {
            'montant': '120', 'mode': 'virement'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.company,
                source_type='paiement_fournisseur').count(), 0)


class TestMultiTenant(Zacc9Base):
    def test_facture_autre_societe_404(self):
        autre = _company('zacc9-autre')
        autre_user = _user(autre, 'zacc9-autre-user',
                           permissions=['stock_modifier', 'stock_voir'])
        autre_api = _api(autre_user)
        resp = autre_api.post(self._paiements_url(), {
            'montant': '10', 'mode': 'virement'}, format='json')
        self.assertEqual(resp.status_code, 404)
