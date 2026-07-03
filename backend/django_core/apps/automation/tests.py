"""Tests du moteur d'automatisations (N72 / N73).

Couvre : correspondance des règles (déclencheur + config), journalisation de
CHAQUE exécution, gating par approbation (N73) avec relance à l'approbation,
caractère best-effort des signaux (jamais casser le save d'origine), isolation
par société, et la sécurité des écritures (champ protégé refusé).
"""
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead, LeadActivity
from apps.stock.models import Produit
from apps.ventes.models import Devis, Facture

from apps.automation import engine
from apps.automation.models import (
    ActionType, ApprovalRequest, ApprovalRequestType, AutomationApproval,
    AutomationRule, AutomationRun, CanalMessage, ModeleMessage, TriggerType,
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


class RecursionGuardTests(TestCase):
    """ERR6 — une règle self-référentielle ne doit pas reboucler à l'infini."""

    def setUp(self):
        self.co = make_company('auto-rec', 'Auto Rec')

    def test_self_referential_rule_does_not_recurse(self):
        # La règle écoute le changement d'étape ET réécrit `stage`. Sans garde,
        # le save de l'action ré-émet post_save → RecursionError.
        AutomationRule.objects.create(
            company=self.co, nom='Boucle stage',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SET_FIELD,
            action_config={'field': 'stage', 'value': 'CONTACTED'})
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()  # ne doit PAS lever RecursionError
        lead.refresh_from_db()
        # L'action s'est exécutée une fois (écrit CONTACTED) sans reboucler.
        self.assertEqual(lead.stage, 'CONTACTED')
        # Exactement un run journalisé : pas de cascade d'évaluations.
        self.assertEqual(
            AutomationRun.objects.filter(company=self.co).count(), 1)

    def test_action_save_does_not_retrigger_other_rules(self):
        # Une seconde règle sur le même déclencheur ne doit pas être relancée
        # par le save interne de la première action.
        AutomationRule.objects.create(
            company=self.co, nom='Écrit priorite', ordre=1,
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SET_FIELD,
            action_config={'field': 'priorite', 'value': 'haute'})
        AutomationRule.objects.create(
            company=self.co, nom='Note', ordre=2,
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'note'})
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()
        # Chaque règle s'exécute exactement une fois (2 runs), pas de re-déclenche.
        self.assertEqual(
            AutomationRun.objects.filter(company=self.co).count(), 2)
        self.assertEqual(
            LeadActivity.objects.filter(lead=lead, body='note').count(), 1)


class RunApprovedScopingTests(TestCase):
    """ERR48 — run_approved ne doit jamais résoudre une cible d'un autre tenant."""

    def setUp(self):
        self.co_a = make_company('auto-ra-a', 'RA A')
        self.co_b = make_company('auto-ra-b', 'RA B')

    def test_run_approved_does_not_cross_tenant(self):
        rule = AutomationRule.objects.create(
            company=self.co_a, nom='Diff', requires_approval=True,
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SET_FIELD,
            action_config={'field': 'priorite', 'value': 'haute'})
        # Lead appartenant à la société B, mais ciblé par une approbation A
        # (même PK croisé). La résolution doit échouer (filtre company).
        lead_b = Lead.objects.create(company=self.co_b, nom='B', stage='NEW')
        approval = AutomationApproval.objects.create(
            company=self.co_a, rule=rule,
            target_model='crm.lead', target_id=lead_b.pk,
            status=AutomationApproval.Status.APPROVED)
        engine.run_approved(approval)
        lead_b.refresh_from_db()
        # La cible cross-tenant n'a PAS été écrite.
        self.assertNotEqual(lead_b.priorite, 'haute')

    def test_run_approved_runs_for_same_tenant(self):
        rule = AutomationRule.objects.create(
            company=self.co_a, nom='Diff', requires_approval=True,
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SET_FIELD,
            action_config={'field': 'priorite', 'value': 'haute'})
        lead_a = Lead.objects.create(company=self.co_a, nom='A', stage='NEW')
        approval = AutomationApproval.objects.create(
            company=self.co_a, rule=rule,
            target_model='crm.lead', target_id=lead_a.pk,
            status=AutomationApproval.Status.APPROVED)
        engine.run_approved(approval)
        lead_a.refresh_from_db()
        self.assertEqual(lead_a.priorite, 'haute')


