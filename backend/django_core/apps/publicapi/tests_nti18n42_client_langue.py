"""NTI18N42 — langue documentaire RÉSOLUE d'un client, en lecture publique.

CRITÈRE D'ACCEPTATION : une clé d'API sans droit « lecture clients »
(``read:clients``) reçoit 403 sur ``GET /api/public/v1/clients/<id>/langue/``.
Vérifié aussi : la société de la clé borne la lecture (404 pour un client d'une
autre société), la langue servie est celle de ``resolve_langue_sortie`` (repli
société inclus), et AUCUN autre champ de la fiche client ne sort.
"""
import json

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from authentication.models import Company

from .models import ApiKey
from .portees import ALL_SCOPES, SCOPE_READ_CLIENTS, SCOPE_READ_LEADS

URL = '/api/public/v1/clients/{}/langue/'


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


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
        resp = _key_client(self.raw_sans_droit).get(URL.format(self.client_fr.pk))
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_sans_cle_401(self):
        resp = APIClient().get(URL.format(self.client_fr.pk))
        self.assertEqual(resp.status_code, 401, resp.content)

    def test_preference_client_arabe_est_servie(self):
        resp = _key_client(self.raw).get(URL.format(self.client_ar.pk))
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
        resp = _key_client(self.raw).get(URL.format(self.client_fr.pk))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['langue_document'], 'fr')
        self.assertEqual(resp.data['langue_sortie'], 'en')

    def test_client_dune_autre_societe_est_un_404(self):
        resp = _key_client(self.raw).get(URL.format(self.client_autre.pk))
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_aucun_autre_champ_de_la_fiche_ne_sort(self):
        resp = _key_client(self.raw).get(URL.format(self.client_fr.pk))
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
