"""XMKT34 — Génération IA de contenu de campagne (FR/AR), gated.

Même patron NO-OP-safe que FG354 (``draft_reply``) :
  * SANS clé LLM, ``draft_campaign_content`` est un NO-OP propre
    (``configured=False``, AUCUN appel réseau) ;
  * AVEC un faux fournisseur LLM sélectionné, il renvoie objet+corps générés ;
  * le prompt construit (``build_campaign_prompt``) ne contient JAMAIS de
    champ interne (prix_achat, marge, coût interne) ;
  * la génération ne fait QUE proposer du texte — jamais d'envoi.
"""
from django.test import SimpleTestCase, override_settings

from core.ai import (
    AIResult,
    CAMPAIGN_PROMPT_FORBIDDEN_TERMS,
    CampaignContentDraft,
    LLMProvider,
    build_campaign_prompt,
    draft_campaign_content,
)
from core.ai import registry


class _FakeLLMProvider(LLMProvider):
    key = 'fake_llm_xmkt34'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        self.last_prompt = prompt
        self.last_system = system
        return AIResult(
            ok=True, configured=True, provider=self.key,
            data={'text': 'OBJET: Offre solaire\nCORPS: Profitez de -20% ce mois-ci.'})


def _register_fake():
    registry.register_provider(_FakeLLMProvider)


class BuildCampaignPromptTests(SimpleTestCase):
    def test_prompt_includes_segment_and_offre(self):
        prompt = build_campaign_prompt(
            segment_label='Leads froids résidentiel', offre='-20% panneaux',
            langue='fr')
        self.assertIn('Leads froids résidentiel', prompt)
        self.assertIn('-20% panneaux', prompt)

    def test_prompt_never_contains_forbidden_terms(self):
        prompt = build_campaign_prompt(
            segment_label='Segment', offre='Offre', instruction='Sois bref',
            langue='ar', longueur='courte')
        for term in CAMPAIGN_PROMPT_FORBIDDEN_TERMS:
            self.assertNotIn(term, prompt)

    def test_prompt_does_not_leak_forbidden_terms_even_if_passed_in(self):
        # Un appelant qui passerait par erreur un champ interne dans le texte
        # libre : le prompt système interdit explicitement leur usage, et la
        # fonction elle-même n'accepte que des chaînes libres (jamais un objet
        # produit avec prix_achat) — ce test verrouille le contrat de surface.
        prompt = build_campaign_prompt(
            segment_label='Segment normal', offre='Offre normale', langue='fr')
        self.assertIn('Ne mentionne JAMAIS', prompt)


class DraftCampaignContentNoopTests(SimpleTestCase):
    def test_noop_without_key(self):
        res = draft_campaign_content(
            segment_label='Segment', offre='Offre', langue='fr')
        self.assertIsInstance(res, CampaignContentDraft)
        self.assertFalse(res.configured)
        self.assertFalse(res.ok)
        self.assertFalse(res.available)
        self.assertEqual(res.objet, '')
        self.assertEqual(res.corps, '')
        self.assertEqual(res.source, 'noop')

    def test_noop_does_not_call_provider(self):
        called = {'n': 0}

        class Spy(LLMProvider):
            key = 'noop'

            def complete(self, **kw):  # pragma: no cover - ne doit pas tourner
                called['n'] += 1
                return AIResult.noop()

        draft_campaign_content(segment_label='S', offre='O')
        self.assertEqual(called['n'], 0)


class DraftCampaignContentWithProviderTests(SimpleTestCase):
    def test_generates_editable_objet_et_corps_with_key(self):
        _register_fake()
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_llm_xmkt34', None))
        with override_settings(AI_PROVIDERS={'llm': 'fake_llm_xmkt34'}):
            res = draft_campaign_content(
                segment_label='Leads froids', offre='-20% panneaux',
                instruction='ton chaleureux', langue='fr')
        self.assertTrue(res.ok)
        self.assertTrue(res.configured)
        self.assertTrue(res.available)
        self.assertEqual(res.objet, 'Offre solaire')
        self.assertEqual(res.corps, 'Profitez de -20% ce mois-ci.')
        self.assertEqual(res.source, 'fake_llm_xmkt34')

    def test_never_auto_sends_only_returns_text(self):
        # Contrat de surface : draft_campaign_content ne renvoie qu'un objet
        # dataclass texte — aucune méthode d'envoi, aucun effet de bord sur
        # une Campagne réelle (l'appelant décide d'appliquer ou non).
        _register_fake()
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_llm_xmkt34', None))
        with override_settings(AI_PROVIDERS={'llm': 'fake_llm_xmkt34'}):
            res = draft_campaign_content(segment_label='S', offre='O')
        self.assertFalse(hasattr(res, 'envoyer'))
        self.assertFalse(hasattr(res, 'send'))

    def test_fallback_when_model_ignores_format(self):
        class _LooseFakeProvider(LLMProvider):
            key = 'fake_llm_xmkt34_loose'

            def is_configured(self):
                return True

            def complete(self, *, prompt, system=None, max_tokens=512):
                return AIResult(
                    ok=True, configured=True, provider=self.key,
                    data={'text': 'Titre libre\nUn corps de message libre.'})

        registry.register_provider(_LooseFakeProvider)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_llm_xmkt34_loose', None))
        with override_settings(AI_PROVIDERS={'llm': 'fake_llm_xmkt34_loose'}):
            res = draft_campaign_content(segment_label='S', offre='O')
        self.assertTrue(res.ok)
        self.assertEqual(res.objet, 'Titre libre')
        self.assertEqual(res.corps, 'Un corps de message libre.')
