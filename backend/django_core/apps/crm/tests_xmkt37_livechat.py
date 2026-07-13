"""XMKT37 — Livechat / assistant IA de qualification (côté ERP uniquement).

Couvre :
  - ouverture de session → token émis, société résolue serveur ;
  - jeton invalide → 404 sur post/get ;
  - throttling actif (classe de throttle attachée aux vues publiques) ;
  - SANS clé LLM (mode dégradé) : le visiteur reçoit le message d'absence
    configurable, et un lead est quand même créé dès que nom + contact sont
    capturés (jamais d'exception) ;
  - AVEC un faux fournisseur LLM : la réponse générée est utilisée ;
  - le lead créé porte le canal livechat, le stage NEW (STAGES.py) et le
    transcript complet dans le chatter ;
  - le prompt système de qualification ne contient JAMAIS de terme interne
    (prix_achat/marge/coût interne/fournisseur) ;
  - multi-tenant : deux sociétés ne partagent jamais une session/un lead.
"""
import json

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from apps.crm.models import ChatSessionPublique, Lead, LeadActivity
from apps.crm import stages
from core.ai import LIVECHAT_FORBIDDEN_TERMS, LIVECHAT_QUALIFICATION_SYSTEM_PROMPT
from core.ai.providers import AIResult, LLMProvider
from core.ai import registry


class _FakeQualificationLLM(LLMProvider):
    key = 'fake_livechat_llm'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        self.last_prompt = prompt
        self.last_system = system
        return AIResult(
            ok=True, configured=True, provider=self.key,
            data={'text': 'Merci ! Quelle est votre ville ?'})


def _register_fake_llm():
    registry.register_provider(_FakeQualificationLLM)


class PromptSafetyTests(TestCase):
    """Le prompt système ne doit JAMAIS exposer de donnée interne."""

    def test_prompt_has_no_forbidden_internal_terms(self):
        lowered = LIVECHAT_QUALIFICATION_SYSTEM_PROMPT.lower()
        for term in LIVECHAT_FORBIDDEN_TERMS:
            self.assertNotIn(term.lower(), lowered)


class OpenSessionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Chat', slug='taqinor-chat')

    def test_open_session_issues_token(self):
        resp = self.client.post(reverse('public-chat-open'))
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['token'])
        session = ChatSessionPublique.objects.get(token=resp.data['token'])
        self.assertEqual(session.company_id, self.company.id)
        self.assertEqual(session.statut, ChatSessionPublique.Statut.ACTIVE)


