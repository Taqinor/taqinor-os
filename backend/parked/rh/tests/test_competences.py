"""Tests FG172 — Matrice de compétences (catalogue + niveau par employé).

Couvre :
* Catalogue Competence : création (company posée côté serveur, jamais lue du
  corps), code unique par société, filtre par domaine.
* Matrice CompetenceEmploye : pose le niveau d'un employé sur une compétence
  (evalue_par/evalue_le posés côté serveur), réévaluation via PATCH, unicité
  (employé, compétence), action matrice/.
* Cross-société : employé OU compétence d'une autre société refusés.
* Isolation multi-société : B ne voit pas le référentiel ni la matrice de A.
* Permission : un rôle normal est refusé (403).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import Competence, CompetenceEmploye, DossierEmploye

User = get_user_model()

CAT = '/api/django/rh/competences/'
MAT = '/api/django/rh/competences-employe/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E')


def make_competence(company, code, domaine='pose_structure'):
    return Competence.objects.create(
        company=company, code=code, libelle=code, domaine=domaine)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class CompetenceCatalogueTests(TestCase):
    def setUp(self):
        self.co_a = make_company('cmp-a', 'A')
        self.co_b = make_company('cmp-b', 'B')
        self.user_a = make_user(self.co_a, 'cmp-user-a')
        self.user_b = make_user(self.co_b, 'cmp-user-b')

    def test_create_company_posee_cote_serveur(self):
        resp = auth(self.user_a).post(CAT, {
            'code': 'POSE', 'libelle': 'Pose structure',
            'domaine': 'pose_structure',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        comp = Competence.objects.get(id=resp.data['id'])
        self.assertEqual(comp.company, self.co_a)
        self.assertEqual(comp.domaine, 'pose_structure')

    def test_code_unique_par_societe(self):
        make_competence(self.co_a, 'SOUD', domaine='soudure')
        resp = auth(self.user_a).post(CAT, {
            'code': 'SOUD', 'libelle': 'Soudure', 'domaine': 'soudure',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_meme_code_autre_societe_ok(self):
        make_competence(self.co_a, 'POMP', domaine='pompage')
        resp = auth(self.user_b).post(CAT, {
            'code': 'POMP', 'libelle': 'Pompage', 'domaine': 'pompage',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_filtre_domaine(self):
        make_competence(self.co_a, 'POSE', domaine='pose_structure')
        make_competence(self.co_a, 'MES', domaine='mes_onduleur')
        resp = auth(self.user_a).get(CAT + '?domaine=mes_onduleur')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_isolation_list(self):
        make_competence(self.co_a, 'DCDC', domaine='raccordement_dc')
        resp = auth(self.user_b).get(CAT)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'cmp-normal', role='normal')
        resp = auth(normal).get(CAT)
        self.assertEqual(resp.status_code, 403)


class CompetenceEmployeTests(TestCase):
    def setUp(self):
        self.co_a = make_company('cme-a', 'A')
        self.co_b = make_company('cme-b', 'B')
        self.user_a = make_user(self.co_a, 'cme-user-a')
        self.user_b = make_user(self.co_b, 'cme-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')
        self.comp_a = make_competence(self.co_a, 'POSE')
        self.comp_b = make_competence(self.co_b, 'POSE')

    def test_set_niveau_company_et_evaluation_cote_serveur(self):
        resp = auth(self.user_a).post(MAT, {
            'employe': self.emp_a.id, 'competence': self.comp_a.id,
            'niveau': 3,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ligne = CompetenceEmploye.objects.get(id=resp.data['id'])
        self.assertEqual(ligne.company, self.co_a)
        self.assertEqual(ligne.niveau, 3)
        self.assertEqual(ligne.evalue_par, self.user_a)
        self.assertIsNotNone(ligne.evalue_le)

    def test_reevaluation_patch_retrace_auteur(self):
        ligne = CompetenceEmploye.objects.create(
            company=self.co_a, employe=self.emp_a, competence=self.comp_a,
            niveau=1)
        resp = auth(self.user_a).patch(
            f'{MAT}{ligne.id}/', {'niveau': 4}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne.refresh_from_db()
        self.assertEqual(ligne.niveau, 4)
        self.assertEqual(ligne.evalue_par, self.user_a)
        self.assertIsNotNone(ligne.evalue_le)

    def test_unicite_employe_competence(self):
        CompetenceEmploye.objects.create(
            company=self.co_a, employe=self.emp_a, competence=self.comp_a,
            niveau=2)
        resp = auth(self.user_a).post(MAT, {
            'employe': self.emp_a.id, 'competence': self.comp_a.id,
            'niveau': 3,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(MAT, {
            'employe': self.emp_b.id, 'competence': self.comp_a.id,
            'niveau': 2,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_competence_autre_societe_refuse(self):
        resp = auth(self.user_a).post(MAT, {
            'employe': self.emp_a.id, 'competence': self.comp_b.id,
            'niveau': 2,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_list(self):
        CompetenceEmploye.objects.create(
            company=self.co_a, employe=self.emp_a, competence=self.comp_a,
            niveau=2)
        resp = auth(self.user_b).get(MAT)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_filtre_employe_et_niveau_min(self):
        comp2 = make_competence(self.co_a, 'SOUD', domaine='soudure')
        CompetenceEmploye.objects.create(
            company=self.co_a, employe=self.emp_a, competence=self.comp_a,
            niveau=1)
        CompetenceEmploye.objects.create(
            company=self.co_a, employe=self.emp_a, competence=comp2, niveau=4)
        r1 = auth(self.user_a).get(MAT + f'?employe={self.emp_a.id}')
        self.assertEqual(len(rows(r1)), 2)
        r2 = auth(self.user_a).get(MAT + '?niveau_min=3')
        self.assertEqual(len(rows(r2)), 1)

    def test_action_matrice(self):
        comp2 = make_competence(self.co_a, 'POMP', domaine='pompage')
        CompetenceEmploye.objects.create(
            company=self.co_a, employe=self.emp_a, competence=self.comp_a,
            niveau=2)
        CompetenceEmploye.objects.create(
            company=self.co_a, employe=self.emp_a, competence=comp2, niveau=4)
        resp = auth(self.user_a).get(MAT + 'matrice/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        entry = resp.data[0]
        self.assertEqual(entry['employe_id'], self.emp_a.id)
        self.assertEqual(len(entry['competences']), 2)
