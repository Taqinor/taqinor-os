"""Tests NTWFL7 — garde de transition (branche simple) sur une étape auto.

Couvre l'acceptance criteria : une étape avec garde « montant > 100 000 »
ne s'auto-avance PAS si le montant de la cible est inférieur, route vers
l'étape alternative configurée ; sans garde, comportement identique à
avant ; sans alternative valide, l'étape reste EN ATTENTE plutôt que de
planter ou d'avancer quand même.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from core import workflow
from core.models import (
    PaymentTransaction, WorkflowDefinition, WorkflowInstance,
    WorkflowStepDefinition, WorkflowStepInstance,
)

GARDE_MONTANT_100K = {'field': 'montant', 'operator': 'gt', 'value': 100000}


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_cible(company, montant):
    return PaymentTransaction.objects.create(company=company, montant=montant)


class GardeTransitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl7', 'NTWFL7')

    def _definition_avec_garde(self, code):
        wf = WorkflowDefinition.objects.create(
            company=self.company, code=code, nom='NTWFL7')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Auto-si-gros-montant',
            type_approbation=WorkflowStepDefinition.APPROBATION_AUTO,
            condition_transition=GARDE_MONTANT_100K,
            etape_alternative_si_echec=2)
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=2, nom='Alternative (petit montant)')
        return wf

    def test_garde_verifiee_auto_avance_normalement(self):
        wf = self._definition_avec_garde('ntwfl7-ok')
        cible = make_cible(self.company, Decimal('150000'))
        instance = workflow.demarrer_workflow(wf, cible, self.company)

        instance.refresh_from_db()
        etape1 = instance.step_instances.get(ordre=1)
        self.assertEqual(etape1.statut, WorkflowStepInstance.STATUT_APPROUVE)
        # Auto-approuvée → avance normalement à l'étape 2 (pas ignorée).
        self.assertEqual(instance.etape_courante, 2)
        etape2 = instance.step_instances.get(ordre=2)
        self.assertEqual(etape2.statut, WorkflowStepInstance.STATUT_EN_ATTENTE)

    def test_garde_echoue_route_vers_alternative(self):
        wf = self._definition_avec_garde('ntwfl7-route')
        cible = make_cible(self.company, Decimal('1000'))  # < 100 000
        instance = workflow.demarrer_workflow(wf, cible, self.company)

        instance.refresh_from_db()
        etape1 = instance.step_instances.get(ordre=1)
        self.assertEqual(etape1.statut, WorkflowStepInstance.STATUT_IGNOREE)
        self.assertEqual(instance.etape_courante, 2)
        etape2 = instance.step_instances.get(ordre=2)
        self.assertEqual(etape2.statut, WorkflowStepInstance.STATUT_EN_ATTENTE)
        self.assertEqual(instance.statut, WorkflowInstance.STATUT_EN_COURS)

    def test_sans_alternative_reste_en_attente(self):
        wf = WorkflowDefinition.objects.create(
            company=self.company, code='ntwfl7-sans-alt', nom='Sans alt')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Auto sans alternative',
            type_approbation=WorkflowStepDefinition.APPROBATION_AUTO,
            condition_transition=GARDE_MONTANT_100K)
        cible = make_cible(self.company, Decimal('1'))

        instance = workflow.demarrer_workflow(wf, cible, self.company)

        instance.refresh_from_db()
        etape1 = instance.step_instances.get(ordre=1)
        self.assertEqual(etape1.statut, WorkflowStepInstance.STATUT_EN_ATTENTE)
        self.assertEqual(instance.etape_courante, 1)
        self.assertEqual(instance.statut, WorkflowInstance.STATUT_EN_COURS)

    def test_sans_garde_comportement_inchange(self):
        wf = WorkflowDefinition.objects.create(
            company=self.company, code='ntwfl7-sans-garde', nom='Sans garde')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Auto sans garde',
            type_approbation=WorkflowStepDefinition.APPROBATION_AUTO)
        cible = make_cible(self.company, Decimal('1'))

        instance = workflow.demarrer_workflow(wf, cible, self.company)

        instance.refresh_from_db()
        etape1 = instance.step_instances.get(ordre=1)
        self.assertEqual(etape1.statut, WorkflowStepInstance.STATUT_APPROUVE)
        self.assertEqual(instance.statut, WorkflowInstance.STATUT_TERMINE)