class SendEmailHonestyTests(TestCase):
    """ERR49 — un email perdu doit être journalisé FAILED, jamais SUCCESS."""

    def setUp(self):
        self.co = make_company('auto-mail', 'Auto Mail')

    def test_dropped_email_is_reported_failed(self):
        rule = AutomationRule.objects.create(
            company=self.co, nom='Mail',
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.SEND_EMAIL, action_config={'body': 'salut'})
        client = Client.objects.create(
            company=self.co, nom='C', email='c@example.com')
        devis = Devis.objects.create(
            company=self.co, reference='DEV-MAIL', statut='brouillon',
            client=client)
        # send_mail renvoie 0 (aucun message remis) → FAILED honnête.
        with mock.patch('django.core.mail.send_mail', return_value=0):
            status, _ = engine.run_action(rule, devis, self.co)
        self.assertEqual(status, AutomationRun.Status.FAILED)

    def test_send_error_is_reported_failed(self):
        rule = AutomationRule.objects.create(
            company=self.co, nom='Mail',
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.SEND_EMAIL, action_config={'body': 'salut'})
        client = Client.objects.create(
            company=self.co, nom='C', email='c@example.com')
        devis = Devis.objects.create(
            company=self.co, reference='DEV-MAIL2', statut='brouillon',
            client=client)
        with mock.patch('django.core.mail.send_mail',
                        side_effect=RuntimeError('SMTP down')):
            status, msg = engine.run_action(rule, devis, self.co)
        self.assertEqual(status, AutomationRun.Status.FAILED)
        self.assertIn('SMTP down', msg)

    def test_delivered_email_is_success(self):
        rule = AutomationRule.objects.create(
            company=self.co, nom='Mail',
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.SEND_EMAIL, action_config={'body': 'salut'})
        client = Client.objects.create(
            company=self.co, nom='C', email='c@example.com')
        devis = Devis.objects.create(
            company=self.co, reference='DEV-MAIL3', statut='brouillon',
            client=client)
        mail.outbox = []
        status, _ = engine.run_action(rule, devis, self.co)
        self.assertEqual(status, AutomationRun.Status.SUCCESS)


class FactureOverdueTimezoneTests(TestCase):
    """ERR90 — l'échéance se compare à la date LOCALE (Africa/Casablanca)."""

    def setUp(self):
        self.co = make_company('auto-tz', 'Auto TZ')
        self.client_obj = Client.objects.create(company=self.co, nom='C')
        AutomationRule.objects.create(
            company=self.co, nom='Retard',
            trigger_type=TriggerType.FACTURE_OVERDUE, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY, action_config={'body': 'r'})

    def _facture(self, echeance):
        return Facture.objects.create(
            company=self.co, reference='F-TZ', statut='emise',
            client=self.client_obj, date_echeance=echeance)

    def test_uses_localdate_not_utc(self):
        # localdate() = hier ; date UTC simulée = demain. La facture dont
        # l'échéance == localdate() n'est PAS en retard et ne doit PAS déclencher,
        # même si la date UTC (demain) la ferait paraître échue.
        local_today = date(2026, 6, 20)
        with mock.patch.object(
                timezone, 'localdate', return_value=local_today):
            self._facture(local_today)  # échéance = aujourd'hui local → pas due
        self.assertFalse(AutomationRun.objects.filter(
            rule__trigger_type=TriggerType.FACTURE_OVERDUE).exists())

    def test_overdue_facture_fires(self):
        local_today = date(2026, 6, 20)
        with mock.patch.object(
                timezone, 'localdate', return_value=local_today):
            self._facture(local_today - timedelta(days=1))  # échue hier
        self.assertTrue(AutomationRun.objects.filter(
            rule__trigger_type=TriggerType.FACTURE_OVERDUE).exists())


