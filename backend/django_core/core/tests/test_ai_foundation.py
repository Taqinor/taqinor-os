"""Tests de la fondation IA (core.ai) — chemin NO-OP par défaut + câblage.

Prouve que :
  * sans réglage, chaque capacité renvoie le fournisseur NO-OP (aucun appel) ;
  * un faux fournisseur enregistré + sélectionné est bien utilisé ;
  * un fournisseur sélectionné mais NON configuré retombe sur le NO-OP ;
  * l'enregistrement valide la capacité et l'interface.
"""
import copy
import json
from pathlib import Path
from unittest import mock

import httpx
from django.test import SimpleTestCase, override_settings

from core.ai import (
    AIResult,
    ClaudeVisionToitProvider,
    register_usage_sink,
    usage_context,
    OCRProvider,
    STTProvider,
    get_provider,
    register_provider,
    available_providers,
    is_capability_configured,
)
from core.ai import registry
from core.ai.usage import unregister_usage_sink


class NoOpDefaultTests(SimpleTestCase):
    def test_every_capability_defaults_to_noop(self):
        for cap in ('ocr', 'stt', 'vision_qa', 'llm', 'vision_toit'):
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


# ─────────────────────────────────────────────────────────────────────────────
# ACAL489 — capacité ``vision_toit`` (image de toit → pans PROPOSÉS), D-ACAL-33
# ─────────────────────────────────────────────────────────────────────────────

_FIXTURE = Path(__file__).parent / 'fixtures' / 'vision_toit_reponse_messages.json'
_AVEC_CLE = dict(AI_PROVIDERS={'vision_toit': 'claude'}, VISION_TOIT_CLE_API='cle-de-test',
                 VISION_TOIT_MODELE='modele-du-reglage', AI_TOKEN_COSTS={})


