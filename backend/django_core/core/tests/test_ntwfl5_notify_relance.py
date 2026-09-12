"""Tests NTWFL5 — notification à l'activation d'une étape BPM (comble
YEVNT8) + relance à mi-SLA (comble YEVNT9), core.workflow uniquement (pas de
canal réel — voir apps/notifications pour l'intégration bout en bout).

Couvre :
- ``core.events.workflow_etape_activee`` est émis EXACTEMENT quand une étape
  devient la nouvelle étape courante (démarrage ET avancement), jamais pour
  une étape ``auto`` franchie automatiquement.
- ``core.workflow.etapes_a_mi_sla`` : sélectionne une étape après 50% du
  délai SLA écoulé, jamais avant, jamais sans SLA configuré, jamais deux
  fois (``dernier_rappel_le``).
- ``core.workflow.marquer_rappel_envoye`` pose le marqueur une seule fois.
"""
import datetime

from django.dispatch import receiver
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core import workflow
from core.events import workflow_etape_activee
from core.models import WorkflowDefinition, WorkflowStepDefinition


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class WorkflowEtapeActiveeSignalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl5-signal', 'NTWFL5 Signal')

    def setUp(self):
        self.recus = []

        @receiver(workflow_etape_activee, dispatch_uid='test-ntwfl5-signal')
        def _capter(sender, step, company, **kwargs):
            self.recus.append((step, company))
        self._capter = _capter

    def tearDown(self):
        workflow_etape_activee.disconnect(dispatch_uid='test-ntwfl5-signal')

    def test_demarrage_emet_pour_la_premiere_etape_manuelle(self):
        wf = WorkflowDefinition.objects.create(
            company=self.company, code='ntwfl5-a', nom='NTWFL5 A')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Étape manuelle')

        workflow.demarrer_workflow(wf, self.company, self.company)

        self.assertEqual(len(self.recus), 1)
        step, company = self.recus[0]
        self.assertEqual(step.ordre, 1)
        self.assertEqual(company, self.company)

    def test_etapes_auto_ne_declenchent_rien(self):
        wf = WorkflowDefinition.objects.create(
            company=self.company, code='ntwfl5-b', nom='NTWFL5 B')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Auto',
            type_approbation=WorkflowStepDefinition.APPROBATION_AUTO)
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=2, nom='Manuelle 2')

        workflow.demarrer_workflow(wf, self.company, self.company)

        # UNE seule émission (l'étape 2, manuelle) — l'étape 1 auto ne notifie
        # jamais personne.
        self.assertEqual(len(self.recus), 1)
        self.assertEqual(self.recus[0][0].ordre, 2)

    def test_avancement_emet_pour_la_deuxieme_etape(self):
        wf = WorkflowDefinition.objects.create(
            company=self.company, code='ntwfl5-c', nom='NTWFL5 C')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Étape 1')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=2, nom='Étape 2')

        instance = workflow.demarrer_workflow(wf, self.company, self.company)
        self.recus.clear()
        workflow.approuver_etape(instance)

        self.assertEqual(len(self.recus), 1)
        self.assertEqual(self.recus[0][0].ordre, 2)


class EtapesAMiSlaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl5-misla', 'NTWFL5 mi-SLA')

    def _instance_avec_sla(self, sla_heures, started):
        wf = WorkflowDefinition.objects.create(
            company=self.company, code=f'ntwfl5-sla-{sla_heures}-{started}',
            nom='NTWFL5 SLA')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Étape', sla_heures=sla_heures)
        return workflow.demarrer_workflow(
            wf, self.company, self.company, now=started)

    def test_avant_mi_sla_pas_selectionnee(self):
        started = timezone.make_aware(datetime.datetime(2026, 1, 1, 8, 0))
        instance = self._instance_avec_sla(48, started)
        now = started + datetime.timedelta(hours=10)  # 20% écoulé
        self.assertEqual(workflow.etapes_a_mi_sla(self.company, now), [])
        step = instance.step_instances.get(ordre=1)
        self.assertIsNone(step.dernier_rappel_le)

    def test_apres_mi_sla_selectionnee_une_fois(self):
        started = timezone.make_aware(datetime.datetime(2026, 1, 1, 8, 0))
        instance = self._instance_avec_sla(48, started)
        now = started + datetime.timedelta(hours=30)  # 62.5% écoulé
        resultat = workflow.etapes_a_mi_sla(self.company, now)
        self.assertEqual(len(resultat), 1)
        step = resultat[0]
        self.assertEqual(step.instance_id, instance.id)

        workflow.marquer_rappel_envoye(step, now=now)
        step.refresh_from_db()
        self.assertEqual(step.dernier_rappel_le, now)

        # Un second passage NE la retrouve plus (déjà relancée).
        self.assertEqual(workflow.etapes_a_mi_sla(self.company, now), [])

    def test_sans_sla_configure_jamais_selectionnee(self):
        wf = WorkflowDefinition.objects.create(
            company=self.company, code='ntwfl5-sans-sla', nom='Sans SLA')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Étape', sla_heures=None)
        started = timezone.make_aware(datetime.datetime(2026, 1, 1, 8, 0))
        workflow.demarrer_workflow(wf, self.company, self.company, now=started)
        now = started + datetime.timedelta(days=30)
        self.assertEqual(workflow.etapes_a_mi_sla(self.company, now), [])
