"""Tests NTWFL25 — versionnement des définitions + migration d'instance.

Acceptance criteria couverte : modifier les étapes d'une définition avec 3
instances actives crée v2 sans toucher aux instances existantes ; une
migration MANUELLE explicite déplace une instance choisie vers v2 avec un
mapping d'étape validé ; et « aucune instance active → mutation en place
autorisée » (compatibilité rétroactive).
"""
from django.test import TestCase

from authentication.models import Company, CustomUser

from core import workflow
from core.models import (
    WorkflowDefinition, WorkflowInstance, WorkflowStepDefinition,
    WorkflowStepInstance,
)

ETAPES_V1 = [
    {'nom': 'Chef de service',
     'type_approbation': WorkflowStepDefinition.APPROBATION_MANUELLE},
    {'nom': 'Direction',
     'type_approbation': WorkflowStepDefinition.APPROBATION_MANUELLE},
    {'nom': 'Finance',
     'type_approbation': WorkflowStepDefinition.APPROBATION_MANUELLE},
]

ETAPES_V2 = [
    {'nom': 'Chef de service',
     'type_approbation': WorkflowStepDefinition.APPROBATION_MANUELLE},
    {'nom': 'Contrôle interne',
     'type_approbation': WorkflowStepDefinition.APPROBATION_MANUELLE},
    {'nom': 'Direction',
     'type_approbation': WorkflowStepDefinition.APPROBATION_MANUELLE},
    {'nom': 'Finance',
     'type_approbation': WorkflowStepDefinition.APPROBATION_MANUELLE},
]


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    user, _ = CustomUser.objects.get_or_create(
        username=username,
        defaults={'email': f'{username}@example.test', 'company': company})
    return user


def definition_trois_paliers(company, code='validation_devis'):
    definition = WorkflowDefinition.objects.create(
        company=company, code=code, nom='Validation devis', actif=True)
    for ordre, etape in enumerate(ETAPES_V1, start=1):
        WorkflowStepDefinition.objects.create(
            definition=definition, ordre=ordre, **etape)
    return definition


class ForkSurInstancesActivesTests(TestCase):

    def setUp(self):
        self.company = make_company('ntwfl25-fork', 'NTWFL25 Fork')
        self.user = make_user(self.company, 'ntwfl25-user')
        self.definition = definition_trois_paliers(self.company)
        # Trois instances actives, chacune sur une cible différente.
        self.cibles = [
            make_company(f'ntwfl25-cible-{i}', f'NTWFL25 Cible {i}')
            for i in range(3)
        ]
        self.instances = [
            workflow.demarrer_workflow(
                self.definition, cible, self.company, user=self.user)
            for cible in self.cibles
        ]

    def test_instance_est_epinglee_a_sa_version(self):
        for instance in self.instances:
            self.assertEqual(instance.definition_version, 1)
            self.assertEqual(instance.definition_id, self.definition.id)

    def test_edition_structurelle_forke_v2_et_ne_touche_pas_les_instances(self):
        etapes_v1_avant = [
            (s.ordre, s.nom)
            for s in self.definition.steps.order_by('ordre')
        ]
        definitions_avant = WorkflowDefinition.objects.filter(
            company=self.company, code=self.definition.code).count()

        v2, forkee = workflow.editer_etapes_definition(
            self.definition, ETAPES_V2)

        self.assertTrue(forkee)
        self.assertNotEqual(v2.pk, self.definition.pk)
        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.code, self.definition.code)
        self.assertEqual(v2.definition_precedente_id, self.definition.pk)
        self.assertTrue(v2.actif)
        self.assertEqual(
            WorkflowDefinition.objects.filter(
                company=self.company, code=self.definition.code).count(),
            definitions_avant + 1)
        self.assertEqual(
            [(s.ordre, s.nom) for s in v2.steps.order_by('ordre')],
            [(1, 'Chef de service'), (2, 'Contrôle interne'),
             (3, 'Direction'), (4, 'Finance')])

        # v1 est intacte, juste désactivée : plus rien ne démarre dessus.
        self.definition.refresh_from_db()
        self.assertFalse(self.definition.actif)
        self.assertEqual(
            [(s.ordre, s.nom)
             for s in self.definition.steps.order_by('ordre')],
            etapes_v1_avant)

        # Les trois instances n'ont PAS bougé.
        for instance in self.instances:
            instance.refresh_from_db()
            self.assertEqual(instance.definition_id, self.definition.pk)
            self.assertEqual(instance.definition_version, 1)
            self.assertEqual(instance.step_instances.count(),
                             len(ETAPES_V1))

    def test_nouvelle_instance_demarre_sur_la_derniere_version_active(self):
        v2, _ = workflow.editer_etapes_definition(self.definition, ETAPES_V2)

        derniere = workflow.derniere_version_active(
            self.company, self.definition.code)
        self.assertEqual(derniere.pk, v2.pk)

        cible = make_company('ntwfl25-nouvelle', 'NTWFL25 Nouvelle')
        instance = workflow.demarrer_workflow(
            derniere, cible, self.company, user=self.user)
        self.assertEqual(instance.definition_version, 2)
        self.assertEqual(instance.step_instances.count(), len(ETAPES_V2))

    def test_mutation_en_place_sans_instance(self):
        """Compat rétroactive : une définition jamais jouée mute en place."""
        vierge = definition_trois_paliers(self.company, code='brouillon_libre')
        self.assertFalse(workflow.a_des_instances_actives(vierge))
        definitions_avant = WorkflowDefinition.objects.filter(
            company=self.company, code='brouillon_libre').count()

        cible, forkee = workflow.editer_etapes_definition(vierge, ETAPES_V2)

        self.assertFalse(forkee)
        self.assertEqual(cible.pk, vierge.pk)
        self.assertEqual(cible.version, 1)
        self.assertEqual(
            WorkflowDefinition.objects.filter(
                company=self.company, code='brouillon_libre').count(),
            definitions_avant)
        self.assertEqual(
            [s.nom for s in cible.steps.order_by('ordre')],
            [e['nom'] for e in ETAPES_V2])


