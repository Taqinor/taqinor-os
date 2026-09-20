"""NTWFL29 — modèles de dossier préconfigurés (« case templates »).

Critère d'acceptation couvert : instancier un modèle « Réclamation complexe »
crée un dossier avec sa checklist par défaut déjà présente, et son workflow
démarré SI un processus est configuré pour le type — en réutilisant
EXACTEMENT le mécanisme NTWFL20 (``core.dossiers.
demarrer_processus_si_configure``), jamais un second moteur."""
from django.db import IntegrityError, transaction
from django.test import TestCase

from authentication.models import Company, CustomUser

from core import dossiers as dossiers_service
from core.models import (
    Dossier, DossierActivity, DossierChecklistItem, DossierModele,
    DossierModeleChecklistItem, WorkflowDefinition, WorkflowStepDefinition,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    user, _ = CustomUser.objects.get_or_create(
        username=username,
        defaults={'email': f'{username}@example.test', 'company': company})
    return user


def definition_onboarding(company, actif=True):
    """Même patron que ``test_ntwfl20_dossier_workflow.definition_onboarding``."""
    definition = WorkflowDefinition.objects.create(
        company=company,
        code=dossiers_service.code_definition_pour_type(
            Dossier.TYPE_ONBOARDING_GRAND_COMPTE),
        nom='Onboarding grand compte', actif=actif)
    WorkflowStepDefinition.objects.create(
        definition=definition, ordre=1, nom='Qualification',
        type_approbation=WorkflowStepDefinition.APPROBATION_MANUELLE)
    return definition


def make_modele(
        company, nom='Réclamation complexe',
        type_dossier=Dossier.TYPE_RECLAMATION_COMPLEXE, checklist=()):
    modele = DossierModele.objects.create(
        company=company, nom=nom, type_dossier=type_dossier)
    for ordre, libelle in enumerate(checklist):
        DossierModeleChecklistItem.objects.create(
            company=company, modele=modele, libelle=libelle, ordre=ordre)
    return modele


class DossierModeleInstancierTests(TestCase):
    def setUp(self):
        self.company = make_company('ntwfl29-co', 'NTWFL29 Co')
        self.user = make_user(self.company, 'ntwfl29-user')

    def test_instancier_cree_un_dossier_du_bon_type(self):
        modele = make_modele(self.company)
        dossier = modele.instancier(user=self.user)
        self.assertIsInstance(dossier, Dossier)
        self.assertEqual(dossier.company_id, self.company.id)
        self.assertEqual(dossier.type_dossier, Dossier.TYPE_RECLAMATION_COMPLEXE)

    def test_titre_par_defaut_est_le_nom_du_modele(self):
        modele = make_modele(self.company, nom='Réclamation complexe')
        dossier = modele.instancier(user=self.user)
        self.assertEqual(dossier.titre, 'Réclamation complexe')

    def test_titre_explicite_prime_sur_le_nom_du_modele(self):
        modele = make_modele(self.company)
        dossier = modele.instancier(titre='Client X — réclamation',
                                    user=self.user)
        self.assertEqual(dossier.titre, 'Client X — réclamation')

    def test_checklist_par_defaut_deja_presente_et_dans_lordre(self):
        modele = make_modele(self.company, checklist=[
            'Accuser réception', 'Qualifier la réclamation',
            'Proposer une résolution',
        ])
        dossier = modele.instancier(user=self.user)

        items = list(DossierChecklistItem.objects.filter(dossier=dossier)
                     .order_by('ordre'))
        self.assertEqual(
            [i.libelle for i in items],
            ['Accuser réception', 'Qualifier la réclamation',
             'Proposer une résolution'])
        self.assertTrue(all(i.company_id == self.company.id for i in items))
        self.assertTrue(all(i.fait is False for i in items))

    def test_instancier_sans_checklist_ne_cree_aucune_etape(self):
        modele = make_modele(self.company)
        dossier = modele.instancier(user=self.user)
        self.assertEqual(
            DossierChecklistItem.objects.filter(dossier=dossier).count(), 0)

    def test_instancier_journalise_la_creation(self):
        modele = make_modele(self.company)
        dossier = modele.instancier(user=self.user)
        kinds = [a.kind for a in dossier.activites.all()]
        self.assertIn(DossierActivity.KIND_CREATION, kinds)

    def test_workflow_demarre_si_un_modele_est_configure_pour_le_type(self):
        definition_onboarding(self.company)
        modele = make_modele(
            self.company, nom='Onboarding grand compte',
            type_dossier=Dossier.TYPE_ONBOARDING_GRAND_COMPTE)

        dossier = modele.instancier(user=self.user)

        self.assertIsNotNone(dossier.workflow_instance_id)
        etape = dossiers_service.etape_courante_du_dossier(dossier)
        self.assertIsNotNone(etape)
        self.assertEqual(etape.ordre, 1)

    def test_aucun_workflow_demarre_sans_modele_configure(self):
        modele = make_modele(self.company)
        dossier = modele.instancier(user=self.user)
        self.assertIsNone(dossier.workflow_instance_id)

    def test_modele_de_workflow_inactif_ignore(self):
        definition_onboarding(self.company, actif=False)
        modele = make_modele(
            self.company, nom='Onboarding grand compte',
            type_dossier=Dossier.TYPE_ONBOARDING_GRAND_COMPTE)
        dossier = modele.instancier(user=self.user)
        self.assertIsNone(dossier.workflow_instance_id)

    def test_instancier_deux_fois_cree_deux_dossiers_distincts(self):
        modele = make_modele(self.company, checklist=['Étape 1'])
        premier = modele.instancier(user=self.user)
        second = modele.instancier(user=self.user)
        self.assertNotEqual(premier.pk, second.pk)
        self.assertEqual(
            DossierChecklistItem.objects.filter(dossier=premier).count(), 1)
        self.assertEqual(
            DossierChecklistItem.objects.filter(dossier=second).count(), 1)


class DossierModeleCatalogueTests(TestCase):
    def setUp(self):
        self.company = make_company('ntwfl29-cat', 'NTWFL29 Catalogue')

    def test_type_dossier_partage_le_catalogue_de_dossier(self):
        champ_modele = DossierModele._meta.get_field('type_dossier')
        champ_dossier = Dossier._meta.get_field('type_dossier')
        self.assertEqual(champ_modele.choices, champ_dossier.choices)

    def test_unicite_par_societe_et_nom(self):
        DossierModele.objects.create(
            company=self.company, nom='Réclamation complexe',
            type_dossier=Dossier.TYPE_RECLAMATION_COMPLEXE)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DossierModele.objects.create(
                    company=self.company, nom='Réclamation complexe',
                    type_dossier=Dossier.TYPE_LITIGE)

    def test_meme_nom_autorise_dans_une_autre_societe(self):
        autre = make_company('ntwfl29-cat-autre', 'NTWFL29 Catalogue Autre')
        DossierModele.objects.create(
            company=self.company, nom='Réclamation complexe',
            type_dossier=Dossier.TYPE_RECLAMATION_COMPLEXE)
        # Ne doit lever aucune exception.
        DossierModele.objects.create(
            company=autre, nom='Réclamation complexe',
            type_dossier=Dossier.TYPE_RECLAMATION_COMPLEXE)
