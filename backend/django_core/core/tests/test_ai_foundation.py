"""Tests de la fondation IA (core.ai) — chemin NO-OP par défaut + câblage.

Prouve que :
  * sans réglage, chaque capacité renvoie le fournisseur NO-OP (aucun appel) ;
  * un faux fournisseur enregistré + sélectionné est bien utilisé ;
  * un fournisseur sélectionné mais NON configuré retombe sur le NO-OP ;
  * l'enregistrement valide la capacité et l'interface.
"""
from django.test import SimpleTestCase, override_settings

from core.ai import (
    AIResult,
    OCRProvider,
    STTProvider,
    get_provider,
    register_provider,
    available_providers,
    is_capability_configured,
)
from core.ai import registry


class NoOpDefaultTests(SimpleTestCase):
    def test_every_capability_defaults_to_noop(self):
        for cap in ('ocr', 'stt', 'vision_qa', 'llm'):
            provider = get_provider(cap)
            self.assertEqual(provider.key, 'noop')
            self.assertFalse(provider.is_configured())

    def test_noop_ocr_returns_unconfigured_result(self):
        res = get_provider('ocr').extract(
            content=b'x', mime_type='image/png', schema='cin')
        self.assertIsInstance(res, AIResult)
        self.assertFalse(res.configured)
        self.assertFalse(res.ok)
        self.assertEqual(res.provider, 'noop')

    def test_noop_stt_and_vision_and_llm(self):
        self.assertFalse(get_provider('stt').transcribe(
            content=b'', mime_type='audio/wav').configured)
        self.assertFalse(get_provider('vision_qa').inspect(
            content=b'', mime_type='image/jpeg', checklist=['a']).configured)
        self.assertFalse(get_provider('llm').complete(prompt='salut').configured)

    def test_unknown_capability_raises(self):
        with self.assertRaises(ValueError):
            get_provider('telepathy')

    def test_is_capability_configured_false_by_default(self):
        self.assertFalse(is_capability_configured('ocr'))


class FakeOCRProvider(OCRProvider):
    key = 'fake'
    label = 'Fake OCR'

    def is_configured(self):
        return True

    def extract(self, *, content, mime_type, schema, hint=None):
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'schema': schema, 'cin': 'AB12345'})


class FakeUnconfiguredOCRProvider(OCRProvider):
    key = 'fake_off'
    label = 'Fake OCR (non configuré)'

    def is_configured(self):
        return False  # clé absente → doit retomber sur NO-OP

    def extract(self, *, content, mime_type, schema, hint=None):  # pragma: no cover
        raise AssertionError("Ne doit jamais être appelé : non configuré")


class WiredProviderTests(SimpleTestCase):
    def setUp(self):
        register_provider(FakeOCRProvider)
        register_provider(FakeUnconfiguredOCRProvider)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        registry._REGISTRY['ocr'].pop('fake', None)
        registry._REGISTRY['ocr'].pop('fake_off', None)

    @override_settings(AI_PROVIDERS={'ocr': 'fake'})
    def test_selected_configured_provider_is_used(self):
        provider = get_provider('ocr')
        self.assertEqual(provider.key, 'fake')
        res = provider.extract(content=b'x', mime_type='image/png', schema='cin')
        self.assertTrue(res.ok)
        self.assertTrue(res.configured)
        self.assertEqual(res.data['cin'], 'AB12345')
        self.assertTrue(is_capability_configured('ocr'))

    @override_settings(AI_PROVIDERS={'ocr': 'fake_off'})
    def test_selected_but_unconfigured_falls_back_to_noop(self):
        provider = get_provider('ocr')
        self.assertEqual(provider.key, 'noop')
        self.assertFalse(is_capability_configured('ocr'))

    @override_settings(AI_PROVIDERS={'ocr': 'does_not_exist'})
    def test_unknown_key_falls_back_to_noop(self):
        self.assertEqual(get_provider('ocr').key, 'noop')

    def test_available_providers_lists_registered(self):
        self.assertIn('fake', available_providers('ocr')['ocr'])
        self.assertIn('noop', available_providers()['llm'])


class RegistrationValidationTests(SimpleTestCase):
    def test_register_rejects_unknown_capability(self):
        class Bad(OCRProvider):
            key = 'b'
            capability = 'nope'
        with self.assertRaises(ValueError):
            register_provider(Bad)

    def test_register_rejects_keyless(self):
        class Bad(OCRProvider):
            key = ''
        with self.assertRaises(ValueError):
            register_provider(Bad)

    def test_register_rejects_wrong_base(self):
        class Bad(STTProvider):
            key = 'b'
            capability = 'ocr'  # prétend OCR mais dérive de STT
        with self.assertRaises(TypeError):
            register_provider(Bad)
