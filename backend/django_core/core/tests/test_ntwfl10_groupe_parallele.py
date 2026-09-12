"""Tests NTWFL10 — étapes en parallèle (fan-out/fan-in simple).

Couvre l'acceptance criteria : 2 étapes du même groupe démarrent
SIMULTANÉMENT (2 notifications au même instant), l'étape suivante n'active
qu'après les DEUX décisions (dans n'importe quel ordre), un rejet de l'une
bloque/termine le groupe entier (pas de logique de quorum).
"""
from django.dispatch import receiver
from django.test import TestCase

from authentication.models import Company
from core import workflow
from core.events import workflow_etape_activee
from core.models import (
    WorkflowDefinition, WorkflowInstance, WorkflowStepDefinition,
    WorkflowStepInstance,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _definition_groupe(company, code, avec_etape_suivante=True):
    wf = WorkflowDefinition.objects.create(company=company, code=code, nom=code)
    WorkflowStepDefinition.objects.create(
        definition=wf, ordre=1, nom='Membre A', groupe_parallele=1)
    WorkflowStepDefinition.objects.create(
        definition=wf, ordre=2, nom='Membre B', groupe_parallele=1)
    if avec_etape_suivante:
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=3, nom='Après le groupe')
    return wf


class GroupeParalleleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl10', 'NTWFL10')

    def setUp(self):
        self.recus = []

        @receiver(workflow_etape_activee, dispatch_uid='test-ntwfl10-signal')
        def _capter(sender, step, company, **kwargs):
            self.recus.append(step.ordre)
        self._capter = _capter

    def tearDown(self):
        workflow_etape_activee.disconnect(dispatch_uid='test-ntwfl10-signal')

    def test_les_deux_membres_demarrent_simultanement(self):
        wf = _definition_groupe(self.company, 'ntwfl10-fanout')
        workflow.demarrer_workflow(wf, self.company, self.company)

        # Les DEUX membres (ordre 1 et 2) sont notifiés au fan-out initial —
        # jamais un seul.
        self.assertEqual(sorted(self.recus), [1, 2])

    def test_etape_suivante_active_seulement_apres_les_deux_decisions(self):
        wf = _definition_groupe(self.company, 'ntwfl10-attente')
        instance = workflow.demarrer_workflow(wf, self.company, self.company)
        membre_a = instance.step_instances.get(ordre=1)
        membre_b = instance.step_instances.get(ordre=2)
        self.recus.clear()

        # Approuver UN SEUL membre n'active pas encore l'étape 3.
        workflow.approuver_etape(instance, step=membre_a)
        instance.refresh_from_db()
        self.assertEqual(instance.statut, WorkflowInstance.STATUT_EN_COURS)
        etape3 = instance.step_instances.get(ordre=3)
        self.assertEqual(etape3.statut, WorkflowStepInstance.STATUT_EN_ATTENTE)
        # Aucune re-notification du membre B déjà notifié au fan-out.
        self.assertEqual(self.recus, [])

        # Approuver le SECOND membre active enfin l'étape suivante.
        workflow.approuver_etape(instance, step=membre_b)
        instance.refresh_from_db()
        self.assertEqual(instance.etape_courante, 3)
        self.assertEqual(self.recus, [3])

    def test_rejet_d_un_membre_termine_le_groupe_entier(self):
        wf = _definition_groupe(self.company, 'ntwfl10-rejet')
        instance = workflow.demarrer_workflow(wf, self.company, self.company)
        membre_a = instance.step_instances.get(ordre=1)

        workflow.rejeter_etape(instance, step=membre_a, commentaire='Non')

        instance.refresh_from_db()
        self.assertEqual(instance.statut, WorkflowInstance.STATUT_TERMINE)
        membre_b = instance.step_instances.get(ordre=2)
        # Le membre B n'a jamais été décidé, mais l'instance est déjà
        # terminée : plus aucune décision ne doit pouvoir s'appliquer.
        self.assertEqual(membre_b.statut, WorkflowStepInstance.STATUT_EN_ATTENTE)
        with self.assertRaises(ValueError):
            workflow.approuver_etape(instance, step=membre_b)

    def test_decision_dans_n_importe_quel_ordre(self):
        """Approuver B avant A fonctionne exactement pareil (pas d'ordre
        imposé entre les membres d'un même groupe)."""
        wf = _definition_groupe(self.company, 'ntwfl10-ordre-libre')
        instance = workflow.demarrer_workflow(wf, self.company, self.company)
        membre_a = instance.step_instances.get(ordre=1)
        membre_b = instance.step_instances.get(ordre=2)

        workflow.approuver_etape(instance, step=membre_b)
        instance.refresh_from_db()
        self.assertEqual(instance.statut, WorkflowInstance.STATUT_EN_COURS)

        workflow.approuver_etape(instance, step=membre_a)
        instance.refresh_from_db()
        self.assertEqual(instance.etape_courante, 3)
