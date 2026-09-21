"""NTAI8/NTAI9 — Tests du copilote de fiche (résumé + prochaines actions).

Couvre : le résumé d'un lead scopé société, le refus d'un type hors whitelist,
la dégradation propre sans clé LLM, l'ALLOWLIST de champs (aucune donnée
interne transmissible), et — côté NTAI9 — « devis envoyé + relance dépassée »
qui renvoie « relancer » en tête avec une clé d'action exécutable, stades lus
depuis STAGES.py.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.ai import AIResult, LLMProvider, register_provider
from core.ai import registry

from ..copilote import (FAITS_TERMES_INTERDITS, RESUME_CHAMPS,
                        RESUME_CONTENT_TYPES, faits_decision, faits_fiche,
                        prochaines_actions)

User = get_user_model()

RESUME_URL = '/api/django/ai/resume-fiche/'
ACTIONS_URL = '/api/django/ai/prochaines-actions/'


class FakeCopiloteLLM(LLMProvider):
    key = 'fake_ntai8'
    dernier_prompt = None

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        FakeCopiloteLLM.dernier_prompt = prompt
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': 'Lead en attente de relance.'})


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai8CopiloteFicheTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.crm.models import Lead
        from apps.crm.stages import CONTACTED, QUOTE_SENT

        cls.QUOTE_SENT = QUOTE_SENT
        cls.CONTACTED = CONTACTED
        cls.company = make_company('ntai8-co', 'NTAI8 Co')
        cls.autre = make_company('ntai8-autre', 'NTAI8 Autre')
        cls.user = User.objects.create_user(
            username='ntai8-user', password='x', company=cls.company,
            role_legacy='normal')
        # Superutilisateur : le catalogue d'actions agent filtre par PERMISSION
        # (``registry.for_user``) — pour prouver qu'une clé exécutable est bien
        # proposée, il faut un utilisateur qui a le droit de l'exécuter.
        cls.admin = User.objects.create_user(
            username='ntai8-admin', password='x', company=cls.company,
            role_legacy='admin')
        cls.admin.is_superuser = True
        cls.admin.save(update_fields=['is_superuser'])
        cls.lead = Lead.objects.create(
            company=cls.company, nom='Client Test', ville='Casablanca',
            stage=QUOTE_SENT,
            relance_date=timezone.localdate() - timedelta(days=5))
        cls.lead_autre = Lead.objects.create(
            company=cls.autre, nom='Lead voisin', stage=CONTACTED)

    def setUp(self):
        FakeCopiloteLLM.dernier_prompt = None

    def _with_fake_llm(self):
        register_provider(FakeCopiloteLLM)
        self.addCleanup(
            lambda: registry._REGISTRY['llm'].pop('fake_ntai8', None))

    # --- Allowlist ----------------------------------------------------------

    def test_allowlist_ne_contient_aucun_champ_interne(self):
        for interdit in FAITS_TERMES_INTERDITS:
            self.assertNotIn(interdit, RESUME_CHAMPS)
        for champ in RESUME_CHAMPS:
            self.assertNotIn('prix_achat', champ)
            self.assertNotIn('marge', champ)

    def test_faits_ne_lisent_que_l_allowlist(self):
        faits = faits_fiche(self.lead)
        self.assertTrue(set(faits).issubset(set(RESUME_CHAMPS)))
        self.assertEqual(faits.get('ville'), 'Casablanca')

    # --- NTAI8 : résumé -----------------------------------------------------

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai8'})
    def test_resume_d_un_lead(self):
        self._with_fake_llm()
        reponse = auth(self.user).post(
            RESUME_URL,
            {'content_type': 'crm.lead', 'object_id': self.lead.id},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        corps = reponse.json()
        self.assertEqual(corps['content_type'], 'crm.lead')
        self.assertIn('relance', corps['resume'].lower())
        self.assertIn('ville', corps['faits'])

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai8'})
    def test_type_hors_whitelist_refuse(self):
        self._with_fake_llm()
        reponse = auth(self.user).post(
            RESUME_URL, {'content_type': 'stock.produit', 'object_id': 1},
            format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('non pris en charge', reponse.json()['detail'])

    @override_settings(AI_PROVIDERS={'llm': 'fake_ntai8'})
    def test_fiche_d_une_autre_societe_refusee(self):
        self._with_fake_llm()
        reponse = auth(self.user).post(
            RESUME_URL,
            {'content_type': 'crm.lead', 'object_id': self.lead_autre.id},
            format='json')
        self.assertEqual(reponse.status_code, 400)

    @override_settings(AI_PROVIDERS={})
    def test_sans_cle_llm_degradation_douce(self):
        reponse = auth(self.user).post(
            RESUME_URL,
            {'content_type': 'crm.lead', 'object_id': self.lead.id},
            format='json')
        self.assertEqual(reponse.status_code, 503)
        self.assertIn('lecture manuelle', reponse.json()['detail'])

    def test_corps_incomplet_refuse(self):
        reponse = auth(self.user).post(
            RESUME_URL, {'content_type': 'crm.lead'}, format='json')
        self.assertEqual(reponse.status_code, 400)

    # --- NTAI9 : prochaines actions ----------------------------------------

    def test_faits_decision_lisent_les_stades_de_stages_py(self):
        faits = faits_decision(self.lead, 'crm.lead', fil=[])
        self.assertEqual(faits['stage'], self.QUOTE_SENT)
        self.assertTrue(faits['has_open_quote'])
        self.assertGreaterEqual(faits['days_since_contact'], 5)

    @override_settings(AI_PROVIDERS={})
    def test_devis_envoye_et_relance_depassee_donne_relancer(self):
        resultat = prochaines_actions(
            company=self.company, content_type='crm.lead',
            object_id=self.lead.id, user=self.admin)
        self.assertEqual(resultat['actions'][0]['action'], 'relancer')
        self.assertFalse(resultat['execute'])
        # Clé du catalogue agent : exécutable en un clic (propose → confirme).
        self.assertEqual(resultat['actions'][0]['action_key'],
                         'crm.lead.whatsapp_prepare')

    @override_settings(AI_PROVIDERS={})
    def test_actions_disponibles_sans_cle_llm(self):
        reponse = auth(self.user).post(
            ACTIONS_URL,
            {'content_type': 'crm.lead', 'object_id': self.lead.id},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        corps = reponse.json()
        self.assertGreaterEqual(len(corps['actions']), 1)
        self.assertLessEqual(len(corps['actions']), 3)
        self.assertFalse(corps['execute'])

    @override_settings(AI_PROVIDERS={})
    def test_au_plus_trois_actions(self):
        resultat = prochaines_actions(
            company=self.company, content_type='crm.lead',
            object_id=self.lead.id, user=self.user, limit=3)
        self.assertLessEqual(len(resultat['actions']), 3)
        cles = [a['action'] for a in resultat['actions']]
        self.assertEqual(len(cles), len(set(cles)))

    def test_whitelist_de_types_documentee(self):
        self.assertIn('crm.lead', RESUME_CONTENT_TYPES)
        self.assertNotIn('stock.produit', RESUME_CONTENT_TYPES)
