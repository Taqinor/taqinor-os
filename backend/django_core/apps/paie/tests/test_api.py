"""Tests API de la Paie marocaine.

Couvre : société posée côté serveur (jamais du corps), isolation entre sociétés
(A ne voit pas les paramètres de B), et accès réservé au palier
Administrateur/Responsable.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.paie.models import ParametrePaie, Rubrique
from apps.paie.services import RUBRIQUES_DEFAUT, ensure_rubriques_defaut

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class PaieApiTests(TestCase):
    BASE = '/api/django/paie/parametres/'

    def setUp(self):
        self.co_a = make_company('paie-a', 'A')
        self.co_b = make_company('paie-b', 'B')
        self.user_a = make_user(self.co_a, 'paie-a')
        self.user_b = make_user(self.co_b, 'paie-b')

    def _payload(self):
        # Corps de création minimal (NO 'company') : date_effet seule, le reste
        # prend ses valeurs par défaut.
        return {'date_effet': '2026-01-01'}

    def _model_kwargs(self):
        return {'date_effet': '2026-01-01'}

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ParametrePaie.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_list_isolation(self):
        ParametrePaie.objects.create(company=self.co_a, **self._model_kwargs())
        api_b = auth(self.user_b)
        resp = api_b.get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'paie-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)


class RubriqueApiTests(TestCase):
    """PAIE6 — rubriques paramétrables : société serveur, isolation, rôle, seed."""

    BASE = '/api/django/paie/rubriques/'

    def setUp(self):
        self.co_a = make_company('paie-rub-a', 'A')
        self.co_b = make_company('paie-rub-b', 'B')
        self.user_a = make_user(self.co_a, 'paie-rub-a')
        self.user_b = make_user(self.co_b, 'paie-rub-b')

    def _payload(self):
        # Corps minimal (NO 'company') : une prime imposable soumise CNSS/AMO.
        return {
            'code': 'PRIME',
            'libelle': 'Prime de rendement',
            'type': 'gain',
            'imposable': True,
            'soumis_cnss': True,
            'soumis_amo': True,
            'soumis_cimr': False,
            'compte': '6411',
            'base': 'brut',
            'taux': None,
            'montant_fixe': '500.00',
            'ordre': 5,
        }

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Rubrique.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.type, 'gain')
        self.assertTrue(obj.imposable)
        self.assertTrue(obj.soumis_cnss)
        self.assertFalse(obj.soumis_cimr)
        # 'company' ne fuite pas dans la réponse.
        self.assertNotIn('company', resp.data)

    def test_company_in_body_is_ignored(self):
        api = auth(self.user_a)
        payload = self._payload()
        payload['company'] = self.co_b.id
        resp = api.post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Rubrique.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_list_isolation(self):
        Rubrique.objects.create(
            company=self.co_a, code='SB', libelle='Salaire de base')
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'paie-rub-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)

    def test_seed_defaults_idempotent_and_scoped(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE + 'seed-defaults/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['rubriques'], len(RUBRIQUES_DEFAUT))
        self.assertEqual(
            Rubrique.objects.filter(company=self.co_a).count(),
            len(RUBRIQUES_DEFAUT))
        # Re-seed : aucun doublon créé.
        resp2 = api.post(self.BASE + 'seed-defaults/', {}, format='json')
        self.assertEqual(resp2.data['rubriques'], 0)
        self.assertEqual(
            Rubrique.objects.filter(company=self.co_a).count(),
            len(RUBRIQUES_DEFAUT))
        # Scopé société : B n'a rien.
        self.assertEqual(
            Rubrique.objects.filter(company=self.co_b).count(), 0)

    def test_seed_defaults_never_overwrites_edited(self):
        # Une rubrique 'SB' déjà éditée doit survivre au seed.
        edited = Rubrique.objects.create(
            company=self.co_a, code='SB', libelle='Mon salaire édité',
            montant_fixe='9999.00')
        ensure_rubriques_defaut(self.co_a)
        edited.refresh_from_db()
        self.assertEqual(edited.libelle, 'Mon salaire édité')

    def test_unique_code_per_company(self):
        Rubrique.objects.create(
            company=self.co_a, code='SB', libelle='Salaire de base')
        api = auth(self.user_a)
        payload = self._payload()
        payload['code'] = 'SB'
        resp = api.post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        # Même code autorisé pour une autre société.
        Rubrique.objects.create(
            company=self.co_b, code='SB', libelle='Salaire de base B')
