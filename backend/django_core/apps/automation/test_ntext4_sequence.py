"""NTEXT4 — automatisation MULTI-ÉTAPES (séquence d'actions).

Couvre :
- la RÉTRO-COMPAT stricte : une règle SANS étape exécute son ``action_type`` /
  ``action_config`` historique et journalise UN seul run (comportement
  d'aujourd'hui inchangé) ;
- la SÉQUENCE : une règle qui envoie un email PUIS crée un ticket SAV PUIS
  assigne l'enregistrement exécute les 3 actions DANS L'ORDRE et journalise
  3 ``AutomationRun`` ;
- l'ORDRE porté par ``ordre`` (et non l'ordre de création) ;
- le fait que la séquence REMPLACE l'action unique de la règle ;
- la robustesse : une étape sans effet / refusée n'interrompt PAS la suite ;
- l'isolation société : les étapes d'une règle d'une AUTRE société ne tournent
  jamais sur l'enregistrement d'un tenant voisin.
"""
import itertools

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity
from apps.sav.models import Ticket

from apps.automation import engine
from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, AutomationStep, TriggerType,
)

User = get_user_model()

_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'ntext4-co-{n}',
        defaults={'nom': nom or f'NTEXT4 Co {n}'})
    return company


def make_user(company, username=None, role='admin'):
    n = next(_seq)
    return User.objects.create_user(
        username=username or f'ntext4-user-{n}', password='x',
        company=company, role_legacy=role)


def rule_signed(company, nom='Séquence signé', **kwargs):
    """Règle « lead passé à SIGNED » (action unique historique par défaut)."""
    kwargs.setdefault('action_type', ActionType.CREATE_ACTIVITY)
    kwargs.setdefault('action_config', {'body': 'action historique'})
    return AutomationRule.objects.create(
        company=company, nom=nom,
        trigger_type=TriggerType.LEAD_STAGE_CHANGE,
        trigger_config={'stage': 'SIGNED'}, **kwargs)


def runs_of(company):
    """Runs de la société, dans leur ORDRE de journalisation."""
    return list(AutomationRun.objects.filter(company=company).order_by('id'))


class RetroCompatSansEtapeTests(TestCase):
    """Sans étape, RIEN ne change : une action, un run, même message."""

    def setUp(self):
        self.co = make_company()

    def test_rule_without_step_runs_its_single_action(self):
        rule_signed(self.co)
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()

        runs = runs_of(self.co)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].status, AutomationRun.Status.SUCCESS)
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, body='action historique').exists())

    def test_run_action_return_value_unchanged_without_step(self):
        rule = rule_signed(self.co)
        lead = Lead.objects.create(company=self.co, nom='T', stage='SIGNED')
        AutomationRun.objects.all().delete()
        status, message = engine.run_action(rule, lead, self.co)
        self.assertEqual(status, AutomationRun.Status.SUCCESS)
        self.assertEqual(message, 'Activité (note) créée sur le lead.')
        self.assertEqual(len(runs_of(self.co)), 1)


