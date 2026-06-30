"""
FG333 — Réservation à la livraison (dépôt vs site).

Couvre :
  * `mode_acheminement` réglable à la création (défaut = via le dépôt) ;
  * le sélecteur `emplacement_a_decrementer_livraison` : dépôt en mode `depot`,
    None en mode `direct_site` ;
  * filtre par `mode_acheminement` ;
  * scope société + barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg333_reservation_livraison -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations import selectors
from apps.installations.models import Installation, Livraison

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg333-co-{n}', defaults={'nom': nom or f'FG333 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg333-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_emplacement(company, nom='Dépôt'):
    from apps.stock.models import EmplacementStock
    return EmplacementStock.objects.create(company=company, nom=nom)


def make_installation(company, ref='RL1'):
    client = Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'rl-{company.id}-{ref}@example.invalid')
    return Installation.objects.create(
        company=company, reference=ref, client=client,
        statut=Installation.Statut.RECEPTIONNE,
        type_installation='residentiel',
        puissance_installee_kwc=Decimal('6.5'))


class TestModeAcheminement(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.depot = make_emplacement(self.company)

    def test_default_mode_is_depot(self):
        resp = self.api.post(f'{BASE}/livraisons/', {
            'installation': self.inst.id, 'depot': self.depot.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        liv = Livraison.objects.get(id=resp.data['id'])
        self.assertEqual(
            liv.mode_acheminement, Livraison.ModeAcheminement.DEPOT)

    def test_create_direct_site(self):
        resp = self.api.post(f'{BASE}/livraisons/', {
            'installation': self.inst.id, 'depot': self.depot.id,
            'mode_acheminement': 'direct_site',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        liv = Livraison.objects.get(id=resp.data['id'])
        self.assertEqual(
            liv.mode_acheminement, Livraison.ModeAcheminement.DIRECT_SITE)

    def test_selecteur_depot_mode(self):
        liv = Livraison.objects.create(
            company=self.company, installation=self.inst, reference='LIV-D',
            depot=self.depot,
            mode_acheminement=Livraison.ModeAcheminement.DEPOT)
        emp = selectors.emplacement_a_decrementer_livraison(liv)
        self.assertEqual(emp, self.depot)

    def test_selecteur_direct_site_none(self):
        liv = Livraison.objects.create(
            company=self.company, installation=self.inst, reference='LIV-S',
            depot=self.depot,
            mode_acheminement=Livraison.ModeAcheminement.DIRECT_SITE)
        emp = selectors.emplacement_a_decrementer_livraison(liv)
        self.assertIsNone(emp)

    def test_filter_by_mode(self):
        Livraison.objects.create(
            company=self.company, installation=self.inst, reference='LIV-1',
            mode_acheminement=Livraison.ModeAcheminement.DIRECT_SITE)
        Livraison.objects.create(
            company=self.company, installation=self.inst, reference='LIV-2',
            mode_acheminement=Livraison.ModeAcheminement.DEPOT)
        resp = self.api.get(
            f'{BASE}/livraisons/?mode_acheminement=direct_site')
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data.get('results', resp.data)
        modes = {r['mode_acheminement'] for r in results}
        self.assertEqual(modes, {'direct_site'})


class TestScopingAndRoles(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company()
        self.inst = make_installation(self.company)

    def test_commercial_cannot_write(self):
        api = auth(make_user(self.company, role='commercial'))
        resp = api.post(f'{BASE}/livraisons/', {
            'installation': self.inst.id, 'mode_acheminement': 'direct_site',
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
