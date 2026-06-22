"""Tests des services IA (FG355-FG359) — NO-OP par défaut + chemin câblé.

Couvre :
  * FG355 — extract_document (CIN/contrat) : NO-OP sans clé, faux fournisseur OK.
  * FG356 — match_ocr_lines : appariement référence + similarité de libellé.
  * FG357 — transcribe_audio : NO-OP sans clé, faux STT OK.
  * FG358 — inspect_photo : NO-OP sans clé, faux vision OK + checklist FR.
  * FG359 — recommend_next_action : heuristique déterministe ; *_ai NO-OP-safe.
"""
from django.test import SimpleTestCase, override_settings

from core.ai import (
    AIResult,
    DEFAULT_PHOTO_QA_CHECKLIST,
    OCRProvider,
    STTProvider,
    VisionQAProvider,
    LLMProvider,
    extract_document,
    inspect_photo,
    match_ocr_lines,
    recommend_next_action,
    recommend_next_action_ai,
    register_provider,
    transcribe_audio,
)
from core.ai import registry
from core.ai.schemas import available_schemas, get_schema


# --- FG355 -------------------------------------------------------------------

class FakeCINProvider(OCRProvider):
    key = 'fake_cin'

    def is_configured(self):
        return True

    def extract(self, *, content, mime_type, schema, hint=None):
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'numero_cin': 'AB12345', 'nom': 'KASRI',
                              'prenom': 'Reda', 'schema': schema})


class FG355OCRDocumentTests(SimpleTestCase):
    def test_schemas_exist(self):
        self.assertIn('cin', available_schemas())
        self.assertIn('contrat', available_schemas())
        self.assertIn('numero_cin', get_schema('cin').required_keys())

    def test_extract_noop_without_key(self):
        res = extract_document(content=b'x', mime_type='image/png', schema='cin')
        self.assertFalse(res.configured)
        self.assertFalse(res.ok)

    def test_extract_unknown_schema_raises(self):
        with self.assertRaises(KeyError):
            extract_document(content=b'x', mime_type='image/png', schema='nope')

    def test_extract_with_fake_provider(self):
        register_provider(FakeCINProvider)
        self.addCleanup(lambda: registry._REGISTRY['ocr'].pop('fake_cin', None))
        with override_settings(AI_PROVIDERS={'ocr': 'fake_cin'}):
            res = extract_document(content=b'x', mime_type='image/png',
                                   schema='cin')
        self.assertTrue(res.ok)
        self.assertEqual(res.data['numero_cin'], 'AB12345')


# --- FG356 -------------------------------------------------------------------

class FG356MatchOcrLinesTests(SimpleTestCase):
    catalogue = [
        {'id': 1, 'designation': 'Panneau solaire 550W mono', 'reference': 'PV-550'},
        {'id': 2, 'designation': 'Onduleur hybride 5kW', 'reference': 'OND-5K'},
        {'id': 3, 'designation': 'Batterie lithium 5kWh', 'reference': 'BAT-5'},
    ]

    def test_exact_reference_match(self):
        lines = [{'designation': 'panneau', 'reference': 'PV-550', 'quantite': 10}]
        out = match_ocr_lines(lines, self.catalogue)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].matched)
        self.assertEqual(out[0].catalogue_id, 1)
        self.assertEqual(out[0].score, 1.0)
        self.assertEqual(out[0].quantite, 10.0)

    def test_label_similarity_match(self):
        lines = [{'designation': 'Onduleur hybride 5 kW', 'quantite': 2}]
        out = match_ocr_lines(lines, self.catalogue)
        self.assertTrue(out[0].matched)
        self.assertEqual(out[0].catalogue_id, 2)
        self.assertGreaterEqual(out[0].score, 0.6)

    def test_no_match_below_threshold(self):
        lines = [{'designation': 'Vis inox M8', 'quantite': 100}]
        out = match_ocr_lines(lines, self.catalogue, threshold=0.8)
        self.assertFalse(out[0].matched)
        self.assertIsNone(out[0].catalogue_id)

    def test_accent_and_case_insensitive(self):
        lines = [{'designation': 'BATTERIE LÍTHIUM 5kwh', 'quantite': 1}]
        out = match_ocr_lines(lines, self.catalogue)
        self.assertEqual(out[0].catalogue_id, 3)

    def test_empty_lines(self):
        self.assertEqual(match_ocr_lines([], self.catalogue), [])

    def test_bad_quantity_coerced_to_zero(self):
        lines = [{'designation': 'Panneau', 'reference': 'PV-550', 'quantite': 'x'}]
        out = match_ocr_lines(lines, self.catalogue)
        self.assertEqual(out[0].quantite, 0.0)


# --- FG357 -------------------------------------------------------------------

