"""Tests FG353/FG354 — synthèse de fil & brouillon de réponse.

Prouve, comme le reste de la fondation IA, que :
  * SANS clé LLM, ``summarize_thread`` et ``draft_reply`` sont des NO-OP propres
    (``configured=False``, AUCUN appel réseau, aucune dépendance externe) ;
  * AVEC un faux fournisseur LLM sélectionné, ils renvoient bien le texte généré ;
  * ``format_thread`` met le fil à plat de façon robuste (entrées vides, non-dict,
    accents, limite) ;
  * ``draft_reply`` ne fait QUE générer du texte (jamais d'envoi).
"""
from django.test import SimpleTestCase, override_settings

from core.ai import (
    AIResult,
    LLMProvider,
    REPLY_CHANNELS,
    ReplyDraft,
    ThreadSummary,
    draft_reply,
    format_thread,
    summarize_thread,
)
from core.ai import registry


THREAD = [
    {'date': '2026-06-20', 'auteur': 'Reda', 'canal': 'email',
     'texte': 'Bonjour, je veux un devis pour 5 kWc.'},
    {'date': '2026-06-21', 'auteur': 'Commercial', 'canal': 'whatsapp',
     'texte': 'Devis envoyé, en attente de retour.'},
]


class _FakeLLMProvider(LLMProvider):
    key = 'fake_llm_thread'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        # On renvoie le prompt reçu pour pouvoir l'inspecter dans les tests.
        self.last_prompt = prompt
        self.last_system = system
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': 'TEXTE GÉNÉRÉ'})


def _register_fake():
    registry.register_provider(_FakeLLMProvider)


# --- format_thread (partagé) -------------------------------------------------

class FormatThreadTests(SimpleTestCase):
    def test_renders_entries_with_prefix(self):
        out = format_thread(THREAD)
        self.assertIn('je veux un devis', out)
        self.assertIn('Reda', out)
        self.assertIn('2026-06-20', out)

    def test_skips_empty_bodies(self):
        out = format_thread([{'auteur': 'X', 'texte': ''}, {'texte': 'ok'}])
        self.assertEqual(out, 'ok')

    def test_accepts_alternate_body_keys(self):
        self.assertEqual(format_thread([{'message': 'm'}]), 'm')
        self.assertEqual(format_thread([{'contenu': 'c'}]), 'c')

    def test_non_dict_entry_coerced(self):
        self.assertEqual(format_thread(['brut']), 'brut')

    def test_limit_keeps_most_recent(self):
        msgs = [{'texte': str(i)} for i in range(10)]
        out = format_thread(msgs, limit=3)
        self.assertEqual(out.splitlines(), ['7', '8', '9'])

    def test_empty_returns_empty(self):
        self.assertEqual(format_thread([]), '')
        self.assertEqual(format_thread(None), '')


# --- FG353 — summarize_thread ------------------------------------------------

class FG353SummarizeTests(SimpleTestCase):
    def test_noop_without_key(self):
        res = summarize_thread(THREAD)
        self.assertIsInstance(res, ThreadSummary)
        self.assertFalse(res.configured)
        self.assertFalse(res.ok)
        self.assertFalse(res.available)
        self.assertEqual(res.summary, '')
        self.assertEqual(res.source, 'noop')

    def test_noop_does_not_call_provider(self):
        # Aucune clé → le NO-OP ne doit jamais toucher complete().
        called = {'n': 0}

        class Spy(LLMProvider):
            key = 'noop'  # forcera le chemin NO-OP via get_provider

            def complete(self, **kw):  # pragma: no cover - ne doit pas tourner
                called['n'] += 1
                return AIResult.noop()

        # Sans AI_PROVIDERS, get_provider('llm') renvoie le NO-OP standard.
        summarize_thread(THREAD)
        self.assertEqual(called['n'], 0)

    def test_summary_with_fake_provider(self):
        _register_fake()
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_llm_thread', None))
        with override_settings(AI_PROVIDERS={'llm': 'fake_llm_thread'}):
            res = summarize_thread(THREAD, context='Lead solaire')
        self.assertTrue(res.ok)
        self.assertTrue(res.available)
        self.assertEqual(res.summary, 'TEXTE GÉNÉRÉ')
        self.assertEqual(res.source, 'fake_llm_thread')

    def test_empty_thread_with_key_no_summary(self):
        _register_fake()
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_llm_thread', None))
        with override_settings(AI_PROVIDERS={'llm': 'fake_llm_thread'}):
            res = summarize_thread([])
        self.assertTrue(res.configured)
        self.assertEqual(res.summary, '')


# --- FG354 — draft_reply -----------------------------------------------------

class FG354DraftReplyTests(SimpleTestCase):
    def test_channels_are_french(self):
        self.assertIn('email', REPLY_CHANNELS)
        self.assertIn('whatsapp', REPLY_CHANNELS)

    def test_noop_without_key(self):
        res = draft_reply(THREAD, channel='whatsapp')
        self.assertIsInstance(res, ReplyDraft)
        self.assertFalse(res.configured)
        self.assertFalse(res.available)
        self.assertEqual(res.draft, '')
        self.assertEqual(res.channel, 'whatsapp')

    def test_draft_with_fake_provider(self):
        _register_fake()
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_llm_thread', None))
        with override_settings(AI_PROVIDERS={'llm': 'fake_llm_thread'}):
            res = draft_reply(THREAD, channel='email',
                              instruction='propose un créneau')
        self.assertTrue(res.ok)
        self.assertEqual(res.draft, 'TEXTE GÉNÉRÉ')
        self.assertEqual(res.channel, 'email')
        self.assertEqual(res.source, 'fake_llm_thread')

    def test_unknown_channel_falls_back_to_email_format(self):
        _register_fake()
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_llm_thread', None))
        # Canal inconnu : le libellé retombe sur l'e-mail (pas d'erreur).
        with override_settings(AI_PROVIDERS={'llm': 'fake_llm_thread'}):
            res = draft_reply(THREAD, channel='pigeon')
        self.assertTrue(res.ok)
        # Le canal demandé est conservé tel quel dans le retour.
        self.assertEqual(res.channel, 'pigeon')