class VisionToitTests(SimpleTestCase):
    def setUp(self):
        self.reponse = json.loads(_FIXTURE.read_text(encoding='utf-8'))
        self.requetes, self.lignes = [], []

        def sink(**ligne):
            self.lignes.append(ligne)
        register_usage_sink(sink)
        self.addCleanup(unregister_usage_sink, sink)

    def _transport(self, statut=200, corps=None, exc=None):
        def handler(requete):
            self.requetes.append(json.loads(requete.content))
            if exc:
                raise exc
            return httpx.Response(statut, json=self.reponse if corps is None else corps)
        patcher = mock.patch.object(ClaudeVisionToitProvider, 'transport', httpx.MockTransport(handler))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _detecter(self):
        with usage_context(company_id=7, feature_key='calepinage.vision_toit'):
            provider = get_provider('vision_toit')
            self.assertEqual(provider.key, 'claude')
            return provider.detecter(content=b'\x89PNG-toit', mime_type='image/png')

    @override_settings(AI_PROVIDERS={'vision_toit': 'claude'}, VISION_TOIT_CLE_API='',
                       VISION_TOIT_MODELE='')
    def test_noop_par_defaut_et_sans_cle(self):
        with mock.patch('core.ai.fournisseurs_claude.httpx.Client') as client:
            provider = get_provider('vision_toit')
            self.assertEqual(provider.key, 'noop')
            self.assertFalse(provider.is_configured())
            self.assertFalse(is_capability_configured('vision_toit'))
            res = provider.detecter(content=b'x', mime_type='image/png')
        self.assertFalse(res.configured)
        client.assert_not_called()  # aucun appel réseau sans clé
        with override_settings(AI_PROVIDERS={}):
            self.assertEqual(get_provider('vision_toit').key, 'noop')

    @override_settings(**_AVEC_CLE)
    def test_avec_cle_et_transport_simule_pans_valides(self):
        self._transport()
        res = self._detecter()
        self.assertTrue(res.ok, res.error)
        self.assertEqual(res.data['pans'][0], {
            'sommets': [[0.12, 0.2], [0.55, 0.18], [0.57, 0.52], [0.13, 0.55]], 'confiance': 0.86})
        self.assertEqual(len(res.data['pans']), 2)
        corps = self.requetes[0]
        self.assertEqual(corps['model'], 'modele-du-reglage')  # réglage, jamais une constante
        # Seuls les octets et le type de l'image partent (aucun texte libre).
        self.assertEqual(len(corps['messages']), 1)
        self.assertEqual([b['type'] for b in corps['messages'][0]['content']], ['image'])
        self.assertEqual(corps['messages'][0]['content'][0]['source']['media_type'], 'image/png')

    @override_settings(**_AVEC_CLE)
    def test_sommet_hors_bornes_ou_pan_court_donne_ok_faux(self):
        for sommets, raison in (([[0.1, 0.1], [1.2, 0.1], [0.5, 0.9]], 'coordonnée hors de [0, 1]'),
                                ([[0.1, 0.1], [0.5, 0.9]], 'pan à moins de 3 sommets')):
            with self.subTest(raison=raison):
                corps = copy.deepcopy(self.reponse)
                corps['content'][0]['text'] = json.dumps({'pans': [{'sommets': sommets}]})
                self._transport(corps=corps)
                res = self._detecter()
                self.assertFalse(res.ok)
                self.assertEqual(res.error, raison)

    def test_valider_obstacles_acceptes_et_refuses_avec_raison(self):
        # ACAL1050 — la liste des types n'est PAS ici : un type libre non vide passe.
        from core.ai.fournisseurs_claude import valider_obstacles

        carre = [[0.1, 0.1], [0.3, 0.1], [0.3, 0.3], [0.1, 0.3]]
        obstacles, raison = valider_obstacles({'obstacles': [
            {'type': 'climatiseur', 'sommets': carre, 'confiance': 0.7},
            {'type': 'lanterneau', 'sommets': carre[:3]}]})
        self.assertEqual(raison, '')
        self.assertEqual([(o['type'], o['confiance']) for o in obstacles],
                         [('climatiseur', 0.7), ('lanterneau', None)])
        self.assertEqual(valider_obstacles({'pans': []}), ([], ''))  # sans clé : aucun
        for obstacle, attendu in (
                ({'type': 'x', 'sommets': [[0.1, 0.1], [1.2, 0.1], [0.5, 0.9]]}, 'coordonnée hors de [0, 1]'),
                ({'type': 'x', 'sommets': carre, 'confiance': 1.5}, 'confiance hors de [0, 1]'),
                ({'type': 'x', 'sommets': carre[:2]}, 'obstacle à moins de 3 sommets'),
                ({'type': '  ', 'sommets': carre}, "type d'obstacle manquant"),
                ({'type': 7, 'sommets': carre}, "type d'obstacle manquant")):
            with self.subTest(attendu=attendu):
                self.assertEqual(valider_obstacles({'obstacles': [obstacle]}), (None, attendu))

    @override_settings(**_AVEC_CLE)
    def test_obstacles_servis_avec_les_pans_quand_la_reponse_en_contient(self):
        carre = [[0.1, 0.1], [0.3, 0.1], [0.3, 0.3], [0.1, 0.3]]
        for obstacles, attendu in (([{'type': 'cheminee', 'sommets': carre, 'confiance': 0.4}], 1),
                                   ([{'type': 'cheminee', 'sommets': carre, 'confiance': 2}], None)):
            with self.subTest(attendu=attendu):
                corps = copy.deepcopy(self.reponse)
                charge = json.loads(corps['content'][0]['text'])
                charge['obstacles'] = obstacles
                corps['content'][0]['text'] = json.dumps(charge)
                self._transport(corps=corps)
                res = self._detecter()
                self.assertTrue(res.ok, res.error)
                self.assertEqual(len(res.data['pans']), 2)  # les pans restent servis
                self.assertEqual(len(res.data['obstacles']) if attendu else res.data.get('obstacles'), attendu)

    @override_settings(**_AVEC_CLE)
    def test_erreurs_http_delai_reponse_invalide_jamais_d_exception(self):
        cas = ((dict(statut=401), 'HTTP 401'), (dict(statut=529), 'HTTP 529'),
               (dict(exc=httpx.ReadTimeout('lent')), 'délai dépassé'),
               (dict(corps={'content': [{'type': 'text', 'text': 'pas de JSON'}]}), 'réponse invalide'))
        for kwargs, raison in cas:
            with self.subTest(raison=raison):
                self._transport(**kwargs)
                res = self._detecter()
                self.assertFalse(res.ok)
                self.assertEqual(res.error, raison)

    @override_settings(**_AVEC_CLE)
    def test_ligne_d_usage_ecrite_cout_inconnu_sans_tarif(self):
        self._transport()
        self._detecter()
        self.assertEqual(len(self.lignes), 1)
        ligne = self.lignes[0]
        self.assertEqual((ligne['capability'], ligne['provider'], ligne['company_id']),
                         ('vision_toit', 'claude', 7))
        self.assertEqual((ligne['prompt_tokens'], ligne['completion_tokens']), (1642, 118))
        self.assertFalse(ligne['cout_tarife'])
        self.assertTrue(ligne['success'])
