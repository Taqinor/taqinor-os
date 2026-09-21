"""NTAI6 — Tests du registre de santé des capacités IA.

Couvre : capacité NON configurée (avec le motif), capacité configurée, les
mesures issues du journal NTAI1 (latence médiane, dernière erreur), l'absence
totale de secret dans la réponse, et la réserve au palier admin/directeur.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.ai import AIResult, LLMProvider, register_provider
from core.ai import registry
from core.ai.registry import capabilities_status

from ..models import LlmUsageRecord

User = get_user_model()

URL = '/api/django/ai-governance/capabilities/'


class FakeCapaciteLLM(LLMProvider):
    key = 'fake_ntai6'
    label = 'Faux LLM NTAI6'
    #: Secret FICTIF : sert à prouver qu'aucun attribut de fournisseur ne
    #: ressort dans la réponse.
    api_key = 'sk-secret-ntai6'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': 'ok'})


class NonConfigureLLM(LLMProvider):
    key = 'fake_ntai6_absent'
    label = 'LLM sans clé'

    def is_configured(self):
        return False

    def complete(self, *, prompt, system=None, max_tokens=512):
        return AIResult(ok=True, configured=True, provider=self.key, data={})


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai6CapabilitiesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntai6-co', 'NTAI6 Co')
        cls.autre = make_company('ntai6-autre', 'NTAI6 Autre')
        cls.admin = User.objects.create_user(
            username='ntai6-admin', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntai6-simple', password='x', company=cls.company,
            role_legacy='normal')

    def _register(self, cls_provider):
        register_provider(cls_provider)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop(cls_provider.key, None))

    @override_settings(AI_PROVIDERS={})
    def test_sans_fournisseur_toutes_les_capacites_sont_inactives(self):
        etat = {ligne['capacite']: ligne
                for ligne in capabilities_status(self.company)}
        self.assertEqual(set(etat), {'ocr', 'stt', 'vision_qa', 'llm'})
        for ligne in etat.values():
            self.assertFalse(ligne['configure'])
            self.assertIn('Aucun fournisseur', ligne['motif'])

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai6'})
    def test_capacite_configuree(self):
        self._register(FakeCapaciteLLM)
        etat = {ligne['capacite']: ligne
                for ligne in capabilities_status(self.company)}
        self.assertTrue(etat['llm']['configure'])
        self.assertEqual(etat['llm']['fournisseur_actif'], 'fake_ntai6')
        self.assertEqual(etat['llm']['motif'], '')

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai6_absent'})
    def test_fournisseur_selectionne_mais_sans_cle(self):
        self._register(NonConfigureLLM)
        etat = {ligne['capacite']: ligne
                for ligne in capabilities_status(self.company)}
        self.assertFalse(etat['llm']['configure'])
        self.assertIn('non configuré', etat['llm']['motif'])

    @override_settings(AI_PROVIDERS={'llm': 'fournisseur_fantome'})
    def test_fournisseur_inconnu_du_registre(self):
        etat = {ligne['capacite']: ligne
                for ligne in capabilities_status(self.company)}
        self.assertIn('inconnu du registre', etat['llm']['motif'])

    def test_mesures_issues_du_journal(self):
        for latence in (100, 200, 300):
            LlmUsageRecord.objects.create(
                company=self.company, capability='llm', provider='fake_ntai6',
                latency_ms=latence, success=True)
        LlmUsageRecord.objects.create(
            company=self.company, capability='llm', provider='fake_ntai6',
            latency_ms=900, success=False, message='quota fournisseur atteint')
        # Bruit d'une AUTRE société : ne doit jamais entrer dans la mesure.
        LlmUsageRecord.objects.create(
            company=self.autre, capability='llm', provider='fake_ntai6',
            latency_ms=9999, success=True)

        etat = {ligne['capacite']: ligne
                for ligne in capabilities_status(self.company)}
        self.assertEqual(etat['llm']['appels'], 4)
        self.assertEqual(etat['llm']['latence_p50_ms'], 200)
        self.assertIn('quota', etat['llm']['derniere_erreur'])

    def test_sans_mesure_les_champs_sont_nuls_pas_zero(self):
        etat = {ligne['capacite']: ligne
                for ligne in capabilities_status(self.company)}
        self.assertIsNone(etat['ocr']['appels'])
        self.assertIsNone(etat['ocr']['latence_p50_ms'])

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai6'})
    def test_endpoint_n_expose_aucun_secret(self):
        self._register(FakeCapaciteLLM)
        reponse = auth(self.admin).get(URL)
        self.assertEqual(reponse.status_code, 200)
        self.assertNotIn('sk-secret-ntai6', reponse.content.decode())
        self.assertNotIn('api_key', reponse.content.decode())

    def test_endpoint_interdit_au_palier_limite(self):
        self.assertEqual(auth(self.simple).get(URL).status_code, 403)
