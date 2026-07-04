"""XPUR2 — RAS-TVA sur paiements fournisseurs (LF 2024, en vigueur 01/07/2024).

Couvre :
  * services (retention 100% biens sans ARF / 0% avec ARF, 75% services avec
    ARF valide / 100% sans) ;
  * désactivable par société (défaut OFF = comportement historique) ;
  * relevé RAS-TVA + export xlsx ;
  * expiry ARF (> 6 mois = considérée invalide).

Run:
    python manage.py test apps.stock.test_xpur2_ras_tva -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AchatsParametres, DocumentConformiteFournisseur,
    FactureFournisseur, Fournisseur,
)
from apps.stock.services import compute_ras_tva, taux_ras_tva, relevé_ras_tva

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


class Xpur2Base(TestCase):
    def setUp(self):
        self.company = _company('xpur2-co')
        self.user = _user(
            self.company, 'xpur2-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Services Maroc')

    def _arf(self, valide=True):
        exp = (timezone.now().date() + timedelta(days=90) if valide
               else timezone.now().date() - timedelta(days=1))
        DocumentConformiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            type_document=DocumentConformiteFournisseur.Type.ARF,
            date_expiration=exp, obligatoire=True)

    def _activate_ras(self):
        AchatsParametres.objects.create(
            company=self.company, ras_tva_actif=True)

    def _facture(self, type_achat, ht=Decimal('1000'), tva=Decimal('200')):
        return FactureFournisseur.objects.create(
            company=self.company, reference=f'FF-XPUR2-{type_achat}',
            fournisseur=self.fournisseur, type_achat=type_achat,
            montant_ht=ht, montant_tva=tva, montant_ttc=ht + tva)


class TestTauxRasTva(Xpur2Base):
    def test_biens_sans_arf_retient_100(self):
        facture = self._facture(FactureFournisseur.TypeAchat.BIENS)
        self.assertEqual(taux_ras_tva(facture), Decimal('100'))

    def test_biens_avec_arf_retient_0(self):
        self._arf(valide=True)
        facture = self._facture(FactureFournisseur.TypeAchat.BIENS)
        self.assertEqual(taux_ras_tva(facture), Decimal('0'))

    def test_services_avec_arf_retient_75(self):
        self._arf(valide=True)
        facture = self._facture(FactureFournisseur.TypeAchat.SERVICES)
        self.assertEqual(taux_ras_tva(facture), Decimal('75'))

    def test_services_sans_arf_retient_100(self):
        facture = self._facture(FactureFournisseur.TypeAchat.SERVICES)
        self.assertEqual(taux_ras_tva(facture), Decimal('100'))

    def test_arf_expiree_traitee_comme_absente(self):
        self._arf(valide=False)
        facture = self._facture(FactureFournisseur.TypeAchat.SERVICES)
        self.assertEqual(taux_ras_tva(facture), Decimal('100'))


class TestComputeRasTva(Xpur2Base):
    def test_disabled_by_default_no_retention(self):
        facture = self._facture(FactureFournisseur.TypeAchat.SERVICES)
        taux, montant = compute_ras_tva(
            self.company, facture, facture.montant_ttc)
        self.assertEqual(taux, Decimal('0'))
        self.assertEqual(montant, Decimal('0'))

    def test_services_20pct_tva_retains_75pct_with_arf(self):
        self._activate_ras()
        self._arf(valide=True)
        facture = self._facture(
            FactureFournisseur.TypeAchat.SERVICES,
            ht=Decimal('1000'), tva=Decimal('200'))
        taux, montant = compute_ras_tva(
            self.company, facture, facture.montant_ttc)
        self.assertEqual(taux, Decimal('75'))
        # 200 * 75% = 150.00
        self.assertEqual(montant, Decimal('150.00'))

    def test_services_20pct_tva_retains_100pct_without_arf(self):
        self._activate_ras()
        facture = self._facture(
            FactureFournisseur.TypeAchat.SERVICES,
            ht=Decimal('1000'), tva=Decimal('200'))
        taux, montant = compute_ras_tva(
            self.company, facture, facture.montant_ttc)
        self.assertEqual(taux, Decimal('100'))
        self.assertEqual(montant, Decimal('200.00'))

    def test_biens_retains_nothing_with_arf(self):
        self._activate_ras()
        self._arf(valide=True)
        facture = self._facture(
            FactureFournisseur.TypeAchat.BIENS,
            ht=Decimal('1000'), tva=Decimal('200'))
        taux, montant = compute_ras_tva(
            self.company, facture, facture.montant_ttc)
        self.assertEqual(taux, Decimal('0'))
        self.assertEqual(montant, Decimal('0'))

    def test_biens_retains_all_without_arf(self):
        self._activate_ras()
        facture = self._facture(
            FactureFournisseur.TypeAchat.BIENS,
            ht=Decimal('1000'), tva=Decimal('200'))
        taux, montant = compute_ras_tva(
            self.company, facture, facture.montant_ttc)
        self.assertEqual(taux, Decimal('100'))
        self.assertEqual(montant, Decimal('200.00'))


class TestPaiementEndpointRas(Xpur2Base):
    def test_payment_records_ras_and_net_paye(self):
        self._activate_ras()
        facture = self._facture(
            FactureFournisseur.TypeAchat.SERVICES,
            ht=Decimal('1000'), tva=Decimal('200'))
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['taux_ras']), Decimal('100.00'))
        self.assertEqual(
            Decimal(resp.data['montant_ras_tva']), Decimal('200.00'))
        self.assertEqual(
            Decimal(resp.data['montant_net_paye']), Decimal('1000.00'))

    def test_payment_no_ras_when_disabled(self):
        facture = self._facture(
            FactureFournisseur.TypeAchat.SERVICES,
            ht=Decimal('1000'), tva=Decimal('200'))
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['montant_ras_tva']), Decimal('0'))
        self.assertEqual(
            Decimal(resp.data['montant_net_paye']), Decimal('1200.00'))


class TestReleveRasTva(Xpur2Base):
    def test_releve_lists_retained_payments(self):
        self._activate_ras()
        facture = self._facture(
            FactureFournisseur.TypeAchat.SERVICES,
            ht=Decimal('1000'), tva=Decimal('200'))
        self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': '1200',
        }, format='json')
        rows = relevé_ras_tva(self.company)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['fournisseur'], self.fournisseur.nom)
        self.assertEqual(rows[0]['montant_ras_tva'], Decimal('200.00'))

    def test_export_xlsx_endpoint(self):
        resp = self.api.get('/api/django/stock/paiements-fournisseur/ras-tva/export/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])
