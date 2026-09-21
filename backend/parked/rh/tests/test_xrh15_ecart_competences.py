"""Tests XRH15 — Compétences requises par poste + analyse d'écart.

Couvre :
* le gap d'un employé liste les compétences SOUS le niveau requis (celles déjà
  satisfaites sont omises) ;
* le classement interne (``candidats-internes``) trie par couverture
  décroissante ;
* création de besoin de formation en un clic depuis un écart ;
* isolation société + unicité (poste, compétence).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    BesoinFormation,
    Competence,
    CompetenceEmploye,
    CompetenceRequise,
    DossierEmploye,
    Poste,
)

User = get_user_model()

EMPLOYES = '/api/django/rh/employes/'
POSTES = '/api/django/rh/postes/'
COMP_REQUISES = '/api/django/rh/competences-requises/'


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


class EcartCompetencesTests(TestCase):
    def setUp(self):
        self.co = make_company('ecart-a', 'A')
        self.rh = make_user(self.co, 'ecart-rh')
        self.poste = Poste.objects.create(
            company=self.co, intitule='Technicien pose')
        self.comp_pose = Competence.objects.create(
            company=self.co, code='POSE', libelle='Pose structure',
            domaine=Competence.Domaine.POSE_STRUCTURE)
        self.comp_dc = Competence.objects.create(
            company=self.co, code='DC', libelle='Raccordement DC',
            domaine=Competence.Domaine.RACCORDEMENT_DC)
        CompetenceRequise.objects.create(
            company=self.co, poste=self.poste, competence=self.comp_pose,
            niveau_requis=CompetenceEmploye.Niveau.CONFIRME)
        CompetenceRequise.objects.create(
            company=self.co, poste=self.poste, competence=self.comp_dc,
            niveau_requis=CompetenceEmploye.Niveau.INTERMEDIAIRE)
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='Ouazzani', prenom='Hamza',
            poste_ref=self.poste)

    def test_ecart_liste_competences_sous_le_niveau_requis(self):
        # Employé DÉBUTANT en pose (requis CONFIRME) → écart. Jamais évalué en
        # DC (requis INTERMEDIAIRE, actuel 0) → écart aussi.
        CompetenceEmploye.objects.create(
            company=self.co, employe=self.emp, competence=self.comp_pose,
            niveau=CompetenceEmploye.Niveau.DEBUTANT)

        resp = auth(self.rh).get(f'{EMPLOYES}{self.emp.id}/ecart-competences/')
        self.assertEqual(resp.status_code, 200, resp.data)
        libelles = {row['competence_libelle'] for row in resp.data}
        self.assertEqual(libelles, {'Pose structure', 'Raccordement DC'})

    def test_competence_deja_satisfaite_omise(self):
        CompetenceEmploye.objects.create(
            company=self.co, employe=self.emp, competence=self.comp_pose,
            niveau=CompetenceEmploye.Niveau.EXPERT)
        CompetenceEmploye.objects.create(
            company=self.co, employe=self.emp, competence=self.comp_dc,
            niveau=CompetenceEmploye.Niveau.INTERMEDIAIRE)
        resp = auth(self.rh).get(f'{EMPLOYES}{self.emp.id}/ecart-competences/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, [])

    def test_sans_poste_ref_liste_vide(self):
        emp2 = DossierEmploye.objects.create(
            company=self.co, matricule='E2', nom='X', prenom='Y')
        resp = auth(self.rh).get(f'{EMPLOYES}{emp2.id}/ecart-competences/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])

    def test_candidats_internes_trie_par_couverture_decroissante(self):
        emp_full = DossierEmploye.objects.create(
            company=self.co, matricule='E3', nom='Complet', prenom='C',
            poste_ref=self.poste)
        CompetenceEmploye.objects.create(
            company=self.co, employe=emp_full, competence=self.comp_pose,
            niveau=CompetenceEmploye.Niveau.CONFIRME)
        CompetenceEmploye.objects.create(
            company=self.co, employe=emp_full, competence=self.comp_dc,
            niveau=CompetenceEmploye.Niveau.INTERMEDIAIRE)
        # self.emp n'a AUCUNE compétence évaluée → 0 % de couverture.

        resp = auth(self.rh).get(f'{POSTES}{self.poste.id}/candidats-internes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data[0]['employe_id'], emp_full.id)
        self.assertEqual(resp.data[0]['couverture_pct'], 100.0)
        self.assertLess(
            resp.data[1]['couverture_pct'], resp.data[0]['couverture_pct'])

    def test_creer_besoin_formation_depuis_ecart(self):
        resp = auth(self.rh).post(
            f'{EMPLOYES}{self.emp.id}/'
            f'ecart-competences-creer-besoin-formation/',
            {'competence': self.comp_pose.id})
        self.assertEqual(resp.status_code, 201, resp.data)
        besoin = BesoinFormation.objects.get(pk=resp.data['id'])
        self.assertEqual(besoin.theme, 'Pose structure')
        self.assertEqual(besoin.employe, self.emp)

    def test_unicite_poste_competence(self):
        resp = auth(self.rh).post(COMP_REQUISES, {
            'poste': self.poste.id, 'competence': self.comp_pose.id,
            'niveau_requis': 3,
        })
        self.assertEqual(resp.status_code, 400)

    def test_isolation_societe(self):
        co_b = make_company('ecart-b', 'B')
        rh_b = make_user(co_b, 'ecart-rh-b')
        resp = auth(rh_b).get(f'{EMPLOYES}{self.emp.id}/ecart-competences/')
        self.assertEqual(resp.status_code, 404)
