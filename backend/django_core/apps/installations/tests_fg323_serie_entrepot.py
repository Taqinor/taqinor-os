"""
FG323 — Suivi du stock par numéro de série en entrepôt.

Couvre :
  * création d'un n° de série : société/`created_by` posés serveur ;
  * un produit/casier d'une autre société rejeté ;
  * unicité (company, produit, numero_serie) ;
  * cycle reserver (lie un chantier) / sortir ;
  * filtre par produit/statut/numero_serie ;
  * scope société + barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg323_serie_entrepot -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, SerieEntrepot

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg323-co-{n}', defaults={'nom': nom or f'FG323 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg323-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_emplacement(company, nom='Dépôt'):
    from apps.stock.models import EmplacementStock
    return EmplacementStock.objects.create(company=company, nom=nom)


def make_produit(company, nom='Onduleur 5kW'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=8000, prix_achat=0)


def make_installation(company, ref='SE1'):
    client = Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'se-{company.id}-{ref}@example.invalid')
    return Installation.objects.create(
        company=company, reference=ref, client=client,
        statut=Installation.Statut.RECEPTIONNE,
        type_installation='residentiel',
        puissance_installee_kwc=Decimal('6.5'))


class TestSerieEntrepot(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.emp = make_emplacement(self.company)
        self.produit = make_produit(self.company)

    def test_create_sets_company_server_side(self):
        resp = self.api.post(f'{BASE}/series-entrepot/', {
            'produit': self.produit.id, 'numero_serie': 'SN-001',
            'emplacement': self.emp.id, 'company': 999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        s = SerieEntrepot.objects.get(id=resp.data['id'])
        self.assertEqual(s.company_id, self.company.id)
        self.assertEqual(s.created_by_id, self.user.id)
        self.assertEqual(s.statut, SerieEntrepot.Statut.EN_STOCK)

    def test_produit_other_company_rejected(self):
        other = make_company()
        p_other = make_produit(other)
        resp = self.api.post(f'{BASE}/series-entrepot/', {
            'produit': p_other.id, 'numero_serie': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_unique_serial_per_product(self):
        SerieEntrepot.objects.create(
            company=self.company, produit=self.produit, numero_serie='SN-DUP')
        resp = self.api.post(f'{BASE}/series-entrepot/', {
            'produit': self.produit.id, 'numero_serie': 'SN-DUP',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_cycle_reserver_sortir(self):
        s = SerieEntrepot.objects.create(
            company=self.company, produit=self.produit, numero_serie='SN-9')
        inst = make_installation(self.company)
        r1 = self.api.post(
            f'{BASE}/series-entrepot/{s.id}/reserver/',
            {'installation': inst.id}, format='json')
        self.assertEqual(r1.status_code, 200, r1.content)
        s.refresh_from_db()
        self.assertEqual(s.statut, SerieEntrepot.Statut.RESERVE)
        self.assertEqual(s.installation_id, inst.id)
        r2 = self.api.post(
            f'{BASE}/series-entrepot/{s.id}/sortir/', {}, format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
        s.refresh_from_db()
        self.assertEqual(s.statut, SerieEntrepot.Statut.SORTI)

    def test_filter_by_statut(self):
        SerieEntrepot.objects.create(
            company=self.company, produit=self.produit, numero_serie='A',
            statut=SerieEntrepot.Statut.EN_STOCK)
        SerieEntrepot.objects.create(
            company=self.company, produit=self.produit, numero_serie='B',
            statut=SerieEntrepot.Statut.SORTI)
        resp = self.api.get(f'{BASE}/series-entrepot/?statut=sorti')
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['numero_serie'], 'B')


class TestScopingAndRoles(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company()
        self.produit = make_produit(self.company)

    def test_commercial_cannot_write(self):
        api = auth(make_user(self.company, role='commercial'))
        resp = api.post(f'{BASE}/series-entrepot/', {
            'produit': self.produit.id, 'numero_serie': 'NO',
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_other_company_cannot_see(self):
        SerieEntrepot.objects.create(
            company=self.company, produit=self.produit, numero_serie='Z')
        api = auth(make_user(self.other))
        resp = api.get(f'{BASE}/series-entrepot/')
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)
