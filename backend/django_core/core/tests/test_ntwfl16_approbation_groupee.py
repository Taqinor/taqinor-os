"""Tests NTWFL16 — approbation groupée « identique » de l'inbox XKB1.

Acceptance criteria couverte :
- sélectionner 5 objets de MÊME type et MÊME palier puis approuver en masse
  crée 5 décisions journalisées DISTINCTES (jamais un seul journal pour N) ;
- un élément dont le formulaire requis (NTWFL12) n'est pas rempli est EXCLU de
  la sélection groupée avec un message explicite ;
- une sélection hétérogène (paliers différents ou types d'objet différents)
  est refusée — aucune approbation « à peu près identique ».
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company, CustomUser
from testkit.base import TenantAPITestCase

from core import workflow
from core.models import (
    FormulaireDefinition, WorkflowDefinition, WorkflowStepDefinition,
    WorkflowStepInstance,
)

URL_MASSE = '/api/django/core/workflows/approuver-en-masse/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _definition(company, code, nb_etapes=2, formulaire=None):
    """Définition à ``nb_etapes`` paliers ; ``formulaire`` sur le palier 1."""
    wf = WorkflowDefinition.objects.create(
        company=company, code=code, nom=code)
    for i in range(1, nb_etapes + 1):
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=i, nom=f'Palier {i}',
            formulaire=(formulaire if i == 1 else None))
    return wf


class ApprobationGroupeeServiceTests(TestCase):
    """Le service ``core.workflow.approuver_en_masse`` (moteur, sans HTTP)."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl16', 'NTWFL16')
        # Cinq CIBLES du MÊME type (contenttypes : des Company, modèle de
        # fondation — ``core`` ne référence aucune app domaine).
        cls.cibles = [
            make_company(f'ntwfl16-cible-{i}', f'Cible {i}') for i in range(5)
        ]
        cls.moment = timezone.now()

    def _cinq_instances(self, code):
        wf = _definition(self.company, code)
        return [
            workflow.demarrer_workflow(
                wf, cible, self.company, now=self.moment)
            for cible in self.cibles
        ]

    def test_cinq_decisions_journalisees_distinctes(self):
        instances = self._cinq_instances('ntwfl16-cinq')
        steps = [workflow.etape_courante_de(i) for i in instances]
        decideur = CustomUser.objects.create_user(
            username='ntwfl16-decideur', password='mdp-73914',
            company=self.company)

        resultat = workflow.approuver_en_masse(
            steps, user=decideur, commentaire='Lot validé en bloc',
            now=self.moment)

        self.assertEqual(len(resultat['decisions']), len(steps))
        self.assertEqual(resultat['exclusions'], [])
        approuvees = WorkflowStepInstance.objects.filter(
            pk__in=[s.pk for s in steps])
        # UNE décision par item : chaque étape porte SON assignee, SON
        # horodatage et SON commentaire (jamais un journal unique pour N).
        self.assertEqual(
            approuvees.filter(
                statut=WorkflowStepInstance.STATUT_APPROUVE,
                assignee=decideur, decided_le=self.moment,
                commentaire='Lot validé en bloc').count(),
            len(steps))
        # Et chaque instance a réellement avancé à son palier 2.
        for instance in instances:
            instance.refresh_from_db()
            self.assertEqual(instance.etape_courante, 2)

    def test_paliers_differents_refuses(self):
        instances = self._cinq_instances('ntwfl16-paliers')
        premier, second = instances[0], instances[1]
        # Fait avancer ``premier`` d'un palier : sa nouvelle étape en attente
        # est au palier 2, alors que ``second`` est encore au palier 1.
        workflow.approuver_etape(premier, now=self.moment)
        steps = [
            workflow.etape_courante_de(premier),
            workflow.etape_courante_de(second),
        ]
        with self.assertRaises(ValueError) as ctx:
            workflow.approuver_en_masse(steps, now=self.moment)
        self.assertIn('palier', str(ctx.exception))

    def test_types_objet_differents_refuses(self):
        wf = _definition(self.company, 'ntwfl16-types')
        # Deux cibles de types DIFFÉRENTS (une Company, une définition de
        # workflow) au MÊME palier → cohortes distinctes.
        instance_a = workflow.demarrer_workflow(
            wf, self.cibles[0], self.company, now=self.moment)
        instance_b = workflow.demarrer_workflow(
            wf, wf, self.company, now=self.moment)
        steps = [
            workflow.etape_courante_de(instance_a),
            workflow.etape_courante_de(instance_b),
        ]
        with self.assertRaises(ValueError) as ctx:
            workflow.approuver_en_masse(steps, now=self.moment)
        self.assertIn("type d'objet", str(ctx.exception))

    def test_formulaire_non_rempli_exclu_avec_motif_explicite(self):
        formulaire = FormulaireDefinition.objects.create(
            company=self.company, code='ntwfl16-quali',
            nom='Qualification', schema=[
                {'nom': 'motif', 'type': 'texte', 'requis': True},
            ])
        wf = _definition(self.company, 'ntwfl16-form', formulaire=formulaire)
        instances = [
            workflow.demarrer_workflow(
                wf, cible, self.company, now=self.moment)
            for cible in self.cibles[:3]
        ]
        steps = [workflow.etape_courante_de(i) for i in instances]
        # Deux items pré-remplis À L'IDENTIQUE, un laissé vide.
        for step in steps[:2]:
            step.donnees_formulaire = {'motif': 'Remise commerciale'}
            step.save(update_fields=['donnees_formulaire'])
        vide = steps[2]

        resultat = workflow.approuver_en_masse(steps, now=self.moment)

        self.assertEqual(
            sorted(s.pk for s in resultat['decisions']),
            sorted(s.pk for s in steps[:2]))
        self.assertEqual(len(resultat['exclusions']), 1)
        exclusion = resultat['exclusions'][0]
        self.assertEqual(exclusion['step_id'], vide.pk)
        self.assertIn('Formulaire requis non complété', exclusion['motif'])
        vide.refresh_from_db()
        self.assertEqual(vide.statut, WorkflowStepInstance.STATUT_EN_ATTENTE)

    def test_formulaire_divergent_exclu(self):
        formulaire = FormulaireDefinition.objects.create(
            company=self.company, code='ntwfl16-div', nom='Divergent',
            schema=[{'nom': 'motif', 'type': 'texte', 'requis': True}])
        wf = _definition(self.company, 'ntwfl16-diverge',
                         formulaire=formulaire)
        instances = [
            workflow.demarrer_workflow(
                wf, cible, self.company, now=self.moment)
            for cible in self.cibles[:2]
        ]
        steps = [workflow.etape_courante_de(i) for i in instances]
        steps[0].donnees_formulaire = {'motif': 'Identique'}
        steps[0].save(update_fields=['donnees_formulaire'])
        steps[1].donnees_formulaire = {'motif': 'Autre réponse'}
        steps[1].save(update_fields=['donnees_formulaire'])

        resultat = workflow.approuver_en_masse(steps, now=self.moment)

        self.assertEqual([s.pk for s in resultat['decisions']], [steps[0].pk])
        self.assertEqual(len(resultat['exclusions']), 1)
        self.assertIn('Formulaire différent',
                      resultat['exclusions'][0]['motif'])

    def test_selection_vide_refusee(self):
        with self.assertRaises(ValueError):
            workflow.approuver_en_masse([], now=self.moment)

    def test_etape_deja_decidee_exclue(self):
        instances = self._cinq_instances('ntwfl16-decidee')
        steps = [workflow.etape_courante_de(i) for i in instances[:2]]
        workflow.approuver_etape(
            instances[0], now=self.moment - datetime.timedelta(hours=1))
        steps[0].refresh_from_db()

        resultat = workflow.approuver_en_masse(steps, now=self.moment)

        self.assertEqual([s.pk for s in resultat['decisions']], [steps[1].pk])
        self.assertIn("plus en attente", resultat['exclusions'][0]['motif'])


