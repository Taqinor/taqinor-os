"""NTADM42 — API publique lecture seule « statut de licence ».

``GET /api/public/v1/licence/statut/`` : renvoie EXACTEMENT
``{plan_code, modules_inclus, sieges_max, sieges_utilises}`` pour la société
de la clé — aucun champ interne (prix, historique). Clé invalide → 401."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from .constants import SCOPE_READ_LEADS, SCOPE_READ_LICENCE
from .models import ApiKey

User = get_user_model()

URL = '/api/public/v1/licence/statut/'


def _company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class PublicLicenceStatutTests(TestCase):
    def setUp(self):
        self.company = _company('ntadm42-a', 'NTADM42 A')
        self.key, self.raw = ApiKey.issue(
            company=self.company, label='licence',
            scopes=[SCOPE_READ_LICENCE])

    def test_cle_valide_renvoie_exactement_les_4_champs(self):
        resp = _key_client(self.raw).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            set(resp.data.keys()),
            {'plan_code', 'modules_inclus', 'sieges_max', 'sieges_utilises'})

    def test_sans_plan_assigne(self):
        resp = _key_client(self.raw).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['plan_code'])
        self.assertEqual(resp.data['modules_inclus'], [])
        self.assertIsNone(resp.data['sieges_max'])

    def test_avec_plan_assigne(self):
        from apps.adminops.models import PlanLicence
        from apps.parametres.models import CompanyProfile

        plan = PlanLicence.objects.get(code='starter')
        profile = CompanyProfile.get(company=self.company)
        profile.plan = plan
        profile.nb_sieges_max = 3
        profile.save(update_fields=['plan', 'nb_sieges_max'])

        resp = _key_client(self.raw).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['plan_code'], 'starter')
        self.assertEqual(resp.data['modules_inclus'], plan.modules_inclus)
        self.assertEqual(resp.data['sieges_max'], 3)

    def test_sieges_utilises_scope_par_societe(self):
        User.objects.create_user(
            username='u1', password='pw', company=self.company,
            role_legacy='normal')
        autre = _company('ntadm42-b', 'NTADM42 B')
        User.objects.create_user(
            username='u2', password='pw', company=autre, role_legacy='normal')
        User.objects.create_user(
            username='u3', password='pw', company=autre, role_legacy='normal')

        resp = _key_client(self.raw).get(URL)
        self.assertEqual(resp.data['sieges_utilises'], 1)

    def test_cle_invalide_401(self):
        resp = _key_client('tqk_does_not_exist').get(URL)
        self.assertEqual(resp.status_code, 401)

    def test_sans_cle_401_ou_403(self):
        resp = APIClient().get(URL)
        self.assertIn(resp.status_code, (401, 403))

    def test_cle_sans_scope_refuse(self):
        key_sans_scope, raw_sans_scope = ApiKey.issue(
            company=self.company, label='sans-scope',
            scopes=[SCOPE_READ_LEADS])
        resp = _key_client(raw_sans_scope).get(URL)
        self.assertEqual(resp.status_code, 403)
