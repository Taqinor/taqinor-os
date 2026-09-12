"""Tests NTWFL12 — formulaires dynamiques rattachés aux étapes de workflow.

Couvre l'acceptance criteria : une étape avec formulaire bloque
l'approbation tant que les champs requis ne sont pas remplis, un champ
conditionnel apparaît/disparaît selon la règle, une section répétable
capture N lignes.
"""
from django.test import TestCase

from authentication.models import Company
from core import workflow
from core.models import (
    FormulaireDefinition, WorkflowDefinition, WorkflowStepDefinition,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _instance_avec_formulaire(company, schema, champs_conditionnels=None):
    formulaire = FormulaireDefinition.objects.create(
        company=company, code='f1', nom='Formulaire test', schema=schema,
        champs_conditionnels=champs_conditionnels or {})
    wf = WorkflowDefinition.objects.create(
        company=company, code='ntwfl12', nom='NTWFL12')
    WorkflowStepDefinition.objects.create(
        definition=wf, ordre=1, nom='Étape', formulaire=formulaire)
    instance = workflow.demarrer_workflow(wf, company, company)
    return instance, formulaire


class FormulaireBloqueApprobationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl12', 'NTWFL12')

    def test_champ_requis_manquant_bloque_approbation(self):
        instance, _ = _instance_avec_formulaire(self.company, [
            {'nom': 'motif', 'type': 'texte', 'requis': True},
        ])
        with self.assertRaises(ValueError):
            workflow.approuver_etape(instance)

    def test_champ_requis_rempli_debloque_approbation(self):
        instance, _ = _instance_avec_formulaire(self.company, [
            {'nom': 'motif', 'type': 'texte', 'requis': True},
        ])
        step = workflow.etape_courante_de(instance)
        step.donnees_formulaire = {'motif': 'Congé annuel'}
        step.save(update_fields=['donnees_formulaire'])

        workflow.approuver_etape(instance)
        instance.refresh_from_db()
        self.assertEqual(instance.statut, instance.STATUT_TERMINE)

    def test_champ_non_requis_manquant_nempeche_pas(self):
        instance, _ = _instance_avec_formulaire(self.company, [
            {'nom': 'commentaire', 'type': 'texte', 'requis': False},
        ])
        workflow.approuver_etape(instance)  # ne lève pas

    def test_sans_formulaire_comportement_inchange(self):
        wf = WorkflowDefinition.objects.create(
            company=self.company, code='sans-form', nom='Sans formulaire')
        WorkflowStepDefinition.objects.create(definition=wf, ordre=1, nom='Étape')
        instance = workflow.demarrer_workflow(wf, self.company, self.company)
        workflow.approuver_etape(instance)  # ne lève pas

    def test_champ_conditionnel_masque_nest_pas_requis(self):
        # 'justificatif' n'est requis QUE si type == 'exceptionnel'.
        instance, _ = _instance_avec_formulaire(
            self.company,
            schema=[
                {'nom': 'type', 'type': 'choix', 'requis': True},
                {'nom': 'justificatif', 'type': 'texte', 'requis': True},
            ],
            champs_conditionnels={
                'justificatif': {
                    'visible_si': {
                        'field': 'type', 'operator': 'eq', 'value': 'exceptionnel'},
                },
            },
        )
        step = workflow.etape_courante_de(instance)
        step.donnees_formulaire = {'type': 'standard'}
        step.save(update_fields=['donnees_formulaire'])

        # 'justificatif' masqué (type != exceptionnel) : pas bloquant.
        workflow.approuver_etape(instance)
        instance.refresh_from_db()
        self.assertEqual(instance.statut, instance.STATUT_TERMINE)

    def test_champ_conditionnel_visible_est_requis(self):
        instance, _ = _instance_avec_formulaire(
            self.company,
            schema=[
                {'nom': 'type', 'type': 'choix', 'requis': True},
                {'nom': 'justificatif', 'type': 'texte', 'requis': True},
            ],
            champs_conditionnels={
                'justificatif': {
                    'visible_si': {
                        'field': 'type', 'operator': 'eq', 'value': 'exceptionnel'},
                },
            },
        )
        step = workflow.etape_courante_de(instance)
        step.donnees_formulaire = {'type': 'exceptionnel'}  # justificatif manquant
        step.save(update_fields=['donnees_formulaire'])

        with self.assertRaises(ValueError):
            workflow.approuver_etape(instance)

    def test_section_repetable_capture_n_occurrences(self):
        instance, _ = _instance_avec_formulaire(self.company, [
            {'nom': 'lignes', 'type': 'section', 'repetable': True},
        ])
        step = workflow.etape_courante_de(instance)
        step.donnees_formulaire = {
            'lignes': [{'produit': 'A'}, {'produit': 'B'}, {'produit': 'C'}],
        }
        step.save(update_fields=['donnees_formulaire'])
        step.refresh_from_db()
        self.assertEqual(len(step.donnees_formulaire['lignes']), 3)
        # Une section n'est jamais elle-même bloquante (pas de valeur directe).
        workflow.approuver_etape(instance)