class ModeleMessageTests(TestCase):
    """DC18 — sujet/corps d'email résolus depuis un modèle stocké éditable,
    avec repli sur l'ancien défaut codé en dur (« Notification Taqinor »)."""

    def setUp(self):
        self.co = make_company('auto-mm', 'Auto MM')
        self.co_b = make_company('auto-mm-b', 'Auto MM B')

    def _send_rule(self):
        return AutomationRule.objects.create(
            company=self.co, nom='Mail',
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.SEND_EMAIL, action_config={'body': 'salut'})

    def _devis_with_email(self, ref='DEV-MM'):
        client = Client.objects.create(
            company=self.co, nom='C', email='c@example.com')
        return Devis.objects.create(
            company=self.co, reference=ref, statut='brouillon', client=client)

    # ── Résolution du modèle ────────────────────────────────────────────

    def test_resolve_falls_back_to_default_subject_when_absent(self):
        objet, corps = ModeleMessage.resolve(self.co, CanalMessage.EMAIL)
        self.assertEqual(objet, 'Notification Taqinor')
        self.assertEqual(corps, '')

    def test_resolve_uses_stored_template(self):
        ModeleMessage.objects.create(
            company=self.co, canal=CanalMessage.EMAIL,
            objet='Bonjour de Taqinor', corps='Corps stocké')
        objet, corps = ModeleMessage.resolve(self.co, CanalMessage.EMAIL)
        self.assertEqual(objet, 'Bonjour de Taqinor')
        self.assertEqual(corps, 'Corps stocké')

    def test_resolve_empty_subject_falls_back_to_default(self):
        ModeleMessage.objects.create(
            company=self.co, canal=CanalMessage.EMAIL, objet='', corps='')
        objet, _ = ModeleMessage.resolve(self.co, CanalMessage.EMAIL)
        self.assertEqual(objet, 'Notification Taqinor')

    def test_resolve_disabled_template_ignored(self):
        ModeleMessage.objects.create(
            company=self.co, canal=CanalMessage.EMAIL,
            objet='Désactivé', corps='x', enabled=False)
        objet, _ = ModeleMessage.resolve(self.co, CanalMessage.EMAIL)
        self.assertEqual(objet, 'Notification Taqinor')

    def test_resolve_per_channel(self):
        ModeleMessage.objects.create(
            company=self.co, canal=CanalMessage.WHATSAPP,
            objet='WA', corps='wa body')
        # Le modèle WhatsApp ne fuit pas sur le canal email.
        objet_email, _ = ModeleMessage.resolve(self.co, CanalMessage.EMAIL)
        self.assertEqual(objet_email, 'Notification Taqinor')
        objet_wa, corps_wa = ModeleMessage.resolve(
            self.co, CanalMessage.WHATSAPP)
        self.assertEqual(objet_wa, 'WA')
        self.assertEqual(corps_wa, 'wa body')

    def test_resolve_scoped_per_company(self):
        ModeleMessage.objects.create(
            company=self.co, canal=CanalMessage.EMAIL,
            objet='Modèle A', corps='a')
        # Une autre société ne voit pas le modèle de self.co → défaut.
        objet, _ = ModeleMessage.resolve(self.co_b, CanalMessage.EMAIL)
        self.assertEqual(objet, 'Notification Taqinor')

    # ── Intégration avec actions._send_email ────────────────────────────

    def test_send_email_uses_default_subject_when_no_template(self):
        rule = self._send_rule()
        devis = self._devis_with_email('DEV-MM-DEF')
        mail.outbox = []
        status, _ = engine.run_action(rule, devis, self.co)
        self.assertEqual(status, AutomationRun.Status.SUCCESS)
        self.assertEqual(mail.outbox[-1].subject, 'Notification Taqinor')

    def test_send_email_uses_stored_subject(self):
        ModeleMessage.objects.create(
            company=self.co, canal=CanalMessage.EMAIL,
            objet='Sujet personnalisé', corps='')
        rule = self._send_rule()
        devis = self._devis_with_email('DEV-MM-SUB')
        mail.outbox = []
        engine.run_action(rule, devis, self.co)
        self.assertEqual(mail.outbox[-1].subject, 'Sujet personnalisé')

    def test_action_config_subject_overrides_template(self):
        ModeleMessage.objects.create(
            company=self.co, canal=CanalMessage.EMAIL,
            objet='Sujet modèle', corps='')
        rule = AutomationRule.objects.create(
            company=self.co, nom='Mail',
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.SEND_EMAIL,
            action_config={'body': 'salut', 'subject': 'Sujet explicite'})
        devis = self._devis_with_email('DEV-MM-OVR')
        mail.outbox = []
        engine.run_action(rule, devis, self.co)
        self.assertEqual(mail.outbox[-1].subject, 'Sujet explicite')

    def test_send_email_body_falls_back_to_template_corps(self):
        ModeleMessage.objects.create(
            company=self.co, canal=CanalMessage.EMAIL,
            objet='S', corps='Corps du modèle')
        # Règle SANS body ni template Paramètres → corps issu du modèle.
        rule = AutomationRule.objects.create(
            company=self.co, nom='Mail',
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.SEND_EMAIL, action_config={})
        devis = self._devis_with_email('DEV-MM-BODY')
        mail.outbox = []
        engine.run_action(rule, devis, self.co)
        self.assertEqual(mail.outbox[-1].body, 'Corps du modèle')


