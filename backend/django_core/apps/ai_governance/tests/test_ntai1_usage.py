"""NTAI1 — Tests du journal d'usage & coût LLM par société.

Couvre : un appel LLM RÉEL écrit une ligne scopée société avec jetons + coût,
le chemin NO-OP n'écrit rien, aucune société connue = aucune ligne, le coût
n'est calculé que si un tarif est configuré, et l'agrégat ne fuit pas d'une
société à l'autre.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.ai import AIResult, LLMProvider, register_provider
from core.ai import registry
from core.ai.registry import get_provider
from core.ai.usage import (estimate_cost, record_usage, usage_context)

from ..models import LlmUsageRecord

User = get_user_model()

URL = '/api/django/ai-governance/usage/'


class FakeUsageLLM(LLMProvider):
    key = 'fake_ntai1'
    label = 'Faux LLM NTAI1'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        return AIResult(
            ok=True, configured=True, provider=self.key,
            data={'text': 'Réponse.',
                  'usage': {'prompt_tokens': 120, 'completion_tokens': 30}})


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai1UsageRecordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntai1-co', 'NTAI1 Co')
        cls.autre = make_company('ntai1-autre', 'NTAI1 Autre')
        cls.admin = User.objects.create_user(
            username='ntai1-admin', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntai1-simple', password='x', company=cls.company,
            role_legacy='normal')

    def _with_fake_llm(self):
        register_provider(FakeUsageLLM)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_ntai1', None))

    # --- Écriture -----------------------------------------------------------

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai1'},
                       AI_TOKEN_COSTS={'fake_ntai1': {'prompt': '1',
                                                      'completion': '2'}})
    def test_appel_reel_ecrit_une_ligne_scopee_avec_jetons_et_cout(self):
        self._with_fake_llm()
        with usage_context(company_id=self.company.id, feature_key='ai.test'):
            resultat = get_provider('llm').complete(prompt='Bonjour')

        self.assertTrue(resultat.ok)
        ligne = LlmUsageRecord.objects.get()
        self.assertEqual(ligne.company_id, self.company.id)
        self.assertEqual(ligne.capability, 'llm')
        self.assertEqual(ligne.provider, 'fake_ntai1')
        self.assertEqual(ligne.feature_key, 'ai.test')
        self.assertEqual(ligne.prompt_tokens, 120)
        self.assertEqual(ligne.completion_tokens, 30)
        self.assertTrue(ligne.success)
        self.assertTrue(ligne.cout_tarife)
        # 120 × 1/1000 + 30 × 2/1000 = 0,18 MAD — calculé, jamais inventé.
        # Stocké EXACTEMENT en micro-MAD (un arrondi au centime écraserait
        # toute la facture IA à zéro).
        self.assertEqual(ligne.cost_estimated_micro_mad, 180000)
        self.assertEqual(ligne.cost_estimated, Decimal('0.180000'))

    @override_settings(AI_PROVIDERS={}, AI_TOKEN_COSTS={})
    def test_chemin_noop_n_ecrit_aucune_ligne(self):
        with usage_context(company_id=self.company.id, feature_key='ai.test'):
            resultat = get_provider('llm').complete(prompt='Bonjour')
        self.assertFalse(resultat.configured)
        self.assertEqual(LlmUsageRecord.objects.count(), 0)

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai1'})
    def test_sans_contexte_societe_aucune_ligne(self):
        """On ne DEVINE jamais une société : hors contexte, rien n'est écrit."""
        self._with_fake_llm()
        get_provider('llm').complete(prompt='Bonjour')
        self.assertEqual(LlmUsageRecord.objects.count(), 0)

    @override_settings(AI_TOKEN_COSTS={})
    def test_sans_tarif_le_cout_est_inconnu_pas_nul(self):
        montant, tarife = estimate_cost('fake_ntai1', 1000, 1000)
        self.assertEqual(montant, Decimal('0'))
        self.assertFalse(tarife)

        record_usage(capability='llm', provider='fake_ntai1',
                     prompt_tokens=1000, completion_tokens=1000,
                     company_id=self.company.id, feature_key='ai.test')
        ligne = LlmUsageRecord.objects.get()
        self.assertFalse(ligne.cout_tarife)
        self.assertEqual(ligne.cost_estimated_micro_mad, 0)

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai1'})
    def test_erreur_du_fournisseur_journalisee_puis_relancee(self):
        class LLMEnPanne(LLMProvider):
            key = 'fake_ntai1_panne'

            def is_configured(self):
                return True

            def complete(self, *, prompt, system=None, max_tokens=512):
                raise RuntimeError('fournisseur indisponible')

        register_provider(LLMEnPanne)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_ntai1_panne', None))

        with override_settings(AI_PROVIDERS={'llm': 'fake_ntai1_panne'}):
            with usage_context(company_id=self.company.id):
                with self.assertRaises(RuntimeError):
                    get_provider('llm').complete(prompt='Bonjour')

        ligne = LlmUsageRecord.objects.get()
        self.assertFalse(ligne.success)
        self.assertIn('indisponible', ligne.message)

    @override_settings(AI_TOKEN_COSTS={'micro_ntai1': {'prompt': '1.8',
                                                       'completion': '0'}})
    def test_cout_d_un_appel_minuscule_n_est_pas_ecrase_a_zero(self):
        """Le piège que l'unité micro-MAD ferme : 100 appels à 0,0018 MAD
        valent 0,18 MAD — pas 0,00 (ce que donnerait un arrondi au centime)."""
        for _ in range(100):
            record_usage(capability='llm', provider='micro_ntai1',
                         prompt_tokens=1, completion_tokens=0,
                         company_id=self.company.id)
        total = sum(ligne.cost_estimated_micro_mad
                    for ligne in LlmUsageRecord.objects.all())
        self.assertEqual(total, 180000)

    def test_aucun_prompt_n_est_stocke(self):
        """Le journal ne porte QUE des métriques — jamais de contenu."""
        champs = {f.name for f in LlmUsageRecord._meta.get_fields()}
        for interdit in ('prompt', 'reponse', 'contenu', 'texte'):
            self.assertNotIn(interdit, champs)

    # --- Endpoint d'agrégats ------------------------------------------------

    def _semer(self, company, feature, appels=1, tarife=True):
        for _ in range(appels):
            LlmUsageRecord.objects.create(
                company=company, capability='llm', provider='fake_ntai1',
                feature_key=feature, prompt_tokens=10, completion_tokens=5,
                cost_estimated_micro_mad=500000 if tarife else 0,
                cout_tarife=tarife, latency_ms=42, success=True)

    def test_endpoint_agrege_sans_fuite_cross_tenant(self):
        self._semer(self.company, 'ai.rediger', appels=2)
        self._semer(self.autre, 'ai.rediger', appels=5)

        reponse = auth(self.admin).get(URL)
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()
        self.assertEqual(corps['totaux']['appels'], 2)
        self.assertEqual(Decimal(corps['totaux']['cout_mad']), Decimal('1'))
        self.assertTrue(corps['cout_complet'])
        self.assertEqual(len(corps['par_feature']), 1)
        self.assertEqual(corps['par_feature'][0]['feature'], 'ai.rediger')
        self.assertEqual(corps['par_jour'][0]['appels'], 2)

    def test_endpoint_signale_un_cout_incomplet(self):
        self._semer(self.company, 'ai.rediger', appels=1, tarife=True)
        self._semer(self.company, 'ai.rediger', appels=1, tarife=False)

        corps = auth(self.admin).get(URL).json()
        self.assertFalse(corps['cout_complet'])
        self.assertEqual(corps['totaux']['appels_sans_tarif'], 1)

    def test_endpoint_filtre_par_feature(self):
        self._semer(self.company, 'ai.rediger', appels=2)
        self._semer(self.company, 'ai.resume', appels=3)

        corps = auth(self.admin).get(URL, {'feature': 'ai.resume'}).json()
        self.assertEqual(corps['totaux']['appels'], 3)

    def test_endpoint_refuse_une_date_invalide(self):
        reponse = auth(self.admin).get(URL, {'since': 'hier'})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('since', reponse.json()['detail'])

    def test_endpoint_interdit_au_palier_limite(self):
        reponse = auth(self.simple).get(URL)
        self.assertEqual(reponse.status_code, 403)