class ApprobationGroupeeApiTests(TenantAPITestCase):
    """L'endpoint ``core/workflows/approuver-en-masse/`` (scoping + refus)."""

    def _steps(self, company, code, nb=3):
        wf = _definition(company, code)
        cibles = [
            make_company(f'{code}-cible-{i}', f'Cible {code} {i}')
            for i in range(nb)
        ]
        instances = [
            workflow.demarrer_workflow(wf, cible, company) for cible in cibles
        ]
        return [workflow.etape_courante_de(i) for i in instances]

    def test_approuve_le_lot_et_journalise_par_item(self):
        steps = self._steps(self.company, 'api-ok')
        r = self.client_as(role=CustomUser.ROLE_ADMIN).post(
            URL_MASSE,
            {'step_ids': [s.pk for s in steps], 'commentaire': 'OK lot'},
            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(sorted(r.json()['approuves']),
                         sorted(s.pk for s in steps))
        self.assertEqual(
            WorkflowStepInstance.objects.filter(
                pk__in=[s.pk for s in steps],
                statut=WorkflowStepInstance.STATUT_APPROUVE,
                commentaire='OK lot').count(),
            len(steps))

    def test_etape_dune_autre_societe_introuvable(self):
        autres = self._steps(self.other_company, 'api-autre')
        r = self.client_as(role=CustomUser.ROLE_ADMIN).post(
            URL_MASSE, {'step_ids': [s.pk for s in autres]}, format='json')
        self.assertEqual(r.status_code, 404, r.content)
        for step in autres:
            step.refresh_from_db()
            self.assertEqual(step.statut,
                             WorkflowStepInstance.STATUT_EN_ATTENTE)

    def test_step_ids_manquant_refuse(self):
        r = self.client_as(role=CustomUser.ROLE_ADMIN).post(
            URL_MASSE, {'commentaire': 'rien'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_selection_heterogene_refusee_avec_message(self):
        steps = self._steps(self.company, 'api-hetero', nb=2)
        instance = steps[0].instance
        workflow.approuver_etape(instance)
        palier2 = workflow.etape_courante_de(instance)
        r = self.client_as(role=CustomUser.ROLE_ADMIN).post(
            URL_MASSE, {'step_ids': [palier2.pk, steps[1].pk]}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('palier', r.json()['detail'])
