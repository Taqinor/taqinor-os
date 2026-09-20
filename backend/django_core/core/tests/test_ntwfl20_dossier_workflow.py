"""Tests NTWFL20 — processus BPM attaché à un dossier transverse.

Acceptance criteria couverte : créer un dossier de type « Onboarding grand
compte » démarre automatiquement le workflow associé à ce type si un modèle
est configuré, et l'étape courante s'affiche sur l'écran dossier.
"""
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company, CustomUser

from core import dossiers as dossiers_service
from core.models import (
    Dossier, WorkflowDefinition, WorkflowInstance, WorkflowStepDefinition,
)
from core.views_dossiers import DossierViewSet

LISTE = DossierViewSet.as_view({'post': 'create'})
DETAIL = DossierViewSet.as_view({'get': 'retrieve'})


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    user, _ = CustomUser.objects.get_or_create(
        username=username,
        defaults={'email': f'{username}@example.test', 'company': company})
    return user


def definition_onboarding(company, actif=True):
    """Le modèle à 4 étapes de l'onboarding grand compte."""
    definition = WorkflowDefinition.objects.create(
        company=company,
        code=dossiers_service.code_definition_pour_type(
            Dossier.TYPE_ONBOARDING_GRAND_COMPTE),
        nom='Onboarding grand compte', actif=actif)
    for ordre, nom in enumerate(
            ['Qualification', 'Revue juridique', 'Validation finance',
             'Mise en service'], start=1):
        WorkflowStepDefinition.objects.create(
            definition=definition, ordre=ordre, nom=nom,
            type_approbation=WorkflowStepDefinition.APPROBATION_MANUELLE)
    return definition


class CodeDefinitionTests(SimpleTestCase):
    """Unité PURE : la convention de code est une seule fonction."""

    def test_prefixe_applique(self):
        self.assertEqual(
            dossiers_service.code_definition_pour_type('onboarding_grand_compte'),
            'dossier_onboarding_grand_compte')


class DemarrageProcessusTests(TestCase):

    def setUp(self):
        self.company = make_company('ntwfl20-co', 'NTWFL20 Co')
        self.user = make_user(self.company, 'ntwfl20-user')

    def _creer(self, type_dossier):
        requete = APIRequestFactory().post('/', {
            'type_dossier': type_dossier,
            'titre': 'Client grand compte Casablanca',
        }, format='json')
        force_authenticate(requete, user=self.user)
        reponse = LISTE(requete)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        return reponse

    def test_creation_demarre_le_processus_du_type_et_expose_letape(self):
        definition = definition_onboarding(self.company)
        instances_avant = WorkflowInstance.objects.filter(
            company=self.company).count()

        reponse = self._creer(Dossier.TYPE_ONBOARDING_GRAND_COMPTE)
        dossier = Dossier.objects.get(pk=reponse.data['id'])

        self.assertEqual(
            WorkflowInstance.objects.filter(company=self.company).count(),
            instances_avant + 1)
        self.assertIsNotNone(dossier.workflow_instance_id)
        instance = dossier.workflow_instance
        self.assertEqual(instance.definition_id, definition.id)
        self.assertEqual(instance.company_id, self.company.id)
        # La cible générique du processus est bien LE dossier.
        self.assertEqual(instance.object_id, dossier.pk)
        self.assertEqual(instance.target, dossier)

        etape = dossiers_service.etape_courante_du_dossier(dossier)
        self.assertIsNotNone(etape)
        self.assertEqual(etape.ordre, 1)
        self.assertEqual(etape.step_def.nom, 'Qualification')

        requete = APIRequestFactory().get('/')
        force_authenticate(requete, user=self.user)
        detail = DETAIL(requete, pk=dossier.pk)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['etape_courante']['nom'],
                         'Qualification')
        self.assertEqual(detail.data['etape_courante']['ordre'], 1)

    def test_sans_modele_configure_aucun_processus(self):
        instances_avant = WorkflowInstance.objects.filter(
            company=self.company).count()

        reponse = self._creer(Dossier.TYPE_RECLAMATION_COMPLEXE)
        dossier = Dossier.objects.get(pk=reponse.data['id'])

        self.assertIsNone(dossier.workflow_instance_id)
        self.assertEqual(
            WorkflowInstance.objects.filter(company=self.company).count(),
            instances_avant)
        self.assertIsNone(
            dossiers_service.etape_courante_du_dossier(dossier))

    def test_modele_inactif_ignore(self):
        definition_onboarding(self.company, actif=False)
        reponse = self._creer(Dossier.TYPE_ONBOARDING_GRAND_COMPTE)
        dossier = Dossier.objects.get(pk=reponse.data['id'])
        self.assertIsNone(dossier.workflow_instance_id)

    def test_modele_dune_autre_societe_jamais_emprunte(self):
        voisine = make_company('ntwfl20-voisine', 'NTWFL20 Voisine')
        definition_onboarding(voisine)

        reponse = self._creer(Dossier.TYPE_ONBOARDING_GRAND_COMPTE)
        dossier = Dossier.objects.get(pk=reponse.data['id'])
        self.assertIsNone(dossier.workflow_instance_id)

    def test_jamais_deux_processus_sur_le_meme_dossier(self):
        definition_onboarding(self.company)
        reponse = self._creer(Dossier.TYPE_ONBOARDING_GRAND_COMPTE)
        dossier = Dossier.objects.get(pk=reponse.data['id'])
        premiere = dossier.workflow_instance_id

        rejeu = dossiers_service.demarrer_processus_si_configure(
            dossier, user=self.user)
        self.assertIsNone(rejeu)
        dossier.refresh_from_db()
        self.assertEqual(dossier.workflow_instance_id, premiere)

    def test_demarrage_journalise_dans_le_chatter(self):
        definition_onboarding(self.company)
        reponse = self._creer(Dossier.TYPE_ONBOARDING_GRAND_COMPTE)
        dossier = Dossier.objects.get(pk=reponse.data['id'])

        champs = [a.field for a in dossier.activites.all()]
        self.assertIn('workflow_instance', champs)
