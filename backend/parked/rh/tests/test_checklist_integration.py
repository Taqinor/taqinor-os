"""Tests XRH4 — checklist d'intégration (onboarding) du nouvel embauché.

Couvre :
* l'embauche via l'ATS (``services.embaucher``) instancie automatiquement la
  checklist du modèle le plus spécifique (poste+département > poste >
  département > défaut), ou rien si aucun modèle n'est configuré ;
* ``services.instancier_integration`` est idempotent (n'instancie pas 2 fois) ;
* l'endpoint ``employes/{id}/instancier-integration`` (manuel) ;
* la progression % exposée par ``employes/{id}/integration`` ;
* cocher/décocher est journalisé (``fait_par``/``date`` posés côté serveur) ;
* isolation multi-société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.rh import services
from apps.rh.models import (
    Departement,
    DossierEmploye,
    ElementIntegration,
    ElementIntegrationEmploye,
    ModeleIntegration,
    Poste,
)

User = get_user_model()

EMPLOYES = '/api/django/rh/employes/'
ELEMENTS_EMP = '/api/django/rh/elements-integration-employe/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_modele(company, nom='Standard', **kwargs):
    return ModeleIntegration.objects.create(company=company, nom=nom, **kwargs)


def make_elements(modele, libelles):
    for i, lib in enumerate(libelles):
        ElementIntegration.objects.create(
            company=modele.company, modele=modele, libelle=lib, ordre=i)


class InstancierIntegrationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('int-a', 'A')
        self.poste = Poste.objects.create(company=self.co, intitule='Poseur')
        self.dep = Departement.objects.create(company=self.co, nom='Prod')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='X', prenom='Y',
            poste_ref=self.poste, departement=self.dep)

    def test_modele_specifique_poste_et_departement_prioritaire(self):
        general = make_modele(self.co, 'Général')
        make_elements(general, ['A', 'B'])
        specifique = make_modele(
            self.co, 'Poseur Prod', poste_ref=self.poste,
            departement=self.dep)
        make_elements(specifique, ['C1', 'C2', 'C3'])
        lignes = services.instancier_integration(self.emp)
        # XRH5 : + 1 item bloquant (déclaration d'entrée CNSS/AMO), toujours
        # ajouté quand aucune ligne du modèle ne le porte déjà.
        self.assertEqual(len(lignes), 4)
        libelles = {ligne.libelle for ligne in lignes}
        self.assertTrue({'C1', 'C2', 'C3'}.issubset(libelles))

    def test_modele_par_defaut_si_aucun_specifique(self):
        defaut = make_modele(self.co, 'Défaut')
        make_elements(defaut, ['Contrat signé', 'CIN/RIB collectés'])
        lignes = services.instancier_integration(self.emp)
        self.assertEqual(len(lignes), 3)

    def test_aucun_modele_ne_leve_pas_erreur(self):
        # XRH5 : même sans modèle configuré, l'item bloquant (déclaration
        # d'entrée CNSS/AMO) est toujours créé — jamais d'exception.
        lignes = services.instancier_integration(self.emp)
        self.assertEqual(len(lignes), 1)
        self.assertIn('CNSS', lignes[0].libelle)

    def test_idempotent_ne_duplique_pas(self):
        modele = make_modele(self.co, 'Standard')
        make_elements(modele, ['A', 'B'])
        services.instancier_integration(self.emp)
        services.instancier_integration(self.emp)
        # XRH5 : + 1 item bloquant (déclaration d'entrée CNSS/AMO), toujours
        # ajouté par le premier appel — le second appel doit rester
        # idempotent et ne rien dupliquer.
        self.assertEqual(
            ElementIntegrationEmploye.objects.filter(employe=self.emp).count(),
            3)

    def test_embaucher_instancie_checklist_automatiquement(self):
        from apps.rh.models import Candidature, OuverturePoste

        modele = make_modele(
            self.co, 'Onboarding poseur', poste_ref=self.poste)
        make_elements(modele, ['Contrat', 'CNSS', 'EPI'])
        ouverture = OuverturePoste.objects.create(
            company=self.co, intitule='Poseur', poste_ref=self.poste,
            nombre_postes=1)
        cand = Candidature.objects.create(
            company=self.co, ouverture=ouverture, nom='Karim Bennani')
        dossier = services.embaucher(cand)
        lignes = ElementIntegrationEmploye.objects.filter(employe=dossier)
        # XRH5 : + 1 item bloquant (déclaration d'entrée CNSS/AMO).
        self.assertEqual(lignes.count(), 4)


class IntegrationApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('int-api-a', 'A')
        self.co_b = make_company('int-api-b', 'B')
        self.user_a = make_user(self.co_a, 'int-api-a')
        self.user_b = make_user(self.co_b, 'int-api-b')
        self.emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='E1', nom='X', prenom='Y')

    def test_instancier_integration_endpoint(self):
        modele = make_modele(self.co_a)
        make_elements(modele, ['A', 'B', 'C'])
        resp = auth(self.user_a).post(
            f'{EMPLOYES}{self.emp.id}/instancier-integration/')
        self.assertEqual(resp.status_code, 201, resp.data)
        # XRH5 : + 1 item bloquant (déclaration d'entrée CNSS/AMO).
        self.assertEqual(len(resp.data), 4)

    def test_progression_pct(self):
        for i in range(4):
            ElementIntegrationEmploye.objects.create(
                company=self.co_a, employe=self.emp, libelle=f'L{i}',
                fait=(i < 1))
        resp = auth(self.user_a).get(
            f'{EMPLOYES}{self.emp.id}/integration/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], 4)
        self.assertEqual(resp.data['faits'], 1)
        self.assertEqual(resp.data['progression_pct'], 25)

    def test_cocher_journalise_fait_par_et_date(self):
        ligne = ElementIntegrationEmploye.objects.create(
            company=self.co_a, employe=self.emp, libelle='Contrat signé')
        resp = auth(self.user_a).patch(
            f'{ELEMENTS_EMP}{ligne.id}/', {'fait': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne.refresh_from_db()
        self.assertTrue(ligne.fait)
        self.assertEqual(ligne.fait_par_id, self.user_a.id)
        self.assertIsNotNone(ligne.date)

    def test_decocher_efface_fait_par_et_date(self):
        ligne = ElementIntegrationEmploye.objects.create(
            company=self.co_a, employe=self.emp, libelle='Contrat signé',
            fait=True, fait_par=self.user_a)
        resp = auth(self.user_a).patch(
            f'{ELEMENTS_EMP}{ligne.id}/', {'fait': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne.refresh_from_db()
        self.assertFalse(ligne.fait)
        self.assertIsNone(ligne.fait_par)
        self.assertIsNone(ligne.date)

    def test_isolation_tenant_cross_company_404(self):
        resp = auth(self.user_b).get(
            f'{EMPLOYES}{self.emp.id}/integration/')
        self.assertEqual(resp.status_code, 404)
