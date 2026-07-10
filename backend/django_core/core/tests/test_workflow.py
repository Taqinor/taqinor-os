"""Tests FG366 — moteur de workflow multi-étapes (BPM) + SLA / escalades.

Couvre :
  * définition → démarrage → avancement → approbation → complétion ;
  * chemin de rejet (chaîne stoppée, instance terminée) ;
  * calcul déterministe de l'échéance SLA (started + sla_heures) ;
  * sélecteur ``etapes_sla_depassees`` (now passé explicitement) + escalade ;
  * étapes ``auto`` franchies sans intervention ;
  * scoping multi-tenant (étapes/instances portent la société, pas de fuite) ;
  * cible GÉNÉRIQUE : un workflow s'attache à n'importe quel modèle (ici une
    Company de l'app fondation authentication) via contenttypes — preuve que
    ``core`` reste découplé.
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStepDefinition,
    WorkflowStepInstance,
)
from core import workflow


def _make_def(company, code='validation_devis', steps=None):
    """Crée une définition + ses étapes ; ``steps`` = liste de dicts kwargs."""
    wf = WorkflowDefinition.objects.create(
        company=company, code=code, nom='Validation devis')
    steps = steps if steps is not None else [
        {'ordre': 1, 'nom': 'Manager', 'sla_heures': 24},
        {'ordre': 2, 'nom': 'Directeur', 'sla_heures': 48},
    ]
    for s in steps:
        WorkflowStepDefinition.objects.create(definition=wf, **s)
    return wf


class WorkflowHappyPathTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Taqinor Test')

    def test_define_start_advance_approve_complete(self):
        wf = _make_def(self.company)
        now = timezone.make_aware(datetime.datetime(2026, 6, 29, 8, 0, 0))
        # Cible générique : on attache le workflow à une Company (fondation).
        target = self.company
        inst = workflow.demarrer_workflow(wf, target, self.company, now=now)

        self.assertEqual(inst.statut, WorkflowInstance.STATUT_EN_COURS)
        self.assertEqual(inst.step_instances.count(), 2)
        self.assertEqual(inst.etape_courante, 1)
        self.assertEqual(inst.started_le, now)

        # Étape 1 active, en attente.
        step1 = workflow.etape_courante_de(inst)
        self.assertEqual(step1.ordre, 1)
        self.assertEqual(step1.statut, WorkflowStepInstance.STATUT_EN_ATTENTE)

        # Approuver l'étape 1 → avance vers l'étape 2.
        workflow.approuver_etape(inst, commentaire='OK manager', now=now)
        inst.refresh_from_db()
        step1.refresh_from_db()
        self.assertEqual(step1.statut, WorkflowStepInstance.STATUT_APPROUVE)
        self.assertEqual(step1.commentaire, 'OK manager')
        self.assertEqual(inst.etape_courante, 2)
        self.assertEqual(inst.statut, WorkflowInstance.STATUT_EN_COURS)

        # Approuver l'étape 2 → instance terminée.
        later = now + datetime.timedelta(hours=5)
        workflow.approuver_etape(inst, now=later)
        inst.refresh_from_db()
        self.assertEqual(inst.statut, WorkflowInstance.STATUT_TERMINE)
        self.assertEqual(inst.ended_le, later)

    def test_generic_target_resolves_back(self):
        wf = _make_def(self.company, code='c_target')
        target = self.company
        inst = workflow.demarrer_workflow(wf, target, self.company)
        inst.refresh_from_db()
        ct = ContentType.objects.get_for_model(Company)
        self.assertEqual(inst.content_type_id, ct.id)
        self.assertEqual(inst.object_id, self.company.pk)
        # Le GenericForeignKey résout bien vers l'objet d'origine.
        self.assertEqual(inst.target, self.company)

    def test_empty_definition_finishes_immediately(self):
        wf = _make_def(self.company, code='vide', steps=[])
        inst = workflow.demarrer_workflow(wf, self.company, self.company)
        inst.refresh_from_db()
        self.assertEqual(inst.statut, WorkflowInstance.STATUT_TERMINE)
        self.assertEqual(inst.step_instances.count(), 0)


class WorkflowRejectTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Rejet Test')

    def test_reject_stops_chain(self):
        wf = _make_def(self.company, code='rejet')
        inst = workflow.demarrer_workflow(wf, self.company, self.company)
        step = workflow.rejeter_etape(inst, commentaire='Prix trop bas')
        inst.refresh_from_db()
        self.assertEqual(step.statut, WorkflowStepInstance.STATUT_REJETE)
        self.assertEqual(step.commentaire, 'Prix trop bas')
        self.assertEqual(inst.statut, WorkflowInstance.STATUT_TERMINE)
        # L'étape 2 n'a jamais été activée.
        step2 = inst.step_instances.get(ordre=2)
        self.assertEqual(step2.statut, WorkflowStepInstance.STATUT_EN_ATTENTE)

    def test_approve_without_pending_raises(self):
        wf = _make_def(self.company, code='vide2', steps=[])
        inst = workflow.demarrer_workflow(wf, self.company, self.company)
        with self.assertRaises(ValueError):
            workflow.approuver_etape(inst)


class WorkflowSlaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='SLA Test')
        cls.other = Company.objects.create(nom='Autre SLA')

    def test_sla_echeance_computed_from_started(self):
        wf = _make_def(self.company, code='sla', steps=[
            {'ordre': 1, 'nom': 'M', 'sla_heures': 24},
            {'ordre': 2, 'nom': 'D', 'sla_heures': None},
        ])
        now = timezone.make_aware(datetime.datetime(2026, 6, 29, 8, 0, 0))
        inst = workflow.demarrer_workflow(wf, self.company, self.company, now=now)
        s1 = inst.step_instances.get(ordre=1)
        s2 = inst.step_instances.get(ordre=2)
        self.assertEqual(s1.sla_echeance, now + datetime.timedelta(hours=24))
        # Pas de sla_heures → pas d'échéance (jamais en dépassement).
        self.assertIsNone(s2.sla_echeance)

    def test_overdue_selector_lists_only_passed(self):
        wf = _make_def(self.company, code='over', steps=[
            {'ordre': 1, 'nom': 'M', 'sla_heures': 24},
        ])
        start = timezone.make_aware(datetime.datetime(2026, 6, 28, 8, 0, 0))
        workflow.demarrer_workflow(wf, self.company, self.company, now=start)

        # Avant échéance (start + 10h) → rien.
        before = start + datetime.timedelta(hours=10)
        self.assertEqual(workflow.etapes_sla_depassees(self.company, before), [])

        # Après échéance (start + 30h > 24h) → l'étape 1 ressort.
        after = start + datetime.timedelta(hours=30)
        overdue = workflow.etapes_sla_depassees(self.company, after)
        self.assertEqual(len(overdue), 1)
        self.assertEqual(overdue[0].ordre, 1)

    def test_flag_overdue_escalates(self):
        wf = _make_def(self.company, code='esc', steps=[
            {'ordre': 1, 'nom': 'M', 'sla_heures': 12},
        ])
        start = timezone.make_aware(datetime.datetime(2026, 6, 28, 8, 0, 0))
        workflow.demarrer_workflow(wf, self.company, self.company, now=start)
        after = start + datetime.timedelta(hours=20)
        escalated = workflow.flag_overdue_steps(self.company, after)
        self.assertEqual(len(escalated), 1)
        step = escalated[0]
        step.refresh_from_db()
        self.assertEqual(step.statut, WorkflowStepInstance.STATUT_ESCALADE)
        self.assertEqual(step.decided_le, after)
        # Plus rien à escalader (déjà escaladé, plus en attente).
        self.assertEqual(workflow.etapes_sla_depassees(self.company, after), [])

    def test_overdue_is_per_company(self):
        wf = _make_def(self.company, code='multico', steps=[
            {'ordre': 1, 'nom': 'M', 'sla_heures': 1},
        ])
        start = timezone.make_aware(datetime.datetime(2026, 6, 28, 8, 0, 0))
        workflow.demarrer_workflow(wf, self.company, self.company, now=start)
        after = start + datetime.timedelta(hours=5)
        # La société 'other' ne voit aucune étape en dépassement.
        self.assertEqual(workflow.etapes_sla_depassees(self.other, after), [])
        self.assertEqual(len(workflow.etapes_sla_depassees(self.company, after)), 1)


class WorkflowAutoStepTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Auto Test')

    def test_auto_steps_cross_without_intervention(self):
        wf = _make_def(self.company, code='auto', steps=[
            {'ordre': 1, 'nom': 'Auto', 'type_approbation':
             WorkflowStepDefinition.APPROBATION_AUTO},
            {'ordre': 2, 'nom': 'Manuel'},
        ])
        now = timezone.make_aware(datetime.datetime(2026, 6, 29, 8, 0, 0))
        inst = workflow.demarrer_workflow(wf, self.company, self.company, now=now)
        inst.refresh_from_db()
        s1 = inst.step_instances.get(ordre=1)
        # L'étape auto est franchie d'emblée ; le pointeur est sur l'étape 2.
        self.assertEqual(s1.statut, WorkflowStepInstance.STATUT_APPROUVE)
        self.assertEqual(inst.etape_courante, 2)
        self.assertEqual(inst.statut, WorkflowInstance.STATUT_EN_COURS)

    def test_all_auto_completes_instance(self):
        wf = _make_def(self.company, code='allauto', steps=[
            {'ordre': 1, 'nom': 'A1', 'type_approbation':
             WorkflowStepDefinition.APPROBATION_AUTO},
            {'ordre': 2, 'nom': 'A2', 'type_approbation':
             WorkflowStepDefinition.APPROBATION_AUTO},
        ])
        inst = workflow.demarrer_workflow(wf, self.company, self.company)
        inst.refresh_from_db()
        self.assertEqual(inst.statut, WorkflowInstance.STATUT_TERMINE)


class WorkflowTenancyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Tenant A')
        cls.other = Company.objects.create(nom='Tenant B')

    def test_instance_and_steps_carry_company(self):
        wf = _make_def(self.company, code='tenant')
        inst = workflow.demarrer_workflow(wf, self.company, self.company)
        self.assertEqual(inst.company, self.company)
        for step in inst.step_instances.all():
            self.assertEqual(step.company, self.company)

    def test_company_scoping_isolates_instances(self):
        wf_a = _make_def(self.company, code='iso_a')
        wf_b = _make_def(self.other, code='iso_b')
        workflow.demarrer_workflow(wf_a, self.company, self.company)
        workflow.demarrer_workflow(wf_b, self.other, self.other)
        a_qs = WorkflowInstance.objects.filter(company=self.company)
        b_qs = WorkflowInstance.objects.filter(company=self.other)
        self.assertEqual(a_qs.count(), 1)
        self.assertEqual(b_qs.count(), 1)
        self.assertNotEqual(a_qs.first().pk, b_qs.first().pk)

    def test_unique_code_per_company(self):
        _make_def(self.company, code='dup')
        # Même code, autre société → autorisé.
        try:
            _make_def(self.other, code='dup')
        except Exception as exc:  # pragma: no cover - ne devrait pas lever
            self.fail(f"Code dupliqué entre sociétés rejeté à tort : {exc}")
        self.assertEqual(
            WorkflowDefinition.objects.filter(code='dup').count(), 2)


class InstanceEnCoursPourTests(TestCase):
    """ARC10 — le sélecteur ``instance_en_cours_pour`` résout le workflow EN
    COURS d'une cible générique, scopé société et optionnellement par code."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Résolveur A')
        cls.other = Company.objects.create(nom='Résolveur B')

    def test_resolves_running_instance_for_target(self):
        wf = _make_def(self.company, code='res')
        inst = workflow.demarrer_workflow(wf, self.company, self.company)
        found = workflow.instance_en_cours_pour(self.company, self.company)
        self.assertEqual(found.id, inst.id)

    def test_scoped_to_company(self):
        wf = _make_def(self.company, code='res_scope')
        workflow.demarrer_workflow(wf, self.company, self.company)
        # La cible est une Company de la société A ; B ne voit rien.
        self.assertIsNone(
            workflow.instance_en_cours_pour(self.company, self.other))

    def test_filtered_by_definition_code(self):
        wf = _make_def(self.company, code='res_code')
        workflow.demarrer_workflow(wf, self.company, self.company)
        self.assertIsNotNone(
            workflow.instance_en_cours_pour(
                self.company, self.company, definition_code='res_code'))
        self.assertIsNone(
            workflow.instance_en_cours_pour(
                self.company, self.company, definition_code='autre'))

    def test_ignores_finished_instance(self):
        wf = _make_def(self.company, code='res_done', steps=[])
        # Définition sans étape → instance terminée d'emblée.
        workflow.demarrer_workflow(wf, self.company, self.company)
        self.assertIsNone(
            workflow.instance_en_cours_pour(self.company, self.company))
