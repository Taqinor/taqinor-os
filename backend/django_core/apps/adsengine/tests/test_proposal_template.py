"""PUB50 — Gabarits de proposition réutilisables.

Prouve : CRUD company-scopé (créer / appliquer(=lire) / supprimer), filtre par
``kind`` pour le composeur, et que le viewset n'EXÉCUTE rien (il ne fait que
stocker/renvoyer une combinaison à pré-remplir).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import EngineAction, ProposalTemplate

User = get_user_model()

BASE = '/api/django/adsengine/gabarits-proposition/'


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


class ProposalTemplateTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Tmpl Co', slug='tmpl-co')
        self.user = make_user(
            self.company, 'tmpl_mgr',
            ['adsengine_view', 'adsengine_manage'])

    def test_create_apply_delete(self):
        # Créer un gabarit « Ramadan agressif » pour set_spend_cap.
        resp = auth(self.user).post(BASE, {
            'name': 'Ramadan agressif', 'kind': 'set_spend_cap',
            'scope': 'campaign',
            'payload': {'spend_cap': '500000'},
            'reason_fr': 'Budget Ramadan renforcé.',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        tid = resp.data['id']
        # Appliquer = LIRE le gabarit (le pré-remplissage est côté front).
        get = auth(self.user).get(f'{BASE}{tid}/')
        self.assertEqual(get.status_code, 200)
        self.assertEqual(get.data['payload']['spend_cap'], '500000')
        # Créer un gabarit N'A créé AUCUNE EngineAction (rien exécuté).
        self.assertEqual(EngineAction.objects.count(), 0)
        # Supprimer.
        dele = auth(self.user).delete(f'{BASE}{tid}/')
        self.assertEqual(dele.status_code, 204)
        self.assertFalse(ProposalTemplate.objects.filter(id=tid).exists())

    def test_company_forced_server_side(self):
        other = Company.objects.create(nom='Tmpl B', slug='tmpl-b')
        resp = auth(self.user).post(BASE, {
            'name': 'Hiver prudent', 'kind': 'rebalance_budget',
            'company': other.id,  # tentative d'injection — ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        tmpl = ProposalTemplate.objects.get(id=resp.data['id'])
        self.assertEqual(tmpl.company_id, self.company.id)

    def test_filter_by_kind(self):
        ProposalTemplate.objects.create(
            company=self.company, name='A', kind='set_schedule')
        ProposalTemplate.objects.create(
            company=self.company, name='B', kind='set_spend_cap')
        resp = auth(self.user).get(f'{BASE}?kind=set_schedule')
        self.assertEqual(resp.status_code, 200)
        names = [r['name'] for r in rows(resp)]
        self.assertEqual(names, ['A'])

    def test_list_company_scoped(self):
        ProposalTemplate.objects.create(
            company=self.company, name='Mine', kind='pause')
        other = Company.objects.create(nom='Tmpl C', slug='tmpl-c')
        ProposalTemplate.objects.create(
            company=other, name='Theirs', kind='pause')
        resp = auth(self.user).get(BASE)
        self.assertEqual(len(rows(resp)), 1)

    def test_name_required(self):
        resp = auth(self.user).post(BASE, {
            'name': '   ', 'kind': 'pause'}, format='json')
        self.assertEqual(resp.status_code, 400)
