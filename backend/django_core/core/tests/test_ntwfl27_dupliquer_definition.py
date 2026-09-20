"""Tests NTWFL27 — duplication d'une définition de processus (portabilité).

Acceptance criteria couverte : dupliquer une définition à 4 étapes + 1
formulaire crée une copie INDÉPENDANTE éditable sans affecter l'originale.
"""
from django.test import TestCase

from authentication.models import Company, CustomUser
from testkit.base import TenantAPITestCase

from core.models import (
    FormulaireDefinition, WorkflowDefinition, WorkflowStepDefinition,
)
from core.workflow_templates import dupliquer_definition_workflow


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


SCHEMA_SOURCE = [
    {'nom': 'motif', 'type': 'texte', 'requis': True},
    {'nom': 'montant', 'type': 'nombre', 'requis': False},
]


def _definition_quatre_etapes(company, code='processus-source'):
    """Définition à 4 étapes dont la 2ᵉ porte un formulaire dynamique."""
    formulaire = FormulaireDefinition.objects.create(
        company=company, code=f'{code}-form', nom='Qualification',
        schema=[dict(champ) for champ in SCHEMA_SOURCE],
        champs_conditionnels={
            'montant': {'visible_si': {'operateur': 'ET', 'regles': []}},
        })
    definition = WorkflowDefinition.objects.create(
        company=company, code=code, nom='Processus source',
        description='Chaîne personnalisée par la société', actif=True)
    WorkflowStepDefinition.objects.create(
        definition=definition, ordre=1, nom='Vérification',
        type_approbation=WorkflowStepDefinition.APPROBATION_MANUELLE,
        sla_heures=24, role_requis='Responsable')
    WorkflowStepDefinition.objects.create(
        definition=definition, ordre=2, nom='Qualification',
        type_approbation=WorkflowStepDefinition.APPROBATION_MANUELLE,
        sla_heures=48, role_requis='Commercial', formulaire=formulaire,
        calendrier_ouvre=True)
    WorkflowStepDefinition.objects.create(
        definition=definition, ordre=3, nom='Contrôle parallèle A',
        type_approbation=WorkflowStepDefinition.APPROBATION_ROLE,
        role_requis='Responsable', groupe_parallele=1)
    WorkflowStepDefinition.objects.create(
        definition=definition, ordre=4, nom='Contrôle parallèle B',
        type_approbation=WorkflowStepDefinition.APPROBATION_ROLE,
        role_requis='Administrateur', groupe_parallele=1,
        escalade_vers='Directeur')
    return definition, formulaire


class DuplicationDefinitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl27', 'NTWFL27')

    def test_copie_porte_les_memes_etapes_en_brouillon(self):
        source, _ = _definition_quatre_etapes(self.company)
        copie = dupliquer_definition_workflow(source)

        self.assertNotEqual(copie.pk, source.pk)
        self.assertEqual(copie.company_id, source.company_id)
        self.assertFalse(copie.actif)  # brouillon : jamais démarrable d'emblée
        self.assertTrue(source.actif)
        self.assertEqual(copie.code, f'{source.code}-copie')
        self.assertIn('(copie)', copie.nom)
        self.assertEqual(copie.steps.count(), source.steps.count())

        attendus = [
            (s.ordre, s.nom, s.type_approbation, s.sla_heures, s.role_requis,
             s.escalade_vers, s.calendrier_ouvre, s.groupe_parallele)
            for s in source.steps.order_by('ordre')
        ]
        obtenus = [
            (s.ordre, s.nom, s.type_approbation, s.sla_heures, s.role_requis,
             s.escalade_vers, s.calendrier_ouvre, s.groupe_parallele)
            for s in copie.steps.order_by('ordre')
        ]
        self.assertEqual(obtenus, attendus)

    def test_formulaire_est_copie_et_independant(self):
        source, formulaire = _definition_quatre_etapes(self.company)
        copie = dupliquer_definition_workflow(source)

        etape_copiee = copie.steps.get(ordre=2)
        self.assertIsNotNone(etape_copiee.formulaire)
        # Formulaire COPIÉ, pas partagé : éditer la copie ne touche pas
        # l'original.
        self.assertNotEqual(etape_copiee.formulaire_id, formulaire.pk)
        self.assertEqual(etape_copiee.formulaire.schema, SCHEMA_SOURCE)
        self.assertEqual(etape_copiee.formulaire.champs_conditionnels,
                         formulaire.champs_conditionnels)

        etape_copiee.formulaire.schema.append(
            {'nom': 'nouveau', 'type': 'texte', 'requis': False})
        etape_copiee.formulaire.save(update_fields=['schema'])
        formulaire.refresh_from_db()
        self.assertEqual(formulaire.schema, SCHEMA_SOURCE)

    def test_editer_la_copie_naffecte_pas_loriginale(self):
        source, _ = _definition_quatre_etapes(self.company)
        copie = dupliquer_definition_workflow(source)

        etape = copie.steps.get(ordre=1)
        etape.nom = 'Vérification allégée'
        etape.sla_heures = 4
        etape.save(update_fields=['nom', 'sla_heures'])
        copie.steps.filter(ordre=4).delete()

        origine_etape = source.steps.get(ordre=1)
        self.assertEqual(origine_etape.nom, 'Vérification')
        self.assertEqual(origine_etape.sla_heures, 24)
        self.assertEqual(source.steps.count(), 4)
        self.assertEqual(copie.steps.count(), 3)

    def test_deuxieme_duplication_suffixe_incremente(self):
        source, _ = _definition_quatre_etapes(self.company)
        premiere = dupliquer_definition_workflow(source)
        seconde = dupliquer_definition_workflow(source)

        self.assertEqual(premiere.code, f'{source.code}-copie')
        self.assertEqual(seconde.code, f'{source.code}-copie-2')
        self.assertNotEqual(
            premiere.steps.get(ordre=2).formulaire_id,
            seconde.steps.get(ordre=2).formulaire_id)

    def test_code_long_garde_le_marqueur_et_respecte_la_longueur(self):
        longueur_max = WorkflowDefinition._meta.get_field('code').max_length
        source = WorkflowDefinition.objects.create(
            company=self.company, code='x' * longueur_max, nom='Code maximal')
        WorkflowStepDefinition.objects.create(
            definition=source, ordre=1, nom='Étape')
        copie = dupliquer_definition_workflow(source)
        self.assertLessEqual(len(copie.code), longueur_max)
        self.assertTrue(copie.code.endswith('-copie'))

    def test_formulaire_partage_par_deux_etapes_copie_une_seule_fois(self):
        formulaire = FormulaireDefinition.objects.create(
            company=self.company, code='ntwfl27-partage', nom='Partagé',
            schema=[{'nom': 'motif', 'type': 'texte', 'requis': True}])
        source = WorkflowDefinition.objects.create(
            company=self.company, code='ntwfl27-deux', nom='Deux étapes')
        for ordre in (1, 2):
            WorkflowStepDefinition.objects.create(
                definition=source, ordre=ordre, nom=f'Étape {ordre}',
                formulaire=formulaire)

        copie = dupliquer_definition_workflow(source)
        ids = {s.formulaire_id for s in copie.steps.all()}
        self.assertEqual(len(ids), 1)
        self.assertNotIn(formulaire.pk, ids)


class DuplicationDefinitionApiTests(TenantAPITestCase):
    """``POST core/workflow-definitions/{id}/dupliquer/``."""

    def _url(self, definition_id):
        return (f'/api/django/core/workflow-definitions/'
                f'{definition_id}/dupliquer/')

    def test_admin_duplique(self):
        source, _ = _definition_quatre_etapes(self.company, 'api-source')
        r = self.client_as(role=CustomUser.ROLE_ADMIN).post(
            self._url(source.pk), {}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertNotEqual(body['id'], source.pk)
        self.assertFalse(body['actif'])
        self.assertEqual(len(body['steps']), source.steps.count())

    def test_definition_dautre_societe_introuvable(self):
        source, _ = _definition_quatre_etapes(
            self.other_company, 'api-source-autre')
        avant = WorkflowDefinition.objects.filter(
            company=self.other_company).count()
        r = self.client_as(role=CustomUser.ROLE_ADMIN).post(
            self._url(source.pk), {}, format='json')
        self.assertEqual(r.status_code, 404, r.content)
        self.assertEqual(
            WorkflowDefinition.objects.filter(
                company=self.other_company).count(), avant)

    def test_palier_limite_refuse(self):
        source, _ = _definition_quatre_etapes(self.company, 'api-source-refus')
        avant = WorkflowDefinition.objects.filter(
            company=self.company).count()
        r = self.client_as(role=CustomUser.ROLE_NORMAL).post(
            self._url(source.pk), {}, format='json')
        self.assertEqual(r.status_code, 403, r.content)
        self.assertEqual(
            WorkflowDefinition.objects.filter(company=self.company).count(),
            avant)
