"""Tests du moteur d'automatisations (N72 / N73).

Couvre : correspondance des règles (déclencheur + config), journalisation de
CHAQUE exécution, gating par approbation (N73) avec relance à l'approbation,
caractère best-effort des signaux (jamais casser le save d'origine), isolation
par société, et la sécurité des écritures (champ protégé refusé).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead, LeadActivity
from apps.stock.models import Produit
from apps.ventes.models import Devis

from apps.automation import engine
from apps.automation.models import (
    ActionType, AutomationApproval, AutomationRule, AutomationRun, TriggerType,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


class RuleMatchingTests(TestCase):
    def setUp(self):
        self.co = make_company('auto-a', 'Auto A')
        self.user = make_user(self.co, 'auto-admin-a', 'admin')

    def test_lead_stage_change_runs_matching_rule_and_logs(self):
        AutomationRule.objects.create(
            company=self.co, nom='Note quand signé',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE,
            trigger_config={'stage': 'SIGNED'},
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'Lead signé !'})
        lead = Lead.objects.create(company=self.co, nom='Test', stage='NEW')
        # Changement d'étape vers SIGNED → la règle correspond.
        lead.stage = 'SIGNED'
        lead.save()

        run = AutomationRun.objects.filter(company=self.co).first()
        self.assertIsNotNone(run)
        self.assertEqual(run.status, AutomationRun.Status.SUCCESS)
        self.assertTrue(
            LeadActivity.objects.filter(lead=lead, body='Lead signé !').exists())

    def test_rule_with_other_stage_does_not_match(self):
        AutomationRule.objects.create(
            company=self.co, nom='Seulement CONTACTED',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE,
            trigger_config={'stage': 'CONTACTED'},
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'x'})
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()
        self.assertEqual(AutomationRun.objects.count(), 0)

    def test_disabled_rule_never_runs(self):
        AutomationRule.objects.create(
            company=self.co, nom='Désactivée', enabled=False,
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY, action_config={'body': 'x'})
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()
        self.assertEqual(AutomationRun.objects.count(), 0)

    def test_no_rules_means_no_behaviour_change(self):
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()
        self.assertEqual(AutomationRun.objects.count(), 0)
        self.assertEqual(LeadActivity.objects.count(), 0)

    def test_devis_accepted_trigger(self):
        AutomationRule.objects.create(
            company=self.co, nom='Devis accepté',
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.SEND_EMAIL, action_config={'body': 'merci'})
        client = Client.objects.create(company=self.co, nom='Client X')
        devis = Devis.objects.create(
            company=self.co, reference='DEV-1', statut='brouillon',
            client=client)
        devis.statut = 'accepte'
        devis.save()
        run = AutomationRun.objects.filter(
            rule__trigger_type=TriggerType.DEVIS_ACCEPTED).first()
        self.assertIsNotNone(run)
        # Pas d'email cible sur le devis → no-op journalisé (sûr).
        self.assertIn(run.status, (
            AutomationRun.Status.NOOP, AutomationRun.Status.SUCCESS))

    def test_stock_below_threshold_trigger(self):
        AutomationRule.objects.create(
            company=self.co, nom='Stock bas',
            trigger_type=TriggerType.STOCK_BELOW_THRESHOLD, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY, action_config={'body': 'x'})
        # quantite_stock (2) <= seuil_alerte (5) à la création → déclenche.
        Produit.objects.create(
            company=self.co, nom='Vis', prix_vente=10,
            quantite_stock=2, seuil_alerte=5)
        self.assertTrue(AutomationRun.objects.filter(
            rule__trigger_type=TriggerType.STOCK_BELOW_THRESHOLD).exists())


class SetFieldActionTests(TestCase):
    def setUp(self):
        self.co = make_company('auto-sf', 'Auto SF')

    def test_set_field_updates_record(self):
        AutomationRule.objects.create(
            company=self.co, nom='Priorité haute si signé',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE,
            trigger_config={'stage': 'SIGNED'},
            action_type=ActionType.SET_FIELD,
            action_config={'field': 'priorite', 'value': 'haute'})
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()
        lead.refresh_from_db()
        self.assertEqual(lead.priorite, 'haute')

    def test_set_field_refuses_protected_company(self):
        rule = AutomationRule.objects.create(
            company=self.co, nom='Tentative société',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SET_FIELD,
            action_config={'field': 'company', 'value': 999})
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        status, _ = engine.run_action(rule, lead, self.co)
        self.assertEqual(status, AutomationRun.Status.SKIPPED)
        lead.refresh_from_db()
        self.assertEqual(lead.company_id, self.co.id)


class ApprovalGatingTests(TestCase):
    def setUp(self):
        self.co = make_company('auto-ap', 'Auto AP')
        self.owner = make_user(self.co, 'auto-owner', 'admin')

    def test_action_requiring_approval_defers_and_creates_pending(self):
        AutomationRule.objects.create(
            company=self.co, nom='À approuver',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE,
            trigger_config={'stage': 'SIGNED'},
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'différé'},
            requires_approval=True)
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()
        # L'action ne part PAS : approbation en attente + run pending.
        self.assertFalse(LeadActivity.objects.filter(body='différé').exists())
        approval = AutomationApproval.objects.get(company=self.co)
        self.assertEqual(approval.status, AutomationApproval.Status.PENDING)
        self.assertEqual(approval.target_id, lead.pk)
        run = AutomationRun.objects.filter(
            status=AutomationRun.Status.PENDING_APPROVAL).first()
        self.assertIsNotNone(run)

    def test_threshold_below_runs_immediately(self):
        rule = AutomationRule.objects.create(
            company=self.co, nom='Remise > 10',
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'x'},
            requires_approval=True, approval_threshold=10)
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        # amount 5 <= seuil 10 → pas d'approbation, exécution directe.
        engine.evaluate(TriggerType.DEVIS_ACCEPTED, lead, self.co,
                        context={'amount': 5})
        self.assertEqual(
            AutomationApproval.objects.filter(rule=rule).count(), 0)
        self.assertTrue(AutomationRun.objects.filter(
            rule=rule, status=AutomationRun.Status.SUCCESS).exists())

    def test_threshold_above_requires_approval(self):
        rule = AutomationRule.objects.create(
            company=self.co, nom='Remise > 10',
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'x'},
            requires_approval=True, approval_threshold=10)
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        engine.evaluate(TriggerType.DEVIS_ACCEPTED, lead, self.co,
                        context={'amount': 20})
        self.assertEqual(
            AutomationApproval.objects.filter(rule=rule).count(), 1)

    def test_approve_runs_deferred_action(self):
        rule = AutomationRule.objects.create(
            company=self.co, nom='À approuver',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'enfin lancé'},
            requires_approval=True)
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        engine.evaluate(TriggerType.LEAD_STAGE_CHANGE, lead, self.co)
        approval = AutomationApproval.objects.get(rule=rule)

        api = auth(self.owner)
        resp = api.post(
            f'/api/django/automation/approvals/{approval.pk}/approve/')
        self.assertEqual(resp.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, AutomationApproval.Status.APPROVED)
        self.assertTrue(
            LeadActivity.objects.filter(body='enfin lancé').exists())

    def test_reject_never_runs_action(self):
        rule = AutomationRule.objects.create(
            company=self.co, nom='À rejeter',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'ne doit pas partir'},
            requires_approval=True)
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        engine.evaluate(TriggerType.LEAD_STAGE_CHANGE, lead, self.co)
        approval = AutomationApproval.objects.get(rule=rule)

        api = auth(self.owner)
        resp = api.post(
            f'/api/django/automation/approvals/{approval.pk}/reject/')
        self.assertEqual(resp.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, AutomationApproval.Status.REJECTED)
        self.assertFalse(
            LeadActivity.objects.filter(body='ne doit pas partir').exists())

    def test_non_owner_cannot_decide(self):
        rule = AutomationRule.objects.create(
            company=self.co, nom='À approuver',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY, action_config={'body': 'x'},
            requires_approval=True)
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        engine.evaluate(TriggerType.LEAD_STAGE_CHANGE, lead, self.co)
        approval = AutomationApproval.objects.get(rule=rule)

        limited = make_user(self.co, 'auto-limited', 'normal')
        api = auth(limited)
        resp = api.post(
            f'/api/django/automation/approvals/{approval.pk}/approve/')
        self.assertEqual(resp.status_code, 403)


class SignalBestEffortTests(TestCase):
    """Un échec d'action ne doit JAMAIS casser le save d'origine."""

    def setUp(self):
        self.co = make_company('auto-be', 'Auto BE')

    def test_failing_action_does_not_break_save(self):
        # action_type inconnu via set_field sur un champ absent → noop/skip,
        # mais surtout : le save du lead réussit toujours.
        AutomationRule.objects.create(
            company=self.co, nom='Champ inexistant',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SET_FIELD,
            action_config={'field': 'champ_qui_nexiste_pas', 'value': 'x'})
        lead = Lead.objects.create(company=self.co, nom='Survivant', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()  # ne doit pas lever
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'SIGNED')

    def test_exception_in_engine_is_swallowed(self):
        # Simule une action qui lève : evaluate journalise FAILED, ne lève pas.
        rule = AutomationRule.objects.create(
            company=self.co, nom='Boom',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type='inexistant', action_config={})
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        # Ne doit pas lever.
        engine.evaluate(TriggerType.LEAD_STAGE_CHANGE, lead, self.co)
        self.assertTrue(AutomationRun.objects.filter(rule=rule).exists())


class CompanyScopingTests(TestCase):
    def setUp(self):
        self.co_a = make_company('auto-scope-a', 'Scope A')
        self.co_b = make_company('auto-scope-b', 'Scope B')
        self.admin_a = make_user(self.co_a, 'scope-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'scope-admin-b', 'admin')

    def test_rule_of_other_company_never_runs(self):
        AutomationRule.objects.create(
            company=self.co_b, nom='Règle B',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY, action_config={'body': 'b'})
        # Lead de la société A change d'étape → la règle de B ne tourne pas.
        lead = Lead.objects.create(company=self.co_a, nom='A', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()
        self.assertEqual(AutomationRun.objects.count(), 0)

    def test_list_rules_scoped_to_company(self):
        AutomationRule.objects.create(
            company=self.co_a, nom='Règle A',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY, action_config={})
        AutomationRule.objects.create(
            company=self.co_b, nom='Règle B',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY, action_config={})
        api = auth(self.admin_a)
        resp = api.get('/api/django/automation/rules/')
        self.assertEqual(resp.status_code, 200)
        noms = {r['nom'] for r in rows(resp)}
        self.assertEqual(noms, {'Règle A'})

    def test_company_forced_server_side_on_create(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/automation/rules/', {
            'nom': 'Forcée', 'trigger_type': TriggerType.LEAD_STAGE_CHANGE,
            'trigger_config': {}, 'action_type': ActionType.CREATE_ACTIVITY,
            'action_config': {}, 'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        rule = AutomationRule.objects.get(nom='Forcée')
        self.assertEqual(rule.company_id, self.co_a.id)

    def test_non_admin_cannot_create_rule(self):
        limited = make_user(self.co_a, 'scope-limited', 'normal')
        api = auth(limited)
        resp = api.post('/api/django/automation/rules/', {
            'nom': 'X', 'trigger_type': TriggerType.LEAD_STAGE_CHANGE,
            'trigger_config': {}, 'action_type': ActionType.CREATE_ACTIVITY,
            'action_config': {},
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_toggle_endpoint_flips_enabled(self):
        rule = AutomationRule.objects.create(
            company=self.co_a, nom='À basculer', enabled=True,
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY, action_config={})
        api = auth(self.admin_a)
        resp = api.post(f'/api/django/automation/rules/{rule.pk}/toggle/')
        self.assertEqual(resp.status_code, 200)
        rule.refresh_from_db()
        self.assertFalse(rule.enabled)


class RunLogTests(TestCase):
    def setUp(self):
        self.co = make_company('auto-log', 'Auto Log')
        self.admin = make_user(self.co, 'log-admin', 'admin')

    def test_runs_endpoint_lists_company_runs(self):
        rule = AutomationRule.objects.create(
            company=self.co, nom='R',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY, action_config={'body': 'x'})
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        engine.evaluate(TriggerType.LEAD_STAGE_CHANGE, lead, self.co)
        api = auth(self.admin)
        resp = api.get('/api/django/automation/runs/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(rows(resp)) >= 1)
        self.assertEqual(rows(resp)[0]['rule'], rule.pk)
