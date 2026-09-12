"""Tests NTWFL4 — WorkflowStepDefinition.calendrier_ouvre + le registre de
calendrier ouvré branché sur core.workflow._sla_echeance / demarrer_workflow.

Couvre :
- ``calendrier_ouvre=False`` (défaut) : comportement HISTORIQUE inchangé,
  même sans aucun résolveur enregistré.
- ``calendrier_ouvre=True`` sans résolveur enregistré : repli sur le calcul
  brut (jamais d'exception).
- ``calendrier_ouvre=True`` avec résolveur enregistré : le résolveur est
  appelé et son résultat devient l'échéance SLA de l'étape.
- Un résolveur qui lève une exception ne casse jamais ``demarrer_workflow``
  (repli sur le calcul brut).
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core import workflow
from core.models import WorkflowDefinition, WorkflowStepDefinition


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class CalendrierOuvreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl4', 'NTWFL4')

    def tearDown(self):
        workflow.register_business_day_advance(None)

    def _definition(self, calendrier_ouvre):
        wf = WorkflowDefinition.objects.create(
            company=self.company, code=f'ntwfl4-{calendrier_ouvre}',
            nom='NTWFL4')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Étape 1', sla_heures=48,
            calendrier_ouvre=calendrier_ouvre)
        return wf

    def test_defaut_false_comportement_brut_inchange(self):
        wf = self._definition(calendrier_ouvre=False)
        now = timezone.make_aware(datetime.datetime(2026, 6, 5, 10, 0))
        instance = workflow.demarrer_workflow(wf, self.company, self.company, now=now)
        step = instance.step_instances.get(ordre=1)
        self.assertEqual(step.sla_echeance, now + datetime.timedelta(hours=48))

    def test_true_sans_resolveur_repli_sur_brut(self):
        workflow.register_business_day_advance(None)
        wf = self._definition(calendrier_ouvre=True)
        now = timezone.make_aware(datetime.datetime(2026, 6, 5, 10, 0))
        instance = workflow.demarrer_workflow(wf, self.company, self.company, now=now)
        step = instance.step_instances.get(ordre=1)
        self.assertEqual(step.sla_echeance, now + datetime.timedelta(hours=48))

    def test_true_avec_resolveur_appelle_le_resolveur(self):
        appels = []

        def resolveur(started, sla_heures, company):
            appels.append((started, sla_heures, company))
            return started + datetime.timedelta(hours=999)

        workflow.register_business_day_advance(resolveur)
        wf = self._definition(calendrier_ouvre=True)
        now = timezone.make_aware(datetime.datetime(2026, 6, 5, 10, 0))
        instance = workflow.demarrer_workflow(wf, self.company, self.company, now=now)
        step = instance.step_instances.get(ordre=1)

        self.assertEqual(step.sla_echeance, now + datetime.timedelta(hours=999))
        self.assertEqual(appels, [(now, 48, self.company)])

    def test_resolveur_qui_leve_replie_sur_brut(self):
        def resolveur(started, sla_heures, company):
            raise RuntimeError('boom')

        workflow.register_business_day_advance(resolveur)
        wf = self._definition(calendrier_ouvre=True)
        now = timezone.make_aware(datetime.datetime(2026, 6, 5, 10, 0))
        instance = workflow.demarrer_workflow(wf, self.company, self.company, now=now)
        step = instance.step_instances.get(ordre=1)
        self.assertEqual(step.sla_echeance, now + datetime.timedelta(hours=48))
