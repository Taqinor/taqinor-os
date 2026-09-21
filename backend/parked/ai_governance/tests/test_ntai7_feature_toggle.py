"""NTAI7 — Tests du consentement IA par feature (opt-out société).

Couvre : le DÉFAUT actif (aucune ligne = comportement inchangé), la coupure
d'une feature précise qui n'affecte QUE la société concernée, la dégradation
propre côté endpoint (503 + message FR, jamais une 500), et le CRUD
admin-only.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.ai import AIResult, LLMProvider, register_provider
from core.ai import registry
from core.ai.services import feature_enabled

from ..models import AiFeatureToggle

User = get_user_model()

URL = '/api/django/ai-governance/feature-toggles/'
DESCRIPTION_URL = '/api/django/ai/description-produit/'


class FakeToggleLLM(LLMProvider):
    key = 'fake_ntai7'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': 'Description.\nCOURT : Description.'})


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai7FeatureToggleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.stock.models import Produit

        cls.company = make_company('ntai7-co', 'NTAI7 Co')
        cls.autre = make_company('ntai7-autre', 'NTAI7 Autre')
        cls.admin = User.objects.create_user(
            username='ntai7-admin', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntai7-simple', password='x', company=cls.company,
            role_legacy='normal')
        cls.admin_autre = User.objects.create_user(
            username='ntai7-admin-autre', password='x', company=cls.autre,
            role_legacy='admin')
        cls.produit = Produit.objects.create(
            company=cls.company, nom='Onduleur Deye 8 kW', marque='Deye',
            prix_vente='10000')
        cls.produit_autre = Produit.objects.create(
            company=cls.autre, nom='Onduleur Deye 8 kW', marque='Deye',
            prix_vente='10000')

    def _with_fake_llm(self):
        register_provider(FakeToggleLLM)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_ntai7', None))

    # --- Résolution ---------------------------------------------------------

    def test_defaut_actif_sans_reglage(self):
        self.assertTrue(feature_enabled(self.company, 'ai.rediger'))

    def test_ligne_active_reste_active(self):
        AiFeatureToggle.objects.create(
            company=self.company, feature_key='ai.rediger', actif=True)
        self.assertTrue(feature_enabled(self.company, 'ai.rediger'))

    def test_coupure_ciblee(self):
        AiFeatureToggle.objects.create(
            company=self.company, feature_key='ai.rediger', actif=False)
        self.assertFalse(feature_enabled(self.company, 'ai.rediger'))
        # Une AUTRE feature de la même société reste active.
        self.assertTrue(feature_enabled(self.company, 'ai.description_produit'))
        # Et la même feature chez une AUTRE société aussi.
        self.assertTrue(feature_enabled(self.autre, 'ai.rediger'))

    def test_societe_absente_reste_active(self):
        self.assertTrue(feature_enabled(None, 'ai.rediger'))

    # --- Effet sur un copilote ---------------------------------------------

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai7'})
    def test_copilote_coupe_degrade_proprement(self):
        self._with_fake_llm()
        AiFeatureToggle.objects.create(
            company=self.company, feature_key='ai.description_produit',
            actif=False, motif='Pas d\'IA sur le catalogue.')

        reponse = auth(self.admin).post(
            DESCRIPTION_URL, {'produit_id': self.produit.id}, format='json')
        self.assertEqual(reponse.status_code, 503)
        self.assertIn('désactivée', reponse.json()['detail'])

        # La MÊME feature reste servie à l'autre société.
        reponse_autre = auth(self.admin_autre).post(
            DESCRIPTION_URL, {'produit_id': self.produit_autre.id},
            format='json')
        self.assertEqual(reponse_autre.status_code, 200)

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai7'})
    def test_sans_reglage_le_copilote_repond(self):
        self._with_fake_llm()
        reponse = auth(self.admin).post(
            DESCRIPTION_URL, {'produit_id': self.produit.id}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)

    # --- CRUD ---------------------------------------------------------------

    def test_crud_admin_seulement(self):
        self.assertEqual(auth(self.simple).get(URL).status_code, 403)

    def test_creation_force_la_societe(self):
        reponse = auth(self.admin).post(
            URL, {'feature_key': 'ai.rediger', 'actif': False,
                  'company': self.autre.id}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        self.assertEqual(AiFeatureToggle.objects.get().company_id,
                         self.company.id)

    def test_doublon_refuse(self):
        AiFeatureToggle.objects.create(
            company=self.company, feature_key='ai.rediger', actif=False)
        reponse = auth(self.admin).post(
            URL, {'feature_key': 'ai.rediger', 'actif': True}, format='json')
        self.assertEqual(reponse.status_code, 400)

    def test_liste_scopee_societe(self):
        AiFeatureToggle.objects.create(
            company=self.autre, feature_key='ai.rediger', actif=False)
        corps = auth(self.admin).get(URL).json()
        resultats = corps['results'] if isinstance(corps, dict) else corps
        self.assertEqual(len(resultats), 0)
