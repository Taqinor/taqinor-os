"""NTLOG36 — ParametresDouane (réglages singleton par société).

Couvre : création paresseuse (``for_company``, idempotente, jamais
``count()+1``), défauts (J-30/J-15/J-7, mention estimation), API GET/PATCH,
isolation société, et le garde d'écriture ``douane_responsable`` (NTLOG43)
appliqué au même titre qu'aux autres viewsets douane.

Run :
    python manage.py test apps.douane.tests.test_ntlog36_parametres_douane -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.douane.models import ParametresDouane
from apps.douane.permissions import DOUANE_COMPTABILITE_VOIR

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/douane'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntlog36-co-{n}', defaults={'nom': f'NTLOG36 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntlog36-{next(_seq)}', password='x',
        role_legacy=role, company=company)


class TestForCompany(TestCase):
    def test_cree_avec_defauts_a_la_premiere_lecture(self):
        company = make_company()
        self.assertEqual(ParametresDouane.objects.filter(company=company).count(), 0)
        obj = ParametresDouane.for_company(company)
        self.assertEqual(obj.alerte_expiration_jours, [30, 15, 7])
        self.assertIn('non contractuelle', obj.mention_estimation_droits)
        self.assertEqual(
            obj.regime_douanier_par_defaut,
            ParametresDouane.RegimeDouanier.MISE_CONSOMMATION)

    def test_idempotent(self):
        company = make_company()
        obj1 = ParametresDouane.for_company(company)
        obj2 = ParametresDouane.for_company(company)
        self.assertEqual(obj1.id, obj2.id)
        self.assertEqual(ParametresDouane.objects.filter(company=company).count(), 1)

    def test_isolation_societe(self):
        company_a = make_company()
        company_b = make_company()
        obj_a = ParametresDouane.for_company(company_a)
        obj_b = ParametresDouane.for_company(company_b)
        self.assertNotEqual(obj_a.id, obj_b.id)


class TestApiParametresDouane(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_get_cree_a_la_volee(self):
        r = self.api.get(f'{BASE}/parametres-douane/')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data['alerte_expiration_jours'], [30, 15, 7])

    def test_patch_met_a_jour_mention(self):
        r = self.api.patch(f'{BASE}/parametres-douane/1/', {
            'mention_estimation_droits': 'Estimation maison — vérifier.',
        })
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        obj = ParametresDouane.for_company(self.company)
        self.assertEqual(obj.mention_estimation_droits, 'Estimation maison — vérifier.')

    def test_patch_alerte_expiration_jours(self):
        r = self.api.patch(f'{BASE}/parametres-douane/1/', {
            'alerte_expiration_jours': [45, 20, 10],
        })
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        obj = ParametresDouane.for_company(self.company)
        self.assertEqual(obj.alerte_expiration_jours, [45, 20, 10])


class TestPermissionsParametresDouane(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_comptabilite_lit_mais_ne_modifie_pas(self):
        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.company, nom='comptabilite',
            permissions=[DOUANE_COMPTABILITE_VOIR])
        user = User.objects.create_user(
            username=f'ntlog36-comptabilite-{next(_seq)}', password='x',
            role_legacy='normal', company=self.company, role=role)
        api = auth(user)

        r_get = api.get(f'{BASE}/parametres-douane/')
        self.assertEqual(r_get.status_code, status.HTTP_200_OK, r_get.data)

        r_patch = api.patch(
            f'{BASE}/parametres-douane/1/', {'mention_estimation_droits': 'x'})
        self.assertEqual(r_patch.status_code, status.HTTP_403_FORBIDDEN, r_patch.data)