class SequenceTests(TestCase):
    """Le critère NTEXT4 : 3 actions en séquence, 3 runs journalisés."""

    def setUp(self):
        self.co = make_company()
        self.cible = make_user(self.co)

    def _rule_with_three_steps(self):
        rule = rule_signed(self.co, nom='Email puis SAV puis assignation')
        AutomationStep.objects.create(
            rule=rule, ordre=1, action_type=ActionType.SEND_EMAIL,
            action_config={'subject': 'Merci', 'body': 'Bonjour'})
        AutomationStep.objects.create(
            rule=rule, ordre=2, action_type=ActionType.CREATE_SAV_TICKET,
            action_config={'description': 'Visite de mise en service'})
        AutomationStep.objects.create(
            rule=rule, ordre=3, action_type=ActionType.ASSIGN_RECORD,
            action_config={'user_id': self.cible.pk})
        return rule

    def test_three_steps_run_in_order_and_log_three_runs(self):
        self._rule_with_three_steps()
        lead = Lead.objects.create(
            company=self.co, nom='Client séquence',
            email='sequence@example.com', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()

        runs = runs_of(self.co)
        self.assertEqual(len(runs), 3)
        self.assertEqual(
            [r.status for r in runs],
            [AutomationRun.Status.SUCCESS] * 3)
        # 1) email réellement remis
        self.assertIn('sequence@example.com',
                      [addr for m in mail.outbox for addr in m.to])
        self.assertIn('sequence@example.com', runs[0].message)
        # 2) ticket SAV créé pour le client résolu depuis le lead
        self.assertEqual(
            Ticket.objects.filter(company=self.co).count(), 1)
        self.assertIn('Ticket SAV', runs[1].message)
        # 3) lead assigné
        lead.refresh_from_db()
        self.assertEqual(lead.owner_id, self.cible.pk)
        self.assertIn('Assigné', runs[2].message)

    def test_execution_order_follows_ordre_not_creation_order(self):
        rule = rule_signed(self.co, nom='Ordre inversé')
        # Créée en PREMIER mais ordre=2 → doit s'exécuter en SECOND.
        AutomationStep.objects.create(
            rule=rule, ordre=2, action_type=ActionType.SET_FIELD,
            action_config={'field': 'priorite', 'value': 'haute'})
        AutomationStep.objects.create(
            rule=rule, ordre=1, action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'première étape'})
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()

        runs = runs_of(self.co)
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0].message, 'Activité (note) créée sur le lead.')
        self.assertEqual(runs[1].message, 'Champ « priorite » mis à jour.')
        lead.refresh_from_db()
        self.assertEqual(lead.priorite, 'haute')

    def test_steps_replace_the_single_action_of_the_rule(self):
        """La séquence REMPLACE ``action_type`` — pas d'action en double."""
        rule_signed(
            self.co, nom='Action unique ignorée',
            action_type=ActionType.SET_FIELD,
            action_config={'field': 'priorite', 'value': 'haute'})
        rule = AutomationRule.objects.get(nom='Action unique ignorée')
        AutomationStep.objects.create(
            rule=rule, ordre=1, action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'seule étape'})
        lead = Lead.objects.create(
            company=self.co, nom='T', stage='NEW', priorite='basse')
        lead.stage = 'SIGNED'
        lead.save()

        self.assertEqual(len(runs_of(self.co)), 1)
        lead.refresh_from_db()
        self.assertEqual(lead.priorite, 'basse')
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, body='seule étape').exists())

    def test_a_refused_step_does_not_stop_the_sequence(self):
        rule = rule_signed(self.co, nom='Étape refusée puis suite')
        AutomationStep.objects.create(
            rule=rule, ordre=1, action_type=ActionType.SET_FIELD,
            action_config={'field': 'company', 'value': 999})
        AutomationStep.objects.create(
            rule=rule, ordre=2, action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'suite exécutée'})
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()

        runs = runs_of(self.co)
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0].status, AutomationRun.Status.SKIPPED)
        self.assertEqual(runs[1].status, AutomationRun.Status.SUCCESS)
        lead.refresh_from_db()
        self.assertEqual(lead.company_id, self.co.id)
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, body='suite exécutée').exists())

    def test_every_run_is_attached_to_the_real_rule(self):
        rule = self._rule_with_three_steps()
        lead = Lead.objects.create(
            company=self.co, nom='T', email='x@example.com', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()
        for run in runs_of(self.co):
            self.assertEqual(run.rule_id, rule.pk)
            self.assertEqual(run.target_model, 'crm.lead')
            self.assertEqual(run.target_id, lead.pk)


class SequenceScopingTests(TestCase):
    """Les étapes n'échappent pas au cloisonnement société de leur règle."""

    def setUp(self):
        self.co_a = make_company(slug='ntext4-scope-a', nom='NTEXT4 Scope A')
        self.co_b = make_company(slug='ntext4-scope-b', nom='NTEXT4 Scope B')

    def test_steps_of_another_company_never_run(self):
        rule = rule_signed(self.co_a, nom='Règle société A')
        AutomationStep.objects.create(
            rule=rule, ordre=1, action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'ne doit jamais arriver'})
        lead_b = Lead.objects.create(company=self.co_b, nom='T', stage='NEW')
        lead_b.stage = 'SIGNED'
        lead_b.save()

        self.assertEqual(AutomationRun.objects.count(), 0)
        self.assertEqual(LeadActivity.objects.count(), 0)
