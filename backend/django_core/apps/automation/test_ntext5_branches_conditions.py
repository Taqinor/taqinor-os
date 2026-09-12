"""NTEXT5 — branches conditionnelles (SI/SINON) dans une automatisation.

Un ``AutomationStep`` porte désormais une ``condition`` (arbre ET/OU/NON,
format ``core.rules``, réutilisé de XPLT15) évaluée sur le contexte de
l'enregistrement : une étape dont la condition est fausse est IGNORÉE (run
``skipped`` journalisé, sans stopper la séquence). ``branche`` ('si'/'sinon'/
'toujours') groupe les étapes de MÊME ``ordre`` en exclusion mutuelle : un
groupe complet si+sinon n'exécute QUE la branche gagnante.
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity

from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, AutomationStep, TriggerType,
)

User = get_user_model()

_seq = itertools.count(1)


def make_company():
    n = next(_seq)
    return Company.objects.create(
        slug=f'ntext5-co-{n}', nom=f'NTEXT5 Co {n}')


def rule_signed(company, nom='Règle branches'):
    return AutomationRule.objects.create(
        company=company, nom=nom,
        trigger_type=TriggerType.LEAD_STAGE_CHANGE,
        trigger_config={'stage': 'SIGNED'},
        action_type=ActionType.CREATE_ACTIVITY,
        action_config={'body': 'action historique'})


def runs_of(company):
    return list(AutomationRun.objects.filter(company=company).order_by('id'))


class BrancheSiSinonTests(TestCase):
    """Le critère NTEXT5 : « si montant>50000 → approbation-like, sinon →
    envoi direct » n'exécute que la branche correspondante."""

    def setUp(self):
        self.co = make_company()

    def _rule_with_branches(self):
        rule = rule_signed(self.co)
        AutomationStep.objects.create(
            rule=rule, ordre=1, branche=AutomationStep.Branche.SI,
            condition={'field': 'montant_estime', 'operator': 'gt',
                       'value': 50000},
            action_type=ActionType.CREATE_SAV_TICKET,
            action_config={'description': 'Gros montant : escalade'})
        AutomationStep.objects.create(
            rule=rule, ordre=1, branche=AutomationStep.Branche.SINON,
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'Envoi direct (petit montant)'})
        return rule

    def test_branche_si_executee_quand_condition_vraie(self):
        self._rule_with_branches()
        lead = Lead.objects.create(
            company=self.co, nom='Gros client', stage='NEW',
            montant_estime=75000)
        lead.stage = 'SIGNED'
        lead.save()

        runs = runs_of(self.co)
        # 1 run réussi (le ticket SAV de la branche « si ») + 1 run skipped
        # (la branche « sinon » non retenue).
        statuses = [r.status for r in runs]
        self.assertIn(AutomationRun.Status.SUCCESS, statuses)
        self.assertIn(AutomationRun.Status.SKIPPED, statuses)
        skipped = [r for r in runs
                   if r.status == AutomationRun.Status.SKIPPED][0]
        self.assertIn('sinon', skipped.message)
        self.assertFalse(LeadActivity.objects.filter(
            lead=lead, body='Envoi direct (petit montant)').exists())

    def test_branche_sinon_executee_quand_condition_fausse(self):
        self._rule_with_branches()
        lead = Lead.objects.create(
            company=self.co, nom='Petit client', stage='NEW',
            montant_estime=1000)
        lead.stage = 'SIGNED'
        lead.save()

        runs = runs_of(self.co)
        statuses = [r.status for r in runs]
        self.assertIn(AutomationRun.Status.SUCCESS, statuses)
        self.assertIn(AutomationRun.Status.SKIPPED, statuses)
        skipped = [r for r in runs
                   if r.status == AutomationRun.Status.SKIPPED][0]
        self.assertIn('si', skipped.message)
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, body='Envoi direct (petit montant)').exists())


class ConditionIndividuelleTests(TestCase):
    """Une étape ``toujours`` avec une condition propre est simplement
    ignorée si la condition est fausse — la suite continue."""

    def setUp(self):
        self.co = make_company()

    def test_etape_toujours_avec_condition_fausse_est_ignoree_sans_stopper(self):
        rule = rule_signed(self.co, nom='Condition simple')
        AutomationStep.objects.create(
            rule=rule, ordre=1,
            condition={'field': 'montant_estime', 'operator': 'gt',
                       'value': 999999},
            action_type=ActionType.SET_FIELD,
            action_config={'field': 'priorite', 'value': 'haute'})
        AutomationStep.objects.create(
            rule=rule, ordre=2, action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'toujours exécutée'})
        lead = Lead.objects.create(
            company=self.co, nom='T', stage='NEW', montant_estime=100,
            priorite='basse')
        lead.stage = 'SIGNED'
        lead.save()

        runs = runs_of(self.co)
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0].status, AutomationRun.Status.SKIPPED)
        self.assertIn('Condition non remplie', runs[0].message)
        self.assertEqual(runs[1].status, AutomationRun.Status.SUCCESS)
        lead.refresh_from_db()
        self.assertEqual(lead.priorite, 'basse')
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, body='toujours exécutée').exists())

    def test_etape_sans_condition_reste_inconditionnelle(self):
        """Rétro-compat : une étape SANS condition (défaut None) s'exécute
        toujours, comme avant NTEXT5."""
        rule = rule_signed(self.co, nom='Sans condition')
        AutomationStep.objects.create(
            rule=rule, ordre=1, action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'toujours'})
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        lead.stage = 'SIGNED'
        lead.save()

        runs = runs_of(self.co)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].status, AutomationRun.Status.SUCCESS)
