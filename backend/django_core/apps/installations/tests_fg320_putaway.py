"""
FG320 — Rangement guidé (put-away).

Couvre :
  * création d'un put-away : société/`created_by`/`bin_suggere` posés serveur ;
  * la suggestion réutilise le casier affecté au produit (FG319) ;
  * l'action `ranger` pose `bin_effectif`/`range_par`/date + statut RANGE ;
  * un produit/casier d'une autre société rejeté ;
  * scope société + barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg320_putaway -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import PutAway, BinLocation, BinAffectation

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg320-co-{n}', defaults={'nom': nom or f'FG320 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg320-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_emplacement(company, nom='Dépôt'):
    from apps.stock.models import EmplacementStock
    return EmplacementStock.objects.create(company=company, nom=nom)


def make_produit(company, nom='Onduleur 5kW'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=8000, prix_achat=0)


class TestPutAway(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.emp = make_emplacement(self.company)
        self.produit = make_produit(self.company)
        self.bin = BinLocation.objects.create(
            company=self.company, emplacement=self.emp, code='A-1-1', ordre=1)

    def test_create_suggests_affected_bin(self):
        BinAffectation.objects.create(
            company=self.company, bin=self.bin, produit=self.produit,
            quantite=5)
        resp = self.api.post(f'{BASE}/putaways/', {
            'produit': self.produit.id, 'emplacement': self.emp.id,
            'quantite': 3, 'company': 999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        pa = PutAway.objects.get(id=resp.data['id'])
        self.assertEqual(pa.company_id, self.company.id)
        self.assertEqual(pa.created_by_id, self.user.id)
        self.assertEqual(pa.bin_suggere_id, self.bin.id)
        self.assertEqual(pa.statut, PutAway.Statut.A_RANGER)

    def test_create_falls_back_to_first_bin(self):
        resp = self.api.post(f'{BASE}/putaways/', {
            'produit': self.produit.id, 'emplacement': self.emp.id,
            'quantite': 2,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        pa = PutAway.objects.get(id=resp.data['id'])
        self.assertEqual(pa.bin_suggere_id, self.bin.id)

    def test_ranger_confirms(self):
        pa = PutAway.objects.create(
            company=self.company, produit=self.produit, emplacement=self.emp,
            quantite=4, bin_suggere=self.bin)
        resp = self.api.post(f'{BASE}/putaways/{pa.id}/ranger/', {},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        pa.refresh_from_db()
        self.assertEqual(pa.statut, PutAway.Statut.RANGE)
        self.assertEqual(pa.bin_effectif_id, self.bin.id)
        self.assertEqual(pa.range_par_id, self.user.id)
        self.assertIsNotNone(pa.date_rangement)

    def test_produit_other_company_rejected(self):
        other = make_company()
        p_other = make_produit(other)
        resp = self.api.post(f'{BASE}/putaways/', {
            'produit': p_other.id, 'quantite': 1,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)


class TestScopingAndRoles(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company()
        self.emp = make_emplacement(self.company)
        self.produit = make_produit(self.company)

    def test_commercial_cannot_write(self):
        commercial = make_user(self.company, role='commercial')
        api = auth(commercial)
        resp = api.post(f'{BASE}/putaways/', {
            'produit': self.produit.id, 'quantite': 1,
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_other_company_cannot_see(self):
        PutAway.objects.create(
            company=self.company, produit=self.produit, quantite=1)
        api = auth(make_user(self.other))
        resp = api.get(f'{BASE}/putaways/')
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)
