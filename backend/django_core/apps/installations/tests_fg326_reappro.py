"""
FG326 — Réapprovisionnement multi-dépôts.

Couvre :
  * création d'une règle : société/`created_by` posés serveur ;
  * seuil_max < seuil_min rejeté ;
  * un emplacement d'une autre société rejeté ;
  * `propositions` ne propose que les SKU sous leur min, jusqu'au max ;
  * scope société + barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg326_reappro -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import RegleReappro

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg326-co-{n}', defaults={'nom': nom or f'FG326 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg326-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_emplacement(company, nom='Dépôt'):
    from apps.stock.models import EmplacementStock
    return EmplacementStock.objects.create(company=company, nom=nom)


def make_produit(company, nom='Panneau 550W', stock=0):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=1500, prix_achat=0,
        quantite_stock=stock)


class TestRegleReappro(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.cible = make_emplacement(self.company, 'Camionnette')
        self.source = make_emplacement(self.company, 'Dépôt principal')
        self.produit = make_produit(self.company, stock=2)

    def test_create_sets_company_server_side(self):
        resp = self.api.post(f'{BASE}/regles-reappro/', {
            'produit': self.produit.id, 'emplacement_cible': self.cible.id,
            'emplacement_source': self.source.id,
            'seuil_min': 5, 'seuil_max': 20, 'company': 999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        r = RegleReappro.objects.get(id=resp.data['id'])
        self.assertEqual(r.company_id, self.company.id)
        self.assertEqual(r.created_by_id, self.user.id)

    def test_max_below_min_rejected(self):
        resp = self.api.post(f'{BASE}/regles-reappro/', {
            'produit': self.produit.id, 'emplacement_cible': self.cible.id,
            'seuil_min': 10, 'seuil_max': 5,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_emplacement_other_company_rejected(self):
        other = make_company()
        cible_other = make_emplacement(other)
        resp = self.api.post(f'{BASE}/regles-reappro/', {
            'produit': self.produit.id, 'emplacement_cible': cible_other.id,
            'seuil_min': 1, 'seuil_max': 5,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_propositions_only_below_min(self):
        # produit à 2 en stock, min 5, max 20 → propose 18
        RegleReappro.objects.create(
            company=self.company, produit=self.produit,
            emplacement_cible=self.cible, emplacement_source=self.source,
            seuil_min=5, seuil_max=20)
        # un autre produit bien fourni → aucune proposition
        p2 = make_produit(self.company, 'Câble', stock=50)
        RegleReappro.objects.create(
            company=self.company, produit=p2,
            emplacement_cible=self.cible, seuil_min=5, seuil_max=20)
        resp = self.api.get(f'{BASE}/regles-reappro/propositions/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 1)
        prop = resp.data[0]
        self.assertEqual(prop['produit_id'], self.produit.id)
        self.assertEqual(prop['quantite_proposee'], 18)


class TestScopingAndRoles(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company()
        self.cible = make_emplacement(self.company)
        self.produit = make_produit(self.company)

    def test_commercial_cannot_write(self):
        api = auth(make_user(self.company, role='commercial'))
        resp = api.post(f'{BASE}/regles-reappro/', {
            'produit': self.produit.id, 'emplacement_cible': self.cible.id,
            'seuil_min': 1, 'seuil_max': 5,
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_other_company_cannot_see(self):
        RegleReappro.objects.create(
            company=self.company, produit=self.produit,
            emplacement_cible=self.cible, seuil_min=1, seuil_max=5)
        api = auth(make_user(self.other))
        resp = api.get(f'{BASE}/regles-reappro/')
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)