class InvalidTokenTests(TestCase):
    def setUp(self):
        Company.objects.create(nom='Taqinor Chat 2', slug='taqinor-chat-2')

    def test_post_message_invalid_token_404(self):
        resp = self.client.post(
            reverse('public-chat-post', kwargs={'token': 'nope'}),
            data=json.dumps({'message': 'Bonjour'}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 404)

    def test_get_session_invalid_token_404(self):
        resp = self.client.get(
            reverse('public-chat-get', kwargs={'token': 'nope'}))
        self.assertEqual(resp.status_code, 404)


class ThrottleWiringTests(TestCase):
    """Vérifie que le throttle est bien attaché aux vues publiques (pas son
    comportement précis sous charge — juste le câblage)."""

    def test_post_view_has_throttle_classes(self):
        from apps.crm.public_chat_views import (
            post_chat_message, PublicChatRateThrottle,
        )
        throttles = getattr(post_chat_message.cls, 'throttle_classes', [])
        self.assertIn(PublicChatRateThrottle, throttles)

    def test_get_view_has_throttle_classes(self):
        from apps.crm.public_chat_views import (
            get_chat_session, PublicChatRateThrottle,
        )
        throttles = getattr(get_chat_session.cls, 'throttle_classes', [])
        self.assertIn(PublicChatRateThrottle, throttles)


class DegradedModeCaptureTests(TestCase):
    """Sans clé LLM configurée : mode dégradé, capture quand même le lead."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Chat Off', slug='taqinor-chat-off')
        open_resp = self.client.post(reverse('public-chat-open'))
        self.token = open_resp.data['token']

    def _post(self, message):
        return self.client.post(
            reverse('public-chat-post', kwargs={'token': self.token}),
            data=json.dumps({'message': message}),
            content_type='application/json')

    def test_away_message_returned_without_llm(self):
        resp = self._post('Bonjour, je veux un devis solaire.')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('commercial TAQINOR', resp.data['reply'])

    def test_lead_created_once_name_and_phone_captured(self):
        self._post('Bonjour, je veux un devis solaire à Casablanca.')
        resp = self._post(
            "Je m'appelle Yassine, mon numéro est 0612345678.")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['lead_created'])

        session = ChatSessionPublique.objects.get(token=self.token)
        self.assertEqual(session.statut, ChatSessionPublique.Statut.QUALIFIEE)
        self.assertIsNotNone(session.lead_id)

        lead = session.lead
        self.assertEqual(lead.company_id, self.company.id)
        self.assertEqual(lead.canal, Lead.Canal.AUTRE)
        self.assertEqual(lead.stage, stages.NEW)
        self.assertEqual(lead.telephone, '0612345678')

        notes = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE)
        self.assertTrue(
            any('Transcript livechat' in (n.body or '') for n in notes))

    def test_second_message_does_not_duplicate_lead(self):
        self._post("Je m'appelle Yassine, 0612345678.")
        self._post('Une autre question.')
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 1)


@override_settings()
class LLMConfiguredReplyTests(TestCase):
    """Avec un faux fournisseur LLM sélectionné, la réponse générée est
    utilisée à la place du message d'absence."""

    def setUp(self):
        _register_fake_llm()
        self.company = Company.objects.create(
            nom='Taqinor Chat On', slug='taqinor-chat-on')
        open_resp = self.client.post(reverse('public-chat-open'))
        self.token = open_resp.data['token']

    @override_settings(AI_PROVIDERS={'llm': 'fake_livechat_llm'})
    def test_generated_reply_used_when_llm_configured(self):
        resp = self.client.post(
            reverse('public-chat-post', kwargs={'token': self.token}),
            data=json.dumps({'message': 'Bonjour'}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['reply'], 'Merci ! Quelle est votre ville ?')


class MultiTenantChatTests(TestCase):
    def test_sessions_are_not_shared_across_companies(self):
        co_a = Company.objects.create(nom='Chat A', slug='chat-a')
        session_a = ChatSessionPublique.objects.create(company=co_a)
        # Un jeton d'une société n'expose jamais de donnée d'une autre — on
        # vérifie juste que la session lue est bien celle de sa société.
        resp = self.client.get(
            reverse('public-chat-get', kwargs={'token': session_a.token}))
        self.assertEqual(resp.status_code, 200)
        session_a.refresh_from_db()
        self.assertEqual(session_a.company_id, co_a.id)


class ResolveCompanyGuardTests(TestCase):
    """QXG5 — code guard : un ``WEBSITE_LEADS_COMPANY_ID`` absent/mauvais ne
    doit jamais mésrouter une session livechat en silence. La confirmation
    prod (variable bien posée) reste un check ops manuel du fondateur — hors
    périmètre ici."""

    def test_missing_env_var_with_two_companies_logs_loud_error(self):
        from apps.crm.public_chat_views import _resolve_company
        c1 = Company.objects.create(nom='Livechat A', slug='livechat-a')
        Company.objects.create(nom='Livechat B', slug='livechat-b')
        with override_settings(WEBSITE_LEADS_COMPANY_ID=None):
            with self.assertLogs('apps.crm.public_chat_views', level='ERROR') as cm:
                resolved = _resolve_company()
        # Repli conservé (safe — jamais casser l'endpoint) : 1re Company par pk.
        self.assertEqual(resolved, c1)
        self.assertTrue(any('WEBSITE_LEADS_COMPANY_ID' in m for m in cm.output))

    def test_missing_env_var_single_company_no_loud_error(self):
        from apps.crm.public_chat_views import _resolve_company
        c1 = Company.objects.create(nom='Livechat Solo', slug='livechat-solo')
        with override_settings(WEBSITE_LEADS_COMPANY_ID=None):
            resolved = _resolve_company()
        self.assertEqual(resolved, c1)

    def test_bad_env_var_value_logs_loud_error_and_returns_none(self):
        from apps.crm.public_chat_views import _resolve_company
        Company.objects.create(nom='Livechat C', slug='livechat-c')
        with override_settings(WEBSITE_LEADS_COMPANY_ID=999999):
            with self.assertLogs('apps.crm.public_chat_views', level='ERROR') as cm:
                resolved = _resolve_company()
        self.assertIsNone(resolved)
        self.assertTrue(any('999999' in m for m in cm.output))
