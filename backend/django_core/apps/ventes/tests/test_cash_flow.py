"""Tests FG47 — prévision cash-flow / encaissements à venir."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Facture, Paiement
from apps.ventes.utils.references import next_reference

User = get_user_model()
URL = '/api/django/ventes/insights/cash-flow/'
TODAY = timezone.now().date()


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _company(slug='cf-co', nom='CashFlow Co'):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return c


def _user(co, username='cf_user'):
    return User.objects.create_user(
        username=username, password='x', role_legacy='responsable', company=co)


def _client(co):
    return Client.objects.create(
        company=co, nom='CF', prenom='Client',
        email='cf@example.com', telephone='+212600000077')


def _facture(co, client, statut='emise', ttc=Decimal('10000'), echeance=None):
    ref = next_reference(Facture, 'FAC', co)
    return Facture.objects.create(
        company=co, client=client,
        reference=ref, statut=statut,
        taux_tva=Decimal('20'),
        montant_ht=ttc / Decimal('1.2'),
        montant_tva=ttc / Decimal('6'),
        montant_ttc=ttc,
        date_echeance=echeance,
    )


def _paiement(co, facture, montant):
    return Paiement.objects.create(
        company=co, facture=facture,
        montant=montant,
        date_paiement=TODAY,
        mode='virement',
    )


class TestCashFlowBasic(TestCase):
    def setUp(self):
        self.co = _company()
        self.user = _user(self.co)
        self.cli = _client(self.co)
        self.api = _auth(self.user)

    def test_endpoint_returns_200(self):
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200)

    def test_response_structure(self):
        r = self.api.get(URL)
        self.assertIn('buckets', r.data)
        self.assertIn('total_en_cours', r.data)
        self.assertIn('rows', r.data)

    def test_buckets_keys_present(self):
        r = self.api.get(URL)
        expected_keys = {
            'en_retard', 'cette_semaine', 'semaine_suivante',
            'ce_mois', 'mois_suivant', 'au_dela', 'sans_echeance',
        }
        self.assertEqual(set(r.data['buckets'].keys()), expected_keys)

    def test_empty_company_returns_zeros(self):
        r = self.api.get(URL)
        self.assertEqual(r.data['total_en_cours'], '0.00')
        self.assertEqual(r.data['rows'], [])

    def test_unauthenticated_returns_401(self):
        r = APIClient().get(URL)
        self.assertIn(r.status_code, (401, 403))


class TestCashFlowBucketing(TestCase):
    """Vérifie que les factures sont bucketisées correctement."""

    def setUp(self):
        self.co = _company(slug='cf-bucket', nom='CF Bucket')
        self.user = _user(self.co, username='cf_bucket_user')
        self.cli = _client(self.co)
        self.api = _auth(self.user)

    def test_past_due_facture_in_en_retard(self):
        past = TODAY - timedelta(days=10)
        _facture(self.co, self.cli, statut='en_retard',
                 ttc=Decimal('5000'), echeance=past)
        r = self.api.get(URL)
        bucket = r.data['buckets']['en_retard']
        self.assertEqual(bucket['count'], 1)
        self.assertAlmostEqual(float(bucket['montant']), 5000.0, delta=0.01)

    def test_this_week_facture(self):
        soon = TODAY + timedelta(days=3)
        _facture(self.co, self.cli, statut='emise',
                 ttc=Decimal('3000'), echeance=soon)
        r = self.api.get(URL)
        bucket = r.data['buckets']['cette_semaine']
        self.assertEqual(bucket['count'], 1)
        self.assertAlmostEqual(float(bucket['montant']), 3000.0, delta=0.01)

    def test_next_week_facture(self):
        next_wk = TODAY + timedelta(days=10)
        _facture(self.co, self.cli, statut='emise',
                 ttc=Decimal('2000'), echeance=next_wk)
        r = self.api.get(URL)
        bucket = r.data['buckets']['semaine_suivante']
        self.assertEqual(bucket['count'], 1)

    def test_sans_echeance_facture(self):
        _facture(self.co, self.cli, statut='emise',
                 ttc=Decimal('4000'), echeance=None)
        r = self.api.get(URL)
        bucket = r.data['buckets']['sans_echeance']
        self.assertEqual(bucket['count'], 1)

    def test_beyond_buckets(self):
        far = TODAY + timedelta(days=120)
        _facture(self.co, self.cli, statut='emise',
                 ttc=Decimal('7000'), echeance=far)
        r = self.api.get(URL)
        bucket = r.data['buckets']['au_dela']
        self.assertEqual(bucket['count'], 1)

    def test_paid_facture_not_in_rows(self):
        """Facture payée → exclue (statut payee)."""
        _facture(self.co, self.cli, statut='payee',
                 ttc=Decimal('1000'), echeance=TODAY - timedelta(days=5))
        r = self.api.get(URL)
        self.assertEqual(r.data['total_en_cours'], '0.00')
        self.assertEqual(r.data['rows'], [])

    def test_partially_paid_shows_remaining(self):
        """Facture partiellement payée → montant_du dans les rows."""
        f = _facture(self.co, self.cli, statut='emise',
                     ttc=Decimal('6000'), echeance=TODAY + timedelta(days=5))
        _paiement(self.co, f, Decimal('2000'))
        r = self.api.get(URL)
        # montant_du = 6000 - 2000 = 4000
        remaining = float(r.data['total_en_cours'])
        self.assertAlmostEqual(remaining, 4000.0, delta=0.01)

    def test_total_en_cours_sum(self):
        """Somme de toutes les factures ouvertes."""
        _facture(self.co, self.cli, statut='emise',
                 ttc=Decimal('3000'), echeance=TODAY - timedelta(days=5))
        _facture(self.co, self.cli, statut='emise',
                 ttc=Decimal('2000'), echeance=TODAY + timedelta(days=3))
        r = self.api.get(URL)
        total = float(r.data['total_en_cours'])
        self.assertAlmostEqual(total, 5000.0, delta=0.01)


class TestCashFlowCompanyScope(TestCase):
    """Vérifie l'isolation société."""

    def setUp(self):
        self.co1 = _company(slug='cf-co1', nom='CF Co1')
        self.co2 = _company(slug='cf-co2', nom='CF Co2')
        self.user1 = _user(self.co1, username='cf_u1')
        self.user2 = _user(self.co2, username='cf_u2')
        self.cli1 = _client(self.co1)
        self.cli2 = Client.objects.create(
            company=self.co2, nom='OC', prenom='Client',
            email='oc@example.com', telephone='+212600000076')
        self.api1 = _auth(self.user1)

    def test_other_company_not_visible(self):
        _facture(self.co2, self.cli2, statut='emise',
                 ttc=Decimal('9999'), echeance=TODAY - timedelta(days=5))
        r = self.api1.get(URL)
        self.assertEqual(r.data['total_en_cours'], '0.00')

    def test_own_facture_visible(self):
        _facture(self.co1, self.cli1, statut='emise',
                 ttc=Decimal('5000'), echeance=TODAY + timedelta(days=3))
        r = self.api1.get(URL)
        total = float(r.data['total_en_cours'])
        self.assertAlmostEqual(total, 5000.0, delta=0.01)


class TestCashFlowRowSorting(TestCase):
    """Les rows : retards en premier, triés par date_echeance."""

    def setUp(self):
        self.co = _company(slug='cf-sort', nom='CF Sort')
        self.user = _user(self.co, username='cf_sort_user')
        self.cli = _client(self.co)
        self.api = _auth(self.user)

    def test_overdue_rows_come_first(self):
        _facture(self.co, self.cli, statut='emise',
                 ttc=Decimal('1000'), echeance=TODAY + timedelta(days=5))
        _facture(self.co, self.cli, statut='en_retard',
                 ttc=Decimal('2000'), echeance=TODAY - timedelta(days=10))
        r = self.api.get(URL)
        rows = r.data['rows']
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['bucket'], 'en_retard')
