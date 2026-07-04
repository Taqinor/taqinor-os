"""XPLT17 — champ IA (valeur générée par LLM, à la demande, NO-OP-safe)."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.customfields.models import CustomFieldDef
from apps.customfields.services import (
    FORBIDDEN_PROMPT_PLACEHOLDERS, generate_ia_value, render_prompt,
    validate_ia_prompt,
)
from apps.parametres.models import SettingsAuditLog
from authentication.models import Company
from core.ai import AIResult, LLMProvider, register_provider
from core.ai import registry as ai_registry

User = get_user_model()


class FakeLLMProvider(LLMProvider):
    key = 'fake_llm_xplt17'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': 'Résumé généré : besoin urgent.'})


class CF17Base(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='cf17-co', defaults={'nom': 'CF17 Co'})[0]
        self.admin = User.objects.create_user(
            username='cf17_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')


class TestValidateIAPrompt(TestCase):
    def test_clean_prompt_accepted(self):
        self.assertEqual(
            validate_ia_prompt('Résume le besoin de {nom} en une phrase.'), [])

    def test_forbidden_placeholder_rejected(self):
        for forbidden in FORBIDDEN_PROMPT_PLACEHOLDERS:
            errors = validate_ia_prompt(f'Utilise {{{forbidden}}} ici.')
            self.assertTrue(errors, forbidden)


class TestRenderPrompt(TestCase):
    def test_substitutes_known_placeholders(self):
        out = render_prompt('Client : {nom}, budget {budget}.',
                            {'nom': 'X', 'budget': 50000})
        self.assertEqual(out, 'Client : X, budget 50000.')

    def test_missing_placeholder_left_as_is(self):
        out = render_prompt('Client : {nom}.', {})
        self.assertEqual(out, 'Client : {nom}.')


class TestDefinitionValidation(CF17Base):
    def test_ia_field_with_forbidden_placeholder_rejected(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'resume', 'libelle': 'Résumé',
            'type': 'ia', 'ia_prompt': 'Voici le {prix_achat} du client.',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('ia_prompt', resp.data)

    def test_ia_field_clean_prompt_accepted(self):
        resp = self.api.post('/api/django/custom-fields/definitions/', {
            'module': 'lead', 'code': 'resume', 'libelle': 'Résumé',
            'type': 'ia', 'ia_prompt': 'Résume le besoin de {nom}.',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


class TestGenerateIAValueNoop(TestCase):
    def test_no_provider_configured_returns_degraded(self):
        field_def = CustomFieldDef(
            module='lead', code='resume', libelle='Résumé', type='ia',
            ia_prompt='Résume {nom}.')
        result = generate_ia_value(field_def=field_def, context={'nom': 'X'})
        self.assertFalse(result.configured)
        self.assertFalse(result.ok)
        self.assertFalse(result.available)
        self.assertTrue(result.error)

    def test_forbidden_prompt_never_calls_provider(self):
        field_def = CustomFieldDef(
            module='lead', code='resume', libelle='Résumé', type='ia',
            ia_prompt='Le {prix_achat} est {nom}.')
        result = generate_ia_value(field_def=field_def, context={'nom': 'X'})
        self.assertFalse(result.configured)
        self.assertFalse(result.available)


class TestGenerateIAValueWithProvider(TestCase):
    def setUp(self):
        register_provider(FakeLLMProvider)
        self.addCleanup(
            lambda: ai_registry._REGISTRY['llm'].pop('fake_llm_xplt17', None))

    def test_generates_with_configured_provider(self):
        field_def = CustomFieldDef(
            module='lead', code='resume', libelle='Résumé', type='ia',
            ia_prompt='Résume le besoin de {nom}.')
        with override_settings(AI_PROVIDERS={'llm': 'fake_llm_xplt17'}):
            result = generate_ia_value(
                field_def=field_def, context={'nom': 'Client X'})
        self.assertTrue(result.available)
        self.assertEqual(result.text, 'Résumé généré : besoin urgent.')
        self.assertEqual(result.source, 'fake_llm_xplt17')


class TestGenerateEndpoint(CF17Base):
    def test_endpoint_noop_without_provider(self):
        lead = Lead.objects.create(company=self.company, nom='Lead X')
        field_def = CustomFieldDef.objects.create(
            company=self.company, module='lead', code='resume',
            libelle='Résumé', type='ia', ia_prompt='Résume {nom}.')
        resp = self.api.post(
            f'/api/django/custom-fields/definitions/{field_def.id}/generer/',
            {'record_id': lead.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['configured'])
        lead.refresh_from_db()
        self.assertNotIn('resume', lead.custom_data or {})

    def test_endpoint_writes_and_audits_with_provider(self):
        register_provider(FakeLLMProvider)
        self.addCleanup(
            lambda: ai_registry._REGISTRY['llm'].pop('fake_llm_xplt17', None))
        lead = Lead.objects.create(company=self.company, nom='Lead X')
        field_def = CustomFieldDef.objects.create(
            company=self.company, module='lead', code='resume',
            libelle='Résumé', type='ia', ia_prompt='Résume {nom}.')
        with override_settings(AI_PROVIDERS={'llm': 'fake_llm_xplt17'}):
            resp = self.api.post(
                f'/api/django/custom-fields/definitions/{field_def.id}/generer/',
                {'record_id': lead.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['configured'])
        self.assertTrue(resp.data['ok'])
        lead.refresh_from_db()
        self.assertEqual(lead.custom_data['resume'],
                         'Résumé généré : besoin urgent.')
        self.assertTrue(SettingsAuditLog.objects.filter(
            company=self.company, section='champs',
            field='lead.resume').exists())

    def test_endpoint_rejects_non_ia_field(self):
        lead = Lead.objects.create(company=self.company, nom='Lead X')
        field_def = CustomFieldDef.objects.create(
            company=self.company, module='lead', code='budget',
            libelle='Budget', type='number')
        resp = self.api.post(
            f'/api/django/custom-fields/definitions/{field_def.id}/generer/',
            {'record_id': lead.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_endpoint_requires_record_id(self):
        field_def = CustomFieldDef.objects.create(
            company=self.company, module='lead', code='resume',
            libelle='Résumé', type='ia', ia_prompt='Résume {nom}.')
        resp = self.api.post(
            f'/api/django/custom-fields/definitions/{field_def.id}/generer/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_endpoint_cross_tenant_record_404(self):
        other = Company.objects.create(slug='cf17-other', nom='Autre')
        other_lead = Lead.objects.create(company=other, nom='Lead autre')
        field_def = CustomFieldDef.objects.create(
            company=self.company, module='lead', code='resume',
            libelle='Résumé', type='ia', ia_prompt='Résume {nom}.')
        resp = self.api.post(
            f'/api/django/custom-fields/definitions/{field_def.id}/generer/',
            {'record_id': other_lead.id}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)