class FakeSTTProvider(STTProvider):
    key = 'fake_stt'

    def is_configured(self):
        return True

    def transcribe(self, *, content, mime_type, language='fr'):
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': 'Compteur posé, RAS.', 'language': language})


class FG357TranscribeTests(SimpleTestCase):
    def test_noop_without_key(self):
        res = transcribe_audio(content=b'', mime_type='audio/wav')
        self.assertFalse(res.configured)

    def test_with_fake_provider(self):
        register_provider(FakeSTTProvider)
        self.addCleanup(lambda: registry._REGISTRY['stt'].pop('fake_stt', None))
        with override_settings(AI_PROVIDERS={'stt': 'fake_stt'}):
            res = transcribe_audio(content=b'\x00', mime_type='audio/wav')
        self.assertTrue(res.ok)
        self.assertEqual(res.data['text'], 'Compteur posé, RAS.')


# --- FG358 -------------------------------------------------------------------

class FakeVisionProvider(VisionQAProvider):
    key = 'fake_vqa'

    def is_configured(self):
        return True

    def inspect(self, *, content, mime_type, checklist):
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'score': 82, 'flags': ['câblage à vérifier'],
                              'checked': len(checklist)})


class FG358InspectPhotoTests(SimpleTestCase):
    def test_default_checklist_is_french(self):
        self.assertTrue(DEFAULT_PHOTO_QA_CHECKLIST)
        self.assertIn('Panneaux alignés et propres', DEFAULT_PHOTO_QA_CHECKLIST)

    def test_noop_without_key(self):
        res = inspect_photo(content=b'', mime_type='image/jpeg')
        self.assertFalse(res.configured)

    def test_with_fake_provider(self):
        register_provider(FakeVisionProvider)
        self.addCleanup(lambda: registry._REGISTRY['vision_qa'].pop('fake_vqa', None))
        with override_settings(AI_PROVIDERS={'vision_qa': 'fake_vqa'}):
            res = inspect_photo(content=b'\xff', mime_type='image/jpeg')
        self.assertTrue(res.ok)
        self.assertEqual(res.data['score'], 82)
        self.assertEqual(res.data['checked'], len(DEFAULT_PHOTO_QA_CHECKLIST))


# --- FG359 -------------------------------------------------------------------

class FakeLLMProvider(LLMProvider):
    key = 'fake_llm'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': 'Relancer car le devis traîne.'})


class FG359NextBestActionTests(SimpleTestCase):
    def test_unpaid_invoice_is_highest(self):
        a = recommend_next_action({'kind': 'facture', 'invoice_unpaid': True})
        self.assertEqual(a.action, 'relancer')
        self.assertEqual(a.priority, 90)

    def test_work_done_to_facturer(self):
        a = recommend_next_action({'kind': 'chantier', 'work_done': True})
        self.assertEqual(a.action, 'facturer')

    def test_quote_accepted_to_planifier(self):
        a = recommend_next_action({'kind': 'lead', 'quote_accepted': True})
        self.assertEqual(a.action, 'planifier')

    def test_open_quote_stale_to_relancer(self):
        a = recommend_next_action(
            {'kind': 'lead', 'has_open_quote': True, 'days_since_contact': 5})
        self.assertEqual(a.action, 'relancer')

    def test_qualified_lead_to_devis(self):
        a = recommend_next_action({'kind': 'lead', 'qualified': True})
        self.assertEqual(a.action, 'envoyer_devis')

    def test_unqualified_lead_to_qualifier(self):
        a = recommend_next_action({'kind': 'lead'})
        self.assertEqual(a.action, 'qualifier')

    def test_nothing_urgent(self):
        a = recommend_next_action({'kind': 'chantier'})
        self.assertEqual(a.action, 'rien')
        self.assertEqual(a.source, 'heuristique')

    def test_ai_noop_falls_back_to_heuristic(self):
        a = recommend_next_action_ai({'kind': 'facture', 'invoice_unpaid': True})
        self.assertEqual(a.action, 'relancer')
        self.assertEqual(a.source, 'heuristique')

    def test_ai_enriches_reason_when_llm_present(self):
        register_provider(FakeLLMProvider)
        self.addCleanup(lambda: registry._REGISTRY['llm'].pop('fake_llm', None))
        facts = {'kind': 'lead', 'has_open_quote': True, 'days_since_contact': 5}
        with override_settings(AI_PROVIDERS={'llm': 'fake_llm'}):
            a = recommend_next_action_ai(facts)
        # L'action machine reste l'heuristique ; seule la raison est enrichie.
        self.assertEqual(a.action, 'relancer')
        self.assertEqual(a.reason, 'Relancer car le devis traîne.')
        self.assertEqual(a.source, 'fake_llm')
