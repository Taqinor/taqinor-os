"""Tests FG45 — tableau de bord Quote-to-Cash."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, LigneDevis, Facture, LigneFacture, Paiement

User = get_user_model()
URL = '/api/django/ventes/dashboard/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _company(slug='dash-co', nom='Dash Co'):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return c


def _user(company, username='dash_user', role='responsable'):
    return User.objects.create_user(
        username=username, password='x', role_legacy=role, company=company)


def _client(company):
    return Client.objects.create(
        company=company, nom='Test', prenom='Client',
        email='tc@example.com', telephone='+212600000099')


def _devis(company, user, client, statut='brouillon', ref=None):
    ref = ref or f'DEV-{statut[:3].upper()}-{id(user)}'
    return Devis.objects.create(
        company=company, created_by=user, client=client,
        reference=ref, statut=statut,
    )


def _ligne_devis(devis, prix=Decimal('8000'), qte=1, remise=Decimal('0')):
    from apps.stock.models import Produit
    p, _ = Produit.objects.get_or_create(
        company=devis.company,
        sku='TEST-DASH',
        defaults={
            'nom': 'Produit Dashboard Test',
            'prix_vente': prix / Decimal('1.20'),
            'tva': Decimal('20'),
        },
    )
    return LigneDevis.objects.create(
        devis=devis,
        produit=p,
        designation='Test ligne',
        quantite=qte,
        prix_unitaire=prix / Decimal('1.20'),
        taux_tva=Decimal('20'),
        remise=remise,
    )


def _facture(company, client, devis=None, statut='emise', ttc=Decimal('9600')):
    from apps.ventes.utils.references import next_reference
    ref = next_reference(Facture, 'FAC', company)
    f = Facture.objects.create(
        company=company, client=client,
        reference=ref, statut=statut,
        taux_tva=Decimal('20'),
        montant_ht=ttc / Decimal('1.2'),
        montant_tva=ttc / Decimal('6'),
        montant_ttc=ttc,
    )
    if devis:
        devis.factures.add(f)
    return f


def _paiement(company, facture, montant=None):
    montant = montant or facture.montant_ttc
    return Paiement.objects.create(
        company=company, facture=facture,
        montant=montant,
        date_paiement=timezone.now().date(),
        mode='virement',
    )


class TestDashboardBasic(TestCase):
    def setUp(self):
        self.co = _company()
        self.user = _user(self.co)
        self.cli = _client(self.co)
        self.api = _auth(self.user)

    def test_dashboard_returns_200(self):
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200)

    def test_dashboard_keys_present(self):
        r = self.api.get(URL)
        self.assertIn('devis', r.data)
        self.assertIn('factures', r.data)
        self.assertIn('conversion', r.data)
        self.assertIn('dso_jours', r.data)
        self.assertIn('cycle_moyen_jours', r.data)
        self.assertIn('par_commercial', r.data)

    def test_dashboard_devis_keys(self):
        r = self.api.get(URL)
        d = r.data['devis']
        for k in ('total', 'envoyes', 'acceptes', 'refuses', 'expires',
                  'taux_acceptation_pct', 'valeur_pipeline'):
            self.assertIn(k, d)

    def test_dashboard_factures_keys(self):
        r = self.api.get(URL)
        f = r.data['factures']
        for k in ('total', 'emises', 'payees', 'en_retard', 'annulees',
                  'montant_facture', 'montant_encaisse'):
            self.assertIn(k, f)

    def test_dashboard_conversion_keys(self):
        r = self.api.get(URL)
        c = r.data['conversion']
        for k in ('devis_envoye_vers_accepte_pct', 'devis_accepte_vers_facture_pct',
                  'devis_envoye_vers_facture_pct'):
            self.assertIn(k, c)

    def test_empty_data_returns_nulls_and_zeros(self):
        r = self.api.get(URL)
        self.assertEqual(r.data['devis']['total'], 0)
        self.assertIsNone(r.data['dso_jours'])
        self.assertIsNone(r.data['cycle_moyen_jours'])
        self.assertEqual(r.data['par_commercial'], [])


class TestDashboardAggregation(TestCase):
    def setUp(self):
        self.co = _company(slug='dash-agg', nom='Dash Agg')
        self.user = _user(self.co, username='dash_agg_user')
        self.cli = _client(self.co)
        self.api = _auth(self.user)

    def test_devis_counts_by_statut(self):
        _devis(self.co, self.user, self.cli, statut='envoye', ref='D-ENV-1')
        _devis(self.co, self.user, self.cli, statut='envoye', ref='D-ENV-2')
        _devis(self.co, self.user, self.cli, statut='accepte', ref='D-ACC-1')
        _devis(self.co, self.user, self.cli, statut='refuse', ref='D-REF-1')
        r = self.api.get(URL)
        d = r.data['devis']
        self.assertEqual(d['envoyes'], 2)
        self.assertEqual(d['acceptes'], 1)
        self.assertEqual(d['refuses'], 1)
        self.assertGreaterEqual(d['total'], 4)

    def test_taux_acceptation_pct_calculated(self):
        # 2 envoyés, 1 accepté → 50 %
        _devis(self.co, self.user, self.cli, statut='envoye', ref='D-ENV-A1')
        _devis(self.co, self.user, self.cli, statut='envoye', ref='D-ENV-A2')
        _devis(self.co, self.user, self.cli, statut='accepte', ref='D-ACC-A1')
        r = self.api.get(URL)
        # taux_acceptation = acceptes / envoyes × 100
        # 1 accepte / 2 envoyes = 50 %
        self.assertEqual(r.data['devis']['taux_acceptation_pct'], 50.0)

    def test_valeur_pipeline_non_zero_when_lignes(self):
        d = _devis(self.co, self.user, self.cli, statut='envoye', ref='D-PIPE-1')
        _ligne_devis(d, prix=Decimal('12000'))
        r = self.api.get(URL)
        val = float(r.data['devis']['valeur_pipeline'])
        self.assertGreater(val, 0)

    def test_factures_montant_facture(self):
        _facture(self.co, self.cli, statut='emise', ttc=Decimal('5000'))
        _facture(self.co, self.cli, statut='payee', ttc=Decimal('3000'))
        r = self.api.get(URL)
        montant = float(r.data['factures']['montant_facture'])
        self.assertGreaterEqual(montant, 8000)

    def test_montant_encaisse(self):
        f = _facture(self.co, self.cli, statut='payee', ttc=Decimal('6000'))
        _paiement(self.co, f, montant=Decimal('6000'))
        r = self.api.get(URL)
        enc = float(r.data['factures']['montant_encaisse'])
        self.assertGreaterEqual(enc, 6000)

    def test_dso_calculation(self):
        # DSO = encours / (montant_facture / 30)
        f = _facture(self.co, self.cli, statut='emise', ttc=Decimal('3000'))
        r = self.api.get(URL)
        dso = r.data['dso_jours']
        # encours = 3000, montant_facture = 3000 → DSO = 30
        self.assertIsNotNone(dso)
        self.assertAlmostEqual(dso, 30.0, delta=1.0)

    def test_par_commercial_breakdown(self):
        d = _devis(self.co, self.user, self.cli, statut='envoye', ref='D-COM-1')
        _ligne_devis(d, prix=Decimal('8000'))
        r = self.api.get(URL)
        self.assertIsInstance(r.data['par_commercial'], list)
        if r.data['par_commercial']:
            row = r.data['par_commercial'][0]
            self.assertIn('commercial', row)
            self.assertIn('devis_actifs', row)
            self.assertIn('valeur_pipeline', row)


class TestDashboardCompanyScope(TestCase):
    """Vérifie que les données d'une autre société n'apparaissent jamais."""

    def setUp(self):
        self.co1 = _company(slug='dash-co1', nom='Company 1')
        self.co2 = _company(slug='dash-co2', nom='Company 2')
        self.user1 = _user(self.co1, username='dash_u1')
        self.user2 = _user(self.co2, username='dash_u2')
        self.cli1 = _client(self.co1)
        self.cli2 = Client.objects.create(
            company=self.co2, nom='Other', prenom='Client',
            email='other@example.com', telephone='+212600000098')
        self.api1 = _auth(self.user1)

    def test_other_company_devis_not_counted(self):
        # Devis de co2 — ne doit PAS apparaître dans le dashboard de co1
        _devis(self.co2, self.user2, self.cli2, statut='envoye', ref='D-CO2-1')
        r = self.api1.get(URL)
        self.assertEqual(r.data['devis']['envoyes'], 0)

    def test_other_company_factures_not_counted(self):
        _facture(self.co2, self.cli2, statut='emise', ttc=Decimal('9999'))
        r = self.api1.get(URL)
        montant = float(r.data['factures']['montant_facture'])
        self.assertEqual(montant, 0)

    def test_own_data_counted_correctly(self):
        _devis(self.co1, self.user1, self.cli1, statut='envoye', ref='D-CO1-1')
        _devis(self.co2, self.user2, self.cli2, statut='envoye', ref='D-CO2-X')
        r = self.api1.get(URL)
        self.assertEqual(r.data['devis']['envoyes'], 1)


class TestDashboardPeriodFilter(TestCase):
    """Vérifie le filtrage par ?month= et ?start=&end=."""

    def setUp(self):
        self.co = _company(slug='dash-period', nom='Period Co')
        self.user = _user(self.co, username='dash_period_user')
        self.cli = _client(self.co)
        self.api = _auth(self.user)

    def test_month_filter_accepted(self):
        r = self.api.get(URL, {'month': '2026-01'})
        self.assertEqual(r.status_code, 200)

    def test_start_end_filter_accepted(self):
        r = self.api.get(URL, {'start': '2026-01-01', 'end': '2026-12-31'})
        self.assertEqual(r.status_code, 200)

    def test_unauthenticated_returns_401(self):
        api = APIClient()
        r = api.get(URL)
        self.assertIn(r.status_code, (401, 403))
