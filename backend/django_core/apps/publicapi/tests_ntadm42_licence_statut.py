"""NTADM42 — API publique lecture seule « statut de licence ».

``GET /api/public/v1/licence/statut/`` : renvoie EXACTEMENT
``{plan_code, modules_inclus, sieges_max, sieges_utilises}`` pour la société
de la clé — aucun champ interne (prix, historique). Clé invalide → 401."""
from django.contrib.auth import get_user_model
import json

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from authentication.models import Company

from .portees import (
    ALL_SCOPES, SCOPE_READ_CLIENTS, SCOPE_READ_LEADS, SCOPE_READ_LICENCE)
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


# NTI18N42 — langue documentaire résolue d'un client (scope read:clients).
URL_LANGUE = '/api/public/v1/clients/{}/langue/'


class Nti18n42ScopeTests(TestCase):
    def test_le_scope_est_declare_au_catalogue(self):
        self.assertIn(SCOPE_READ_CLIENTS, ALL_SCOPES)
        self.assertEqual(SCOPE_READ_CLIENTS, 'read:clients')


class Nti18n42ClientLangueTests(TestCase):
    def setUp(self):
        self.co = _company('nti18n42', 'NTI18N42')
        self.autre = _company('nti18n42-autre', 'NTI18N42 autre')
        self.client_fr = Client.objects.create(
            company=self.co, nom='Alaoui', email='secret@example.com')
        self.client_ar = Client.objects.create(
            company=self.co, nom='Bennani', langue_document='ar')
        self.client_autre = Client.objects.create(
            company=self.autre, nom='Etranger')
        _k, self.raw = ApiKey.issue(
            company=self.co, label='clients', scopes=[SCOPE_READ_CLIENTS])
        _k2, self.raw_sans_droit = ApiKey.issue(
            company=self.co, label='leads', scopes=[SCOPE_READ_LEADS])

    def test_cle_sans_droit_lecture_clients_recoit_403(self):
        resp = _key_client(self.raw_sans_droit).get(URL_LANGUE.format(self.client_fr.pk))
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_sans_cle_401(self):
        resp = APIClient().get(URL_LANGUE.format(self.client_fr.pk))
        self.assertEqual(resp.status_code, 401, resp.content)

    def test_preference_client_arabe_est_servie(self):
        resp = _key_client(self.raw).get(URL_LANGUE.format(self.client_ar.pk))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data, {
            'client_id': self.client_ar.pk,
            'langue_document': 'ar',
            'langue_sortie': 'ar',
        })

    def test_client_au_defaut_suit_le_repli_de_la_societe(self):
        profile = CompanyProfile.get(company=self.co)
        profile.langue_repli = 'en'
        profile.save(update_fields=['langue_repli'])
        resp = _key_client(self.raw).get(URL_LANGUE.format(self.client_fr.pk))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['langue_document'], 'fr')
        self.assertEqual(resp.data['langue_sortie'], 'en')

    def test_client_dune_autre_societe_est_un_404(self):
        resp = _key_client(self.raw).get(URL_LANGUE.format(self.client_autre.pk))
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_aucun_autre_champ_de_la_fiche_ne_sort(self):
        resp = _key_client(self.raw).get(URL_LANGUE.format(self.client_fr.pk))
        self.assertEqual(
            set(resp.data), {'client_id', 'langue_document', 'langue_sortie'})
        rendu = json.dumps(resp.data, default=str)
        self.assertNotIn('Alaoui', rendu)
        self.assertNotIn('secret@example.com', rendu)

    def test_le_chemin_est_documente_dans_openapi(self):
        from .openapi import build_openapi_schema
        schema = build_openapi_schema()
        chemin = '/api/public/v1/clients/{id}/langue/'
        self.assertIn(chemin, schema['paths'])
        params = schema['paths'][chemin]['get']['parameters']
        self.assertEqual([p['name'] for p in params], ['id'])