class BeatTaskTests(TestCase):
    """FG2 — Déclencheurs temporels de l'automation engine via Celery Beat."""

    def setUp(self):
        self.co = make_company('beat-co', 'Beat Co')
        self.user = make_user(self.co, 'beat-admin', 'admin')

    def _rule(self, trigger_type):
        """Crée une règle CREATE_ACTIVITY activée pour ce TriggerType."""
        return AutomationRule.objects.create(
            company=self.co, nom=f'Test {trigger_type}',
            trigger_type=trigger_type,
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'test'},
            enabled=True)

    def test_warranty_expiring_beat_triggers_rule(self):
        """WARRANTY_EXPIRING : un équipement en garantie expirante déclenche
        la règle configurée."""
        from apps.crm.models import Client
        from apps.installations.models import Installation
        from apps.sav.models import Equipement
        from apps.stock.models import Produit
        from apps.automation.beat_tasks import _trigger_warranty_expiring

        self._rule(TriggerType.WARRANTY_EXPIRING)
        client = Client.objects.create(company=self.co, nom='CliB')
        chantier = Installation.objects.create(
            company=self.co, client=client, reference='CH-BEAT')
        produit = Produit.objects.create(
            company=self.co, nom='Onduleur Beat', prix_vente=0)
        from datetime import date, timedelta
        Equipement.objects.create(
            company=self.co, produit=produit, installation=chantier,
            statut=Equipement.Statut.EN_SERVICE,
            date_fin_garantie=date.today() + timedelta(days=30))

        count = _trigger_warranty_expiring(self.co)
        self.assertEqual(count, 1)
        self.assertTrue(AutomationRun.objects.filter(
            company=self.co,
            rule__trigger_type=TriggerType.WARRANTY_EXPIRING).exists())

    def test_maintenance_due_beat_triggers_rule(self):
        """MAINTENANCE_DUE : un contrat en retard déclenche la règle."""
        from datetime import date, timedelta
        from apps.crm.models import Client
        from apps.sav.models import ContratMaintenance
        from apps.automation.beat_tasks import _trigger_maintenance_due

        self._rule(TriggerType.MAINTENANCE_DUE)
        client = Client.objects.create(company=self.co, nom='CliM')
        ContratMaintenance.objects.create(
            company=self.co, client=client, actif=True,
            date_debut=date.today() - timedelta(days=400),
            periodicite='annuel')

        count = _trigger_maintenance_due(self.co)
        self.assertEqual(count, 1)
        self.assertTrue(AutomationRun.objects.filter(
            company=self.co,
            rule__trigger_type=TriggerType.MAINTENANCE_DUE).exists())

    def test_facture_overdue_beat_triggers_rule(self):
        """FACTURE_OVERDUE : une facture échue non payée déclenche la règle."""
        from datetime import date, timedelta
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        from apps.automation.beat_tasks import _trigger_facture_overdue

        self._rule(TriggerType.FACTURE_OVERDUE)
        client = Client.objects.create(company=self.co, nom='CliF')
        Facture.objects.create(
            company=self.co, client=client, reference='F-BEAT',
            statut='envoye',
            date_echeance=date.today() - timedelta(days=1))

        count = _trigger_facture_overdue(self.co)
        self.assertEqual(count, 1)
        self.assertTrue(AutomationRun.objects.filter(
            company=self.co,
            rule__trigger_type=TriggerType.FACTURE_OVERDUE).exists())

    def test_beat_noop_without_matching_rules(self):
        """Sans règle activée, la tâche ne fait rien."""
        from apps.automation.beat_tasks import time_triggers_daily
        result = time_triggers_daily()
        self.assertIsInstance(result, int)
        self.assertEqual(AutomationRun.objects.count(), 0)

    def test_beat_scoped_per_company(self):
        """Les évaluations ne traversent pas les frontières de société."""
        from datetime import date, timedelta
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        from apps.automation.beat_tasks import _trigger_facture_overdue

        # Règle dans self.co uniquement.
        self._rule(TriggerType.FACTURE_OVERDUE)
        other_co = make_company('beat-other', 'Beat Other')
        other_client = Client.objects.create(company=other_co, nom='OtherC')
        # Facture de l'AUTRE société.
        Facture.objects.create(
            company=other_co, client=other_client, reference='F-OTHER',
            statut='envoye',
            date_echeance=date.today() - timedelta(days=1))

        count = _trigger_facture_overdue(other_co)
        # Aucune règle dans other_co → 0 run.
        self.assertEqual(count, 1)  # la facture existe (count = nb d'évaluations)
        # Mais aucun run enregistré pour other_co.
        self.assertEqual(
            AutomationRun.objects.filter(company=other_co).count(), 0)


