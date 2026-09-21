"""Tests ZRH7 — Gabarits de questions d'évaluation réutilisables.

Une ``EvaluationEmploye`` créée dans une campagne portant un ``modele``
instancie ``reponses`` depuis les questions du modèle (défaut le modèle du
département/poste de l'employé, sinon le modèle par défaut société). CRUD
modèles company-scopé.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    CampagneEvaluation, Departement, DossierEmploye, EvaluationEmploye,
    ModeleEvaluation,
)

User = get_user_model()

MODELES_URL = '/api/django/rh/modeles-evaluation/'
CAMP_URL = '/api/django/rh/campagnes-evaluation/'
EVAL_URL = '/api/django/rh/evaluations-employe/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, departement=None):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P',
        departement=departement)


def make_campagne(company, modele=None):
    return CampagneEvaluation.objects.create(
        company=company, intitule='Campagne 2026', annee=2026, modele=modele)


def make_modele(company, nom, departement=None, questions=None):
    return ModeleEvaluation.objects.create(
        company=company, nom=nom, departement=departement,
        questions=questions or [
            {'libelle': 'Autonomie', 'type': 'note1-5', 'cible': 'manager'},
            {'libelle': 'Commentaire libre', 'type': 'texte',
             'cible': 'employe'},
        ])


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class InstancierReponsesServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('zrh7-a', 'A')
        self.dep = Departement.objects.create(company=self.company, nom='Dep1')

    def test_modele_explicite_campagne(self):
        modele = make_modele(self.company, 'Modele campagne')
        campagne = make_campagne(self.company, modele=modele)
        employe = make_employe(self.company, 'ZRH7-1')
        reponses = services.instancier_reponses_evaluation(campagne, employe)
        self.assertEqual(len(reponses), 2)
        self.assertEqual(reponses[0]['libelle'], 'Autonomie')
        self.assertEqual(reponses[0]['reponse'], '')

    def test_modele_departement_employe_sans_campagne_modele(self):
        make_modele(self.company, 'Modele dep', departement=self.dep)
        campagne = make_campagne(self.company)  # pas de modele explicite
        employe = make_employe(self.company, 'ZRH7-2', departement=self.dep)
        reponses = services.instancier_reponses_evaluation(campagne, employe)
        self.assertEqual(len(reponses), 2)

    def test_modele_defaut_societe(self):
        make_modele(self.company, 'Modele defaut')  # sans departement
        campagne = make_campagne(self.company)
        employe = make_employe(self.company, 'ZRH7-3')  # sans departement
        reponses = services.instancier_reponses_evaluation(campagne, employe)
        self.assertEqual(len(reponses), 2)

    def test_aucun_modele_reponses_vide(self):
        campagne = make_campagne(self.company)
        employe = make_employe(self.company, 'ZRH7-4')
        reponses = services.instancier_reponses_evaluation(campagne, employe)
        self.assertEqual(reponses, [])

    def test_isolation_tenant_modele(self):
        autre = make_company('zrh7-b', 'B')
        make_modele(autre, 'Modele autre societe')
        campagne = make_campagne(self.company)
        employe = make_employe(self.company, 'ZRH7-5')
        reponses = services.instancier_reponses_evaluation(campagne, employe)
        self.assertEqual(reponses, [])


class EvaluationEndpointReponsesTests(TestCase):
    def setUp(self):
        self.company = make_company('zrh7-c', 'C')
        self.rh = make_user(self.company, 'zrh7-rh')

    def test_creation_evaluation_instancie_reponses(self):
        modele = make_modele(self.company, 'Modele test')
        campagne = make_campagne(self.company, modele=modele)
        employe = make_employe(self.company, 'ZRH7-EP')
        resp = auth(self.rh).post(EVAL_URL, {
            'campagne': campagne.id, 'employe': employe.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        evaluation = EvaluationEmploye.objects.get(id=resp.data['id'])
        self.assertEqual(len(evaluation.reponses), 2)


class ModeleEvaluationCrudTests(TestCase):
    def setUp(self):
        self.company = make_company('zrh7-d', 'D')
        self.rh = make_user(self.company, 'zrh7-rh2')

    def test_creation_company_cote_serveur(self):
        resp = auth(self.rh).post(MODELES_URL, {
            'nom': 'Modele X',
            'questions': [{'libelle': 'Q1', 'type': 'texte',
                          'cible': 'manager'}],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        modele = ModeleEvaluation.objects.get(id=resp.data['id'])
        self.assertEqual(modele.company, self.company)

    def test_isolation_tenant_liste(self):
        autre = make_company('zrh7-e', 'E')
        make_modele(autre, 'Modele autre')
        resp = auth(self.rh).get(MODELES_URL)
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        rows = data['results'] if isinstance(data, dict) and \
            'results' in data else data
        self.assertEqual(len(rows), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'zrh7-normal', role='normal')
        resp = auth(normal).get(MODELES_URL)
        self.assertEqual(resp.status_code, 403)
