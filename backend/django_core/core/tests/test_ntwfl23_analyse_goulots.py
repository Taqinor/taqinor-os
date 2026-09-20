"""Tests NTWFL23 — audit de processus (temps par étape, goulots).

Acceptance criteria couverte : une définition avec 50 instances historiques
renvoie la durée moyenne par étape ET désigne l'étape la plus lente comme
goulot ; l'isolation tenant est vérifiée (la définition d'une autre société
est indistinguable d'une définition inexistante).
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company, CustomUser
from testkit.base import TenantAPITestCase

from core import workflow
from core.models import (
    WorkflowDefinition, WorkflowStepDefinition, WorkflowStepInstance,
)
from core.selectors import analyse_goulots_workflow


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _definition_trois_paliers(company, code):
    wf = WorkflowDefinition.objects.create(
        company=company, code=code, nom=code)
    for ordre, nom in ((1, 'Vérification'), (2, 'Validation'), (3, 'Clôture')):
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=ordre, nom=nom)
    return wf


def _figer(step_ids, base, heures, statut):
    """Fixe ``created_at``/``decided_le``/``statut`` d'un lot d'étapes.

    ``created_at`` est ``auto_now_add`` : un ``queryset.update()`` est le SEUL
    moyen d'écrire une durée observée déterministe (aucun ``timezone.now()``
    ne se glisse dans la mesure)."""
    WorkflowStepInstance.objects.filter(pk__in=step_ids).update(
        created_at=base,
        decided_le=base + datetime.timedelta(hours=heures),
        statut=statut,
    )


class AnalyseGoulotsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl23', 'NTWFL23')
        cls.autre = make_company('ntwfl23-autre', 'NTWFL23 Autre')
        cls.base = timezone.now() - datetime.timedelta(days=30)
        cls.wf = _definition_trois_paliers(cls.company, 'ntwfl23-audit')

        cls.nb_instances = 50
        instances = [
            workflow.demarrer_workflow(
                cls.wf, cls.company, cls.company, now=cls.base)
            for _ in range(cls.nb_instances)
        ]
        etapes = {1: [], 2: [], 3: []}
        for instance in instances:
            for step in instance.step_instances.all():
                etapes[step.ordre].append(step.pk)

        # Palier 1 — 40 décisions en 1 h, 10 en 10 h : moyenne 2,8 h,
        # médiane 1 h, p90 10 h (le p90 renvoie une durée RÉELLEMENT observée).
        _figer(etapes[1][:40], cls.base, 1,
               WorkflowStepInstance.STATUT_APPROUVE)
        _figer(etapes[1][40:], cls.base, 10,
               WorkflowStepInstance.STATUT_APPROUVE)
        # Palier 2 — 6 h partout : le GOULOT. 10 rejets + 5 escalades SLA.
        _figer(etapes[2][:35], cls.base, 6,
               WorkflowStepInstance.STATUT_APPROUVE)
        _figer(etapes[2][35:45], cls.base, 6,
               WorkflowStepInstance.STATUT_REJETE)
        _figer(etapes[2][45:], cls.base, 6,
               WorkflowStepInstance.STATUT_ESCALADE)
        # Palier 3 — 2 h partout.
        _figer(etapes[3], cls.base, 2,
               WorkflowStepInstance.STATUT_APPROUVE)
        cls.nb_etapes_definition = cls.wf.steps.count()

    def test_durees_par_etape_et_goulot(self):
        analyse = analyse_goulots_workflow(self.company, self.wf.pk)
        self.assertIsNotNone(analyse)
        self.assertEqual(len(analyse['etapes']), self.nb_etapes_definition)
        p1, p2, p3 = analyse['etapes']

        self.assertEqual(p1['nb_decisions'], self.nb_instances)
        self.assertAlmostEqual(p1['duree_moyenne_h'], 2.8, places=3)
        self.assertAlmostEqual(p1['duree_mediane_h'], 1.0, places=3)
        self.assertAlmostEqual(p1['duree_p90_h'], 10.0, places=3)
        self.assertAlmostEqual(p2['duree_moyenne_h'], 6.0, places=3)
        self.assertAlmostEqual(p3['duree_moyenne_h'], 2.0, places=3)

        # L'étape la plus lente EST le goulot — et elle seule.
        self.assertEqual(analyse['goulot_ordre'], 2)
        self.assertTrue(p2['goulot'])
        self.assertFalse(p1['goulot'])
        self.assertFalse(p3['goulot'])

    def test_taux_rejet_et_escalade(self):
        analyse = analyse_goulots_workflow(self.company, self.wf.pk)
        p2 = analyse['etapes'][1]
        self.assertAlmostEqual(p2['taux_rejet'], 0.2, places=3)
        self.assertAlmostEqual(p2['taux_escalade'], 0.1, places=3)
        p1 = analyse['etapes'][0]
        self.assertAlmostEqual(p1['taux_rejet'], 0.0, places=3)

    def test_nb_instances_compte_reellement(self):
        analyse = analyse_goulots_workflow(self.company, self.wf.pk)
        from core.models import WorkflowInstance
        self.assertEqual(
            analyse['nb_instances'],
            WorkflowInstance.objects.filter(
                company=self.company, definition=self.wf).count())

    def test_isolation_tenant_definition_dautre_societe(self):
        wf_autre = _definition_trois_paliers(self.autre, 'ntwfl23-autre-def')
        # Vue depuis ``self.company``, la définition de l'autre société est
        # introuvable — indistinguable d'un id inexistant.
        self.assertIsNone(
            analyse_goulots_workflow(self.company, wf_autre.pk))
        self.assertIsNone(
            analyse_goulots_workflow(self.company, 9_999_999))

    def test_etape_sans_decision_reste_non_mesuree(self):
        wf = _definition_trois_paliers(self.company, 'ntwfl23-vide')
        workflow.demarrer_workflow(wf, self.company, self.company,
                                   now=self.base)
        analyse = analyse_goulots_workflow(self.company, wf.pk)
        for etape in analyse['etapes']:
            self.assertEqual(etape['nb_decisions'], 0)
            self.assertIsNone(etape['duree_moyenne_h'])
            self.assertIsNone(etape['taux_rejet'])
            self.assertFalse(etape['goulot'])
        self.assertIsNone(analyse['goulot_ordre'])

    def test_periode_restreint_aux_decisions_du_mois(self):
        wf = _definition_trois_paliers(self.company, 'ntwfl23-periode')
        instance = workflow.demarrer_workflow(
            wf, self.company, self.company, now=self.base)
        step = instance.step_instances.get(ordre=1)
        _figer([step.pk], self.base, 3,
               WorkflowStepInstance.STATUT_APPROUVE)
        step.refresh_from_db()
        mois = f'{step.decided_le:%Y-%m}'

        dedans = analyse_goulots_workflow(self.company, wf.pk, periode=mois)
        self.assertEqual(dedans['etapes'][0]['nb_decisions'], 1)
        self.assertEqual(dedans['periode'], mois)

        autre_mois = step.decided_le - datetime.timedelta(days=90)
        dehors = analyse_goulots_workflow(
            self.company, wf.pk, periode=f'{autre_mois:%Y-%m}')
        self.assertEqual(dehors['etapes'][0]['nb_decisions'], 0)
        self.assertIsNone(dehors['goulot_ordre'])


class AnalyseGoulotsApiTests(TenantAPITestCase):
    """L'endpoint ``core/workflows/{id}/analyse/`` (admin, lecture seule)."""

    def _url(self, definition_id):
        return f'/api/django/core/workflows/{definition_id}/analyse/'

    def test_admin_lit_lanalyse(self):
        wf = _definition_trois_paliers(self.company, 'api-analyse')
        base = timezone.now() - datetime.timedelta(days=2)
        instance = workflow.demarrer_workflow(
            wf, self.company, self.company, now=base)
        _figer([instance.step_instances.get(ordre=2).pk], base, 9,
               WorkflowStepInstance.STATUT_APPROUVE)

        r = self.client_as(role=CustomUser.ROLE_ADMIN).get(self._url(wf.pk))
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual(body['definition_id'], wf.pk)
        self.assertEqual(body['goulot_ordre'], 2)

    def test_definition_dautre_societe_404(self):
        wf = _definition_trois_paliers(self.other_company, 'api-analyse-autre')
        r = self.client_as(role=CustomUser.ROLE_ADMIN).get(self._url(wf.pk))
        self.assertEqual(r.status_code, 404, r.content)

    def test_palier_limite_refuse(self):
        wf = _definition_trois_paliers(self.company, 'api-analyse-refus')
        r = self.client_as(role=CustomUser.ROLE_NORMAL).get(self._url(wf.pk))
        self.assertEqual(r.status_code, 403, r.content)
