"""XMKT34 — endpoint ``POST /api/django/compta/campagnes/generer-ia/``.

Couvre le contrat HTTP : sans clé LLM configurée, ``configured: false`` (le
frontend masque le bouton) ; avec un faux fournisseur LLM, l'objet/corps
générés remontent tels quels. Multi-tenant : l'action ne lit/écrit rien de
scopé société (texte libre uniquement) — testée quand même via un client
authentifié standard, comme les autres actions de ``CampagneViewSet``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.ai import AIResult, LLMProvider
from core.ai import registry

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


class _FakeLLMProvider(LLMProvider):
    key = 'fake_llm_xmkt34_view'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        return AIResult(
            ok=True, configured=True, provider=self.key,
            data={'text': 'OBJET: Promo été\nCORPS: -15% sur les kits solaires.'})


class GenererIaEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt34-view', 'XMKT34 View')
        self.user = make_user(self.co, 'xmkt34-view-user')

    def test_sans_cle_configured_false(self):
        api = auth(self.user)
        resp = api.post(
            '/api/django/compta/campagnes/generer-ia/',
            {'segment_label': 'Leads froids', 'offre': '-20%'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.data['configured'])
        self.assertEqual(resp.data['objet'], '')
        self.assertEqual(resp.data['corps'], '')

    def test_avec_cle_retourne_objet_et_corps_editables(self):
        registry.register_provider(_FakeLLMProvider)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_llm_xmkt34_view', None))
        api = auth(self.user)
        with override_settings(AI_PROVIDERS={'llm': 'fake_llm_xmkt34_view'}):
            resp = api.post(
                '/api/django/compta/campagnes/generer-ia/',
                {'segment_label': 'Leads froids', 'offre': '-20%',
                 'langue': 'fr'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['configured'])
        self.assertTrue(resp.data['ok'])
        self.assertEqual(resp.data['objet'], 'Promo été')
        self.assertEqual(resp.data['corps'], '-15% sur les kits solaires.')

    def test_requiert_authentification(self):
        api = APIClient()
        resp = api.post(
            '/api/django/compta/campagnes/generer-ia/',
            {'segment_label': 'S'}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_probe_disponible_sans_cle_false(self):
        api = auth(self.user)
        resp = api.get('/api/django/compta/campagnes/generer-ia-disponible/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.data['configured'])

    def test_probe_disponible_avec_cle_true(self):
        registry.register_provider(_FakeLLMProvider)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_llm_xmkt34_view', None))
        api = auth(self.user)
        with override_settings(AI_PROVIDERS={'llm': 'fake_llm_xmkt34_view'}):
            resp = api.get(
                '/api/django/compta/campagnes/generer-ia-disponible/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['configured'])
