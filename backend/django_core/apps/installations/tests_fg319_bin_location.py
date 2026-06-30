"""
FG319 — Emplacements fins zone/allée/casier (bin locations).

Couvre :
  * création d'un casier via l'API : société + ``created_by`` posés CÔTÉ SERVEUR ;
  * l'injection de ``company``/``created_by`` est ignorée ;
  * un emplacement d'une autre société est rejeté ;
  * affectation produit ↔ casier ; un produit d'une autre société rejeté ;
  * le filtre par emplacement / archived ;
  * le scope société et la barrière de rôle (lecture tout rôle, écriture
    responsable/admin).

Run :
    python manage.py test apps.installations.tests_fg319_bin_location -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import BinLocation, BinAffectation

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg319-co-{n}', defaults={'nom': nom or f'FG319 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg319-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_emplacement(company, nom='Dépôt principal'):
    from apps.stock.models import EmplacementStock
    return EmplacementStock.objects.create(company=company, nom=nom)


def make_produit(company, nom='Onduleur 5kW'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=8000, prix_achat=0)


class TestBinCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.emp = make_emplacement(self.company)

    def test_create_sets_company_and_created_by_server_side(self):
        other = make_company()
        resp = self.api.post(f'{BASE}/bin-locations/', {
            'emplacement': self.emp.id,
            'code': 'A-03-12',
            'zone': 'A', 'allee': '03', 'casier': '12',
            'company': other.id,        # injection ignorée
            'created_by': 999,          # injection ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        b = BinLocation.objects.get(id=resp.data['id'])
        self.assertEqual(b.company_id, self.company.id)
        self.assertEqual(b.created_by_id, self.user.id)
        self.assertEqual(b.code, 'A-03-12')

    def test_emplacement_other_company_rejected(self):
        other = make_company()
        emp_other = make_emplacement(other)
        resp = self.api.post(f'{BASE}/bin-locations/', {
            'emplacement': emp_other.id, 'code': 'X-1-1',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('emplacement', resp.data)

    def test_blank_code_rejected(self):
        resp = self.api.post(f'{BASE}/bin-locations/', {
            'emplacement': self.emp.id, 'code': '   ',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)


class TestBinAffectation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.emp = make_emplacement(self.company)
        self.bin = BinLocation.objects.create(
            company=self.company, emplacement=self.emp, code='B-01-01')
        self.produit = make_produit(self.company)

    def test_affecter_produit(self):
        resp = self.api.post(f'{BASE}/bin-affectations/', {
            'bin': self.bin.id, 'produit': self.produit.id, 'quantite': 7,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        a = BinAffectation.objects.get(id=resp.data['id'])
        self.assertEqual(a.company_id, self.company.id)
        self.assertEqual(a.quantite, 7)

    def test_produit_other_company_rejected(self):
        other = make_company()
        p_other = make_produit(other)
        resp = self.api.post(f'{BASE}/bin-affectations/', {
            'bin': self.bin.id, 'produit': p_other.id, 'quantite': 1,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)


class TestScopingAndRoles(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company()
        self.emp = make_emplacement(self.company)
        BinLocation.objects.create(
            company=self.company, emplacement=self.emp, code='Z-1-1')

    def test_other_company_cannot_see(self):
        other_user = make_user(self.other)
        api = auth(other_user)
        resp = api.get(f'{BASE}/bin-locations/')
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)

    def test_commercial_cannot_write(self):
        commercial = make_user(self.company, role='commercial')
        api = auth(commercial)
        resp = api.post(f'{BASE}/bin-locations/', {
            'emplacement': self.emp.id, 'code': 'NO-1-1',
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_commercial_can_read(self):
        commercial = make_user(self.company, role='commercial')
        api = auth(commercial)
        resp = api.get(f'{BASE}/bin-locations/')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_filter_by_emplacement(self):
        user = make_user(self.company)
        api = auth(user)
        resp = api.get(f'{BASE}/bin-locations/?emplacement={self.emp.id}')
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 1)
