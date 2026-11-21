"""Tests YHARD2 — journal des actions IA confirmées + rollback.

Couvre : journalisation à la confirmation (scopée société), refus
d'annulation d'une action irréversible / déjà annulée / sans handler,
annulation réussie via un handler enregistré, isolation multi-tenant de
l'endpoint de lecture + de l'endpoint d'annulation.
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from apps.agent import services
from apps.agent.models import AgentActionLog, UsageIA
from core.ai import AIResult, LLMProvider, get_provider, register_provider, usage_context
from core.ai import registry as ai_registry
from core.ai.usage import usage_sinks
from apps.agent.views import AgentActionLogView, AgentActionUndoView

User = get_user_model()


class LogConfirmedActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='YHARD2 Co')
        cls.other = Company.objects.create(nom='YHARD2 Autre')
        cls.user = User.objects.create_user(
            username='yhard2_user', password='x', company=cls.company)

    def test_log_creates_entry_scoped_to_company(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.user, action_key='devis.envoyer',
            risk_level=AgentActionLog.RiskLevel.OUTWARD, inputs={'devis_id': 1})
        self.assertEqual(log.company_id, self.company.id)
        self.assertEqual(log.action_key, 'devis.envoyer')
        self.assertIsNotNone(log.executed_at)
        self.assertIsNone(log.undone_at)

    def test_log_derives_content_type_from_resulted_object(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.user, action_key='crm.creer_client',
            risk_level=AgentActionLog.RiskLevel.INTERNAL,
            resulted_object=self.company)
        self.assertIsNotNone(log.content_type)
        self.assertEqual(log.object_id, str(self.company.pk))

    def test_origine_confirmee_par_defaut_interne_sur_demande(self):
        """Copilote vague 2 (FND7) — journal des écritures internes."""
        par_defaut = services.log_confirmed_action(
            company=self.company, user=self.user, action_key='devis.envoyer',
            risk_level=AgentActionLog.RiskLevel.OUTWARD)
        interne = services.log_confirmed_action(
            company=self.company, user=self.user, action_key='crm.lead.note',
            risk_level=AgentActionLog.RiskLevel.INTERNAL, inputs={'id': 4},
            origine=AgentActionLog.Origine.INTERNE)
        self.assertEqual((par_defaut.origine, interne.origine), ('confirmee', 'interne'))
        self.assertFalse(interne.is_undoable)  # aucun handler pour une écriture interne


class AnnulerActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='YHARD2 Undo Co')
        cls.user = User.objects.create_user(
            username='yhard2_undo', password='x', company=cls.company)

    def setUp(self):
        self._calls = []
        services.register_undo_handler('test.reversible', self._fake_handler)

    def _fake_handler(self, log):
        self._calls.append(log.pk)
        return 'annule (test)'

    def test_irreversible_action_cannot_be_undone(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.user, action_key='test.reversible',
            risk_level=AgentActionLog.RiskLevel.IRREVERSIBLE)
        with self.assertRaises(services.ActionNotUndoableError):
            services.annuler_action(log)
        self.assertEqual(self._calls, [])

    def test_no_handler_registered_refuses(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.user, action_key='test.no_handler',
            risk_level=AgentActionLog.RiskLevel.OUTWARD)
        with self.assertRaises(services.ActionNotUndoableError):
            services.annuler_action(log)

    def test_reversible_action_undo_calls_handler_and_marks_undone(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.user, action_key='test.reversible',
            risk_level=AgentActionLog.RiskLevel.OUTWARD)
        result = services.annuler_action(log)
        self.assertEqual(self._calls, [log.pk])
        self.assertIsNotNone(result.undone_at)
        self.assertEqual(result.undo_detail, 'annule (test)')

    def test_already_undone_action_cannot_be_undone_again(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.user, action_key='test.reversible',
            risk_level=AgentActionLog.RiskLevel.OUTWARD)
        services.annuler_action(log)
        with self.assertRaises(services.ActionNotUndoableError):
            services.annuler_action(log)
        self.assertEqual(len(self._calls), 1)


class AgentActionLogEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='YHARD2 EP Co')
        cls.other = Company.objects.create(nom='YHARD2 EP Autre')
        cls.admin = User.objects.create_user(
            username='yhard2_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.plain = User.objects.create_user(
            username='yhard2_plain', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def test_list_scoped_to_company(self):
        services.log_confirmed_action(
            company=self.company, user=self.admin, action_key='a',
            risk_level=AgentActionLog.RiskLevel.INTERNAL)
        services.log_confirmed_action(
            company=self.other, user=self.admin, action_key='b',
            risk_level=AgentActionLog.RiskLevel.INTERNAL)
        req = self.factory.get('/logs/')
        force_authenticate(req, user=self.admin)
        resp = AgentActionLogView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)

    def test_non_admin_forbidden(self):
        req = self.factory.get('/logs/')
        force_authenticate(req, user=self.plain)
        resp = AgentActionLogView.as_view()(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_undo_endpoint_scoped_to_company_404_for_other(self):
        services.register_undo_handler('test.endpoint', lambda log: 'ok')
        log = services.log_confirmed_action(
            company=self.other, user=self.admin, action_key='test.endpoint',
            risk_level=AgentActionLog.RiskLevel.OUTWARD)
        req = self.factory.post(f'/logs/{log.pk}/annuler/')
        force_authenticate(req, user=self.admin)
        resp = AgentActionUndoView.as_view()(req, pk=log.pk)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_undo_endpoint_success(self):
        services.register_undo_handler('test.endpoint2', lambda log: 'ok')
        log = services.log_confirmed_action(
            company=self.company, user=self.admin, action_key='test.endpoint2',
            risk_level=AgentActionLog.RiskLevel.OUTWARD)
        req = self.factory.post(f'/logs/{log.pk}/annuler/')
        force_authenticate(req, user=self.admin)
        resp = AgentActionUndoView.as_view()(req, pk=log.pk)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        log.refresh_from_db()
        self.assertIsNotNone(log.undone_at)

    def test_undo_endpoint_irreversible_conflict(self):
        log = services.log_confirmed_action(
            company=self.company, user=self.admin, action_key='test.irrev',
            risk_level=AgentActionLog.RiskLevel.IRREVERSIBLE)
        req = self.factory.post(f'/logs/{log.pk}/annuler/')
        force_authenticate(req, user=self.admin)
        resp = AgentActionUndoView.as_view()(req, pk=log.pk)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)


# ─────────────────────────────────────────────────────────────────────────────
# Décision fondateur 21/11/2026 — journal d'usage IA persisté (UsageIA)
# ─────────────────────────────────────────────────────────────────────────────

class _FauxLLM(LLMProvider):
    key = 'faux_usage_ia'
    label = 'Faux LLM (usage IA)'

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': 'réponse secrète',
                              'usage': {'prompt_tokens': 120,
                                        'completion_tokens': 30}})


@override_settings(AI_PROVIDERS={'llm': 'faux_usage_ia'}, AI_PII_REDACTION=False)
class UsageIASinkTests(TestCase):
    PROMPT = 'Client Jean Dupont 0612345678 toit à Rabat'

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Usage IA Co')

    def setUp(self):
        register_provider(_FauxLLM)
        self.addCleanup(lambda: ai_registry._REGISTRY['llm'].pop('faux_usage_ia', None))

    def _appel(self):
        with usage_context(company_id=self.company.pk, feature_key='test.usage_ia'):
            return get_provider('llm').complete(prompt=self.PROMPT)

    def test_puits_branche_au_demarrage(self):
        self.assertIn(services.enregistrer_usage_ia, usage_sinks())

    @override_settings(AI_TOKEN_COSTS={})
    def test_un_appel_une_ligne_societe_jetons_cout_inconnu(self):
        res = self._appel()
        self.assertTrue(res.ok)
        lignes = list(UsageIA.objects.all())
        self.assertEqual(len(lignes), 1)
        ligne = lignes[0]
        self.assertEqual(ligne.company_id, self.company.pk)
        self.assertEqual((ligne.capability, ligne.provider, ligne.feature_key),
                         ('llm', 'faux_usage_ia', 'test.usage_ia'))
        self.assertEqual((ligne.input_tokens, ligne.output_tokens), (120, 30))
        self.assertTrue(ligne.success)
        self.assertIsNone(ligne.cout)  # aucun tarif ⇒ coût INCONNU, jamais 0 inventé

    @override_settings(AI_TOKEN_COSTS={'faux_usage_ia': {'prompt': '1', 'completion': '2'}})
    def test_cout_pose_seulement_si_tarife(self):
        self._appel()
        # (120 × 1 + 30 × 2) / 1000 = 0,18 MAD
        self.assertEqual(UsageIA.objects.get().cout, Decimal('0.18'))

    def test_aucun_contenu_stocke(self):
        self._appel()
        valeurs = ' '.join(str(v) for v in UsageIA.objects.values().get().values())
        for fragment in ('Jean', 'Dupont', '0612345678', 'Rabat', 'secrète'):
            self.assertNotIn(fragment, valeurs)

    def test_hors_contexte_societe_aucune_ligne(self):
        get_provider('llm').complete(prompt='x')
        self.assertFalse(UsageIA.objects.exists())

    def test_puits_en_echec_ne_casse_pas_l_appel(self):
        with mock.patch.object(UsageIA.objects, 'create', side_effect=RuntimeError('base en panne')):
            res = self._appel()
        self.assertTrue(res.ok)
        self.assertEqual(res.data['text'], 'réponse secrète')
        # La transaction du test reste utilisable (savepoint).
        self.assertEqual(Company.objects.filter(pk=self.company.pk).count(), 1)

    def test_societe_inconnue_ignoree_sans_erreur(self):
        services.enregistrer_usage_ia(company_id=999999, capability='llm', provider='x')
        self.assertFalse(UsageIA.objects.exists())