# ─────────────────────────────────────────────────────────────────────────────
# XKB2 — Types de demandes d'approbation ad-hoc configurables.

class ApprovalRequestTests(TestCase):
    def setUp(self):
        self.co = make_company('xkb2-a', 'XKB2 A')
        self.admin = make_user(self.co, 'xkb2-admin', 'admin')
        self.employe = make_user(self.co, 'xkb2-emp', 'normal')

    def _type(self, **kwargs):
        defaults = dict(
            company=self.co, nom='Note de frais', enabled=True,
            champs_requis=['montant'], champs_optionnels=['reference'])
        defaults.update(kwargs)
        return ApprovalRequestType.objects.create(**defaults)

    def test_admin_creates_type_with_required_field(self):
        api = auth(self.admin)
        resp = api.post('/api/django/automation/approval-request-types/', {
            'nom': 'Note de frais > 1000 MAD',
            'champs_requis': ['montant'],
            'champs_optionnels': [],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            ApprovalRequestType.objects.get(pk=resp.data['id']).company,
            self.co)

    def test_employee_cannot_create_type(self):
        api = auth(self.employe)
        resp = api.post('/api/django/automation/approval-request-types/', {
            'nom': 'Hack', 'champs_requis': [],
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_employee_submits_request_seen_by_approver(self):
        req_type = self._type()
        api = auth(self.employe)
        resp = api.post('/api/django/automation/approval-requests/', {
            'request_type': req_type.pk,
            'payload': {'montant': '1200'},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        req = ApprovalRequest.objects.get(pk=resp.data['id'])
        self.assertEqual(req.demandeur, self.employe)
        self.assertEqual(req.status, ApprovalRequest.Status.PENDING)

        # L'approbateur (admin) le voit dans la boîte.
        admin_api = auth(self.admin)
        listing = admin_api.get('/api/django/automation/approval-requests/')
        ids = [r['id'] for r in rows(listing)]
        self.assertIn(req.pk, ids)

    def test_submission_rejects_missing_required_field(self):
        req_type = self._type()
        api = auth(self.employe)
        resp = api.post('/api/django/automation/approval-requests/', {
            'request_type': req_type.pk,
            'payload': {},
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ApprovalRequest.objects.count(), 0)

    def test_approver_approves_and_decision_is_visible(self):
        req_type = self._type()
        req = ApprovalRequest.objects.create(
            company=self.co, request_type=req_type, demandeur=self.employe,
            payload={'montant': '900'})
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/automation/approval-requests/{req.pk}/approve/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        req.refresh_from_db()
        self.assertEqual(req.status, ApprovalRequest.Status.APPROVED)
        self.assertEqual(req.decided_by, self.admin)

    def test_employee_cannot_approve(self):
        req_type = self._type()
        req = ApprovalRequest.objects.create(
            company=self.co, request_type=req_type, demandeur=self.employe,
            payload={'montant': '900'})
        api = auth(self.employe)
        resp = api.post(
            f'/api/django/automation/approval-requests/{req.pk}/approve/',
            {}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_tenant_isolation_on_requests(self):
        req_type = self._type()
        req = ApprovalRequest.objects.create(
            company=self.co, request_type=req_type, demandeur=self.employe,
            payload={'montant': '900'})
        other_co = make_company('xkb2-b', 'XKB2 B')
        other_admin = make_user(other_co, 'xkb2-admin-b', 'admin')
        api = auth(other_admin)
        resp = api.get('/api/django/automation/approval-requests/')
        ids = [r['id'] for r in rows(resp)]
        self.assertNotIn(req.pk, ids)

    def test_disabled_type_cannot_be_used_for_submission(self):
        req_type = self._type(enabled=False)
        api = auth(self.employe)
        resp = api.post('/api/django/automation/approval-requests/', {
            'request_type': req_type.pk,
            'payload': {'montant': '100'},
        }, format='json')
        self.assertEqual(resp.status_code, 400)