class MigrationManuelleTests(TestCase):

    def setUp(self):
        self.company = make_company('ntwfl25-migr', 'NTWFL25 Migration')
        self.user = make_user(self.company, 'ntwfl25-migr-user')
        self.definition = definition_trois_paliers(self.company)
        self.cible = make_company('ntwfl25-migr-cible', 'NTWFL25 Cible')
        self.instance = workflow.demarrer_workflow(
            self.definition, self.cible, self.company, user=self.user)
        # Le premier palier est approuvé : l'instance attend au palier 2.
        workflow.approuver_etape(
            self.instance, user=self.user, commentaire='OK service')
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.etape_courante, 2)

        self.v2, _ = workflow.editer_etapes_definition(
            self.definition, ETAPES_V2)

    def test_migration_explicite_deplace_linstance_et_garde_les_decisions(self):
        etapes_avant = self.instance.step_instances.count()

        workflow.migrer_instance_vers_version(
            self.instance, self.v2,
            # v1 palier 1 → v2 palier 1 ; v1 palier 2 → v2 palier 3 (« Contrôle
            # interne » s'insère avant) ; v1 palier 3 → v2 palier 4.
            {1: 1, 2: 3, 3: 4})

        self.instance.refresh_from_db()
        self.assertEqual(self.instance.definition_id, self.v2.pk)
        self.assertEqual(self.instance.definition_version, 2)
        self.assertEqual(self.instance.etape_courante, 3)
        self.assertEqual(self.instance.step_instances.count(),
                         len(ETAPES_V2))
        self.assertGreater(self.instance.step_instances.count(),
                           etapes_avant)

        par_ordre = {s.ordre: s
                     for s in self.instance.step_instances.all()}
        # La décision déjà prise est conservée, re-pointée sur v2.
        self.assertEqual(par_ordre[1].statut,
                         WorkflowStepInstance.STATUT_APPROUVE)
        self.assertEqual(par_ordre[1].commentaire, 'OK service')
        self.assertEqual(par_ordre[1].step_def.definition_id, self.v2.pk)
        # L'étape neuve de v2 est en attente.
        self.assertEqual(par_ordre[2].statut,
                         WorkflowStepInstance.STATUT_EN_ATTENTE)
        self.assertEqual(par_ordre[2].step_def.nom, 'Contrôle interne')
        # Toutes les étapes pointent bien la version cible.
        for step in par_ordre.values():
            self.assertEqual(step.step_def.definition_id, self.v2.pk)
            self.assertEqual(step.company_id, self.company.id)

    def test_migration_refusee_sans_mapping(self):
        for mapping in [None, {}, 'nimporte quoi']:
            with self.assertRaises(ValueError):
                workflow.migrer_instance_vers_version(
                    self.instance, self.v2, mapping)
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.definition_id, self.definition.pk)

    def test_migration_refusee_si_etape_courante_absente_du_mapping(self):
        with self.assertRaises(ValueError) as ctx:
            workflow.migrer_instance_vers_version(
                self.instance, self.v2, {1: 1, 3: 4})
        self.assertIn('étape courante', str(ctx.exception))
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.definition_id, self.definition.pk)

    def test_migration_refusee_si_decision_non_mappee(self):
        with self.assertRaises(ValueError) as ctx:
            workflow.migrer_instance_vers_version(
                self.instance, self.v2, {2: 3, 3: 4})
        self.assertIn('décidées', str(ctx.exception))

    def test_migration_refusee_vers_etape_inexistante(self):
        with self.assertRaises(ValueError) as ctx:
            workflow.migrer_instance_vers_version(
                self.instance, self.v2, {1: 1, 2: 9, 3: 4})
        self.assertIn('version cible', str(ctx.exception))

    def test_migration_refusee_vers_une_autre_lignee(self):
        etrangere = definition_trois_paliers(
            self.company, code='autre_processus')
        with self.assertRaises(ValueError) as ctx:
            workflow.migrer_instance_vers_version(
                self.instance, etrangere, {1: 1, 2: 2, 3: 3})
        self.assertIn('lignée', str(ctx.exception))

    def test_migration_refusee_sur_instance_terminee(self):
        self.instance.statut = WorkflowInstance.STATUT_TERMINE
        self.instance.save(update_fields=['statut'])
        with self.assertRaises(ValueError) as ctx:
            workflow.migrer_instance_vers_version(
                self.instance, self.v2, {1: 1, 2: 3, 3: 4})
        self.assertIn('EN COURS', str(ctx.exception))

    def test_migration_refusee_vers_deux_fois_la_meme_etape(self):
        with self.assertRaises(ValueError) as ctx:
            workflow.migrer_instance_vers_version(
                self.instance, self.v2, {1: 1, 2: 4, 3: 4})
        self.assertIn('même étape', str(ctx.exception))
