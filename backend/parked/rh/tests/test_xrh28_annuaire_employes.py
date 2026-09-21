"""Tests XRH28 — Annuaire interne des employés (trombinoscope).

Couvre :
* un employé simple (rôle ``normal``) voit l'annuaire de SA société ;
* AUCUN champ sensible dans la réponse (exhaustivité des clés) ;
* recherche ``?q=`` nom/poste/département ;
* filtre par compétence ``?competence=&niveau_min=`` ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    Competence, CompetenceEmploye, Departement, DossierEmploye,
)

User = get_user_model()

ANNUAIRE_URL = '/api/django/rh/employes/annuaire/'

# Champs JAMAIS autorisés dans la réponse annuaire (donnée sensible).
CHAMPS_INTERDITS = {
    'cin', 'rib', 'cout_horaire', 'cnss', 'cimr', 'amo',
    'adresse_perso', 'telephone_perso', 'email_perso',
    'situation_familiale', 'groupe_sanguin', 'nombre_enfants',
    'urgence_nom', 'urgence_lien', 'urgence_telephone', 'matricule',
}


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


class AnnuaireEmployesTests(TestCase):
    def setUp(self):
        self.co = make_company('ann-a', 'A')
        self.employe_user = make_user(self.co, 'ann-employe', role='normal')
        self.dep = Departement.objects.create(company=self.co, nom='Atelier')
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='Fahmi', prenom='Yassir',
            cin='AB12345', rib='RIB123', cout_horaire=150,
            telephone='0612345678', email='yassir@example.com',
            departement=self.dep, poste='Technicien pose',
            statut=DossierEmploye.Statut.ACTIF)

    def test_employe_normal_voit_annuaire_de_sa_societe(self):
        resp = auth(self.employe_user).get(ANNUAIRE_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['nom'], 'Fahmi')

    def test_aucun_champ_sensible_exhaustivite(self):
        resp = auth(self.employe_user).get(ANNUAIRE_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        cles = set(resp.data[0].keys())
        fuite = cles & CHAMPS_INTERDITS
        self.assertEqual(fuite, set(), f'Champs sensibles exposés : {fuite}')

    def test_recherche_q_nom_poste_departement(self):
        resp = auth(self.employe_user).get(ANNUAIRE_URL, {'q': 'Atelier'})
        self.assertEqual(len(resp.data), 1)
        resp = auth(self.employe_user).get(ANNUAIRE_URL, {'q': 'Technicien'})
        self.assertEqual(len(resp.data), 1)
        resp = auth(self.employe_user).get(ANNUAIRE_URL, {'q': 'Introuvable'})
        self.assertEqual(len(resp.data), 0)

    def test_filtre_par_competence_niveau_min(self):
        comp = Competence.objects.create(
            company=self.co, code='POSE', libelle='Pose structure')
        CompetenceEmploye.objects.create(
            company=self.co, employe=self.dossier, competence=comp, niveau=3)
        autre_dossier = DossierEmploye.objects.create(
            company=self.co, matricule='E2', nom='N2', prenom='P2',
            statut=DossierEmploye.Statut.ACTIF)

        resp = auth(self.employe_user).get(
            ANNUAIRE_URL, {'competence': comp.id, 'niveau_min': 2})
        ids = {row['id'] for row in resp.data}
        self.assertIn(self.dossier.id, ids)
        self.assertNotIn(autre_dossier.id, ids)

    def test_isolation_societe(self):
        co_b = make_company('ann-b', 'B')
        user_b = make_user(co_b, 'ann-employe-b', role='normal')
        resp = auth(user_b).get(ANNUAIRE_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, [])
