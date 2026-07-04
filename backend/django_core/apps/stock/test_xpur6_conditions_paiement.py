"""XPUR6 — Conditions de paiement fournisseur & échéancier multi-tranches.

Couvre :
  * date_echeance auto-dérivée (délai + fin_de_mois), modifiable ensuite ;
  * échéancier 30/70 génère 2 tranches vues par le payment run (selector) ;
  * escompte calculé dans la fenêtre (informatif) ;
  * pas de délai configuré = comportement historique (date_echeance non
    dérivée).

Run:
    python manage.py test apps.stock.test_xpur6_conditions_paiement -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import EcheanceFactureFournisseur, FactureFournisseur, Fournisseur
from apps.stock.selectors import echeances_facture_fournisseur
from apps.stock.services import (
    derive_date_echeance, escompte_applicable,
    creer_echeancier_facture_fournisseur,
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


class Xpur6Base(TestCase):
    def setUp(self):
        self.company = _company('xpur6-co')
        self.user = _user(
            self.company, 'xpur6-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)


class TestDeriveDateEcheance(Xpur6Base):
    def test_no_delai_configured_returns_none(self):
        f = Fournisseur.objects.create(company=self.company, nom='Comptant')
        result = derive_date_echeance(f, datetime.date(2026, 7, 1))
        self.assertIsNone(result)

    def test_simple_delai_60_days(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='60j', delai_paiement_jours=60)
        result = derive_date_echeance(f, datetime.date(2026, 6, 1))
        self.assertEqual(result, datetime.date(2026, 6, 1) + datetime.timedelta(days=60))

    def test_fin_de_mois_rounds_to_month_end(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='60j FdM', delai_paiement_jours=60,
            fin_de_mois=True)
        result = derive_date_echeance(f, datetime.date(2026, 6, 1))
        # 2026-06-01 + 60j = 2026-07-31 -> fin de mois de juillet = 31
        self.assertEqual(result.month, 7)
        self.assertEqual(result.day, 31)


class TestFactureAutoDeriveEndpoint(Xpur6Base):
    def test_facture_60j_fin_de_mois_derives_echeance(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur 60j FdM',
            delai_paiement_jours=60, fin_de_mois=True)
        resp = self.api.post('/api/django/stock/factures-fournisseur/', {
            'fournisseur': f.id, 'date_facture': '2026-06-01',
            'montant_ht': '1000', 'montant_tva': '200', 'montant_ttc': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['date_echeance'], '2026-07-31')

    def test_explicit_date_echeance_not_overridden(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur avec delai',
            delai_paiement_jours=30)
        resp = self.api.post('/api/django/stock/factures-fournisseur/', {
            'fournisseur': f.id, 'date_facture': '2026-06-01',
            'date_echeance': '2026-08-15',
            'montant_ht': '1000', 'montant_tva': '200', 'montant_ttc': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['date_echeance'], '2026-08-15')

    def test_no_delai_leaves_date_echeance_manual(self):
        f = Fournisseur.objects.create(company=self.company, nom='Comptant 2')
        resp = self.api.post('/api/django/stock/factures-fournisseur/', {
            'fournisseur': f.id, 'date_facture': '2026-06-01',
            'montant_ht': '1000', 'montant_tva': '200', 'montant_ttc': '1200',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data['date_echeance'])


class TestEcheancierMultiTranches(Xpur6Base):
    def test_30_70_generates_two_tranches(self):
        f = Fournisseur.objects.create(company=self.company, nom='Import')
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR6-0001', fournisseur=f,
            montant_ht=Decimal('10000'), montant_tva=Decimal('2000'),
            montant_ttc=Decimal('12000'))
        resp = self.api.post(
            f'/api/django/stock/factures-fournisseur/{facture.id}/echeancier/',
            {'tranches': [
                {'pourcentage': 30, 'date_echeance': '2026-07-01'},
                {'pourcentage': 70, 'date_echeance': '2026-08-01'},
            ]}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(
            EcheanceFactureFournisseur.objects.filter(
                facture=facture).count(), 2)
        montants = sorted(
            Decimal(t['montant']) for t in resp.data)
        self.assertEqual(montants, [Decimal('3600.00'), Decimal('8400.00')])

    def test_echeances_visible_via_selector(self):
        f = Fournisseur.objects.create(company=self.company, nom='Import 2')
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR6-0002', fournisseur=f,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        creer_echeancier_facture_fournisseur(self.company, facture, [
            {'montant': Decimal('600'), 'date_echeance': datetime.date(2026, 7, 1)},
            {'montant': Decimal('600'), 'date_echeance': datetime.date(2026, 8, 1)},
        ])
        rows = echeances_facture_fournisseur(self.company, facture.id)
        self.assertEqual(len(rows), 2)

    def test_missing_date_echeance_rejected(self):
        f = Fournisseur.objects.create(company=self.company, nom='Import 3')
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR6-0003', fournisseur=f,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        resp = self.api.post(
            f'/api/django/stock/factures-fournisseur/{facture.id}/echeancier/',
            {'tranches': [{'pourcentage': 100}]}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


class TestEscompte(Xpur6Base):
    def test_no_escompte_configured_returns_false(self):
        f = Fournisseur.objects.create(company=self.company, nom='Sans escompte')
        self.assertFalse(escompte_applicable(
            f, datetime.date(2026, 6, 1), datetime.date(2026, 6, 5)))

    def test_within_window_true(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='2/10 net 30',
            escompte_pct=Decimal('2'), escompte_jours=10)
        self.assertTrue(escompte_applicable(
            f, datetime.date(2026, 6, 1), datetime.date(2026, 6, 8)))

    def test_outside_window_false(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='2/10 net 30 late',
            escompte_pct=Decimal('2'), escompte_jours=10)
        self.assertFalse(escompte_applicable(
            f, datetime.date(2026, 6, 1), datetime.date(2026, 6, 20)))

    def test_payment_endpoint_surfaces_escompte_flag(self):
        f = Fournisseur.objects.create(
            company=self.company, nom='Escompte flag',
            escompte_pct=Decimal('2'), escompte_jours=10)
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR6-0004', fournisseur=f,
            date_facture=datetime.date(2026, 6, 1),
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': '1200',
            'date_paiement': '2026-06-05',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('escompte_disponible_pct', resp.data)
