"""Tests NTHCM10 — grille 9-box (performance × potentiel).

Couvre :
* positionner un employé sur les DEUX axes calcule sa case 1-9 côté serveur ;
* ``grille_neuf_box`` agrège la répartition et renvoie TOUJOURS 9 cases ;
* un employé sans positionnement reste ABSENT (pas d'erreur) ;
* ``evalue_par`` est posé côté serveur, ``case_calculee`` non écrasable ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import DossierEmploye, EvaluationNeufBox
from apps.rh.models import case_neuf_box

User = get_user_model()


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


class CaseNeufBoxTests(TestCase):
    def test_bornes_de_la_grille(self):
        self.assertEqual(case_neuf_box(1, 1), 1)
        self.assertEqual(case_neuf_box(3, 1), 3)
        self.assertEqual(case_neuf_box(1, 2), 4)
        self.assertEqual(case_neuf_box(2, 2), 5)
        self.assertEqual(case_neuf_box(3, 3), 9)

    def test_valeurs_hors_bornes_sont_ramenees(self):
        self.assertEqual(case_neuf_box(0, 0), 1)
        self.assertEqual(case_neuf_box(9, 9), 9)


class GrilleNeufBoxTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm10-a', 'A')
        self.rh = make_user(self.co, 'nthcm10-rh')
        self.api = auth(self.rh)
        self.e1 = DossierEmploye.objects.create(
            company=self.co, matricule='N-1', nom='Alpha', prenom='Un')
        self.e2 = DossierEmploye.objects.create(
            company=self.co, matricule='N-2', nom='Beta', prenom='Deux')
        self.non_positionne = DossierEmploye.objects.create(
            company=self.co, matricule='N-3', nom='Gamma', prenom='Trois')

    def test_case_calculee_cote_serveur(self):
        evaluation = EvaluationNeufBox.objects.create(
            company=self.co, employe=self.e1,
            axe_performance=3, axe_potentiel=3)
        self.assertEqual(evaluation.case_calculee, 9)

    def test_case_recalculee_a_la_mise_a_jour(self):
        evaluation = EvaluationNeufBox.objects.create(
            company=self.co, employe=self.e1,
            axe_performance=1, axe_potentiel=1)
        self.assertEqual(evaluation.case_calculee, 1)
        evaluation.axe_potentiel = 3
        evaluation.save(update_fields=['axe_potentiel'])
        evaluation.refresh_from_db()
        self.assertEqual(evaluation.case_calculee, 7)

    def test_grille_renvoie_toujours_neuf_cases(self):
        EvaluationNeufBox.objects.create(
            company=self.co, employe=self.e1,
            axe_performance=3, axe_potentiel=3)
        grille = selectors.grille_neuf_box(self.co)
        self.assertEqual(len(grille['cases']), 9)
        self.assertEqual(grille['total'], 1)
        case9 = next(c for c in grille['cases'] if c['case'] == 9)
        self.assertEqual(case9['nombre'], 1)
        self.assertEqual(case9['employes'][0]['employe_id'], self.e1.id)

    def test_employe_sans_evaluation_absent_sans_erreur(self):
        EvaluationNeufBox.objects.create(
            company=self.co, employe=self.e1,
            axe_performance=2, axe_potentiel=2)
        grille = selectors.grille_neuf_box(self.co)
        ids = {ligne['employe_id']
               for case in grille['cases'] for ligne in case['employes']}
        self.assertIn(self.e1.id, ids)
        self.assertNotIn(self.non_positionne.id, ids)

    def test_grille_vide_ne_leve_pas(self):
        grille = selectors.grille_neuf_box(self.co)
        self.assertEqual(grille['total'], 0)
        self.assertEqual(
            sum(case['nombre'] for case in grille['cases']), 0)

    def test_agregat_par_case(self):
        EvaluationNeufBox.objects.create(
            company=self.co, employe=self.e1,
            axe_performance=2, axe_potentiel=2)
        EvaluationNeufBox.objects.create(
            company=self.co, employe=self.e2,
            axe_performance=2, axe_potentiel=2)
        grille = selectors.grille_neuf_box(self.co)
        case5 = next(c for c in grille['cases'] if c['case'] == 5)
        self.assertEqual(case5['nombre'], 2)
        self.assertEqual(grille['total'], 2)

    def test_endpoint_grille(self):
        EvaluationNeufBox.objects.create(
            company=self.co, employe=self.e1,
            axe_performance=1, axe_potentiel=3)
        resp = self.api.get('/api/django/rh/evaluations-neuf-box/grille/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], 1)
        case7 = next(c for c in resp.data['cases'] if c['case'] == 7)
        self.assertEqual(case7['nombre'], 1)

    def test_creation_api_pose_evalue_par_et_societe(self):
        resp = self.api.post(
            '/api/django/rh/evaluations-neuf-box/',
            {'employe': self.e1.id, 'axe_performance': 3,
             'axe_potentiel': 2, 'case_calculee': 1}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        evaluation = EvaluationNeufBox.objects.get(id=resp.data['id'])
        self.assertEqual(evaluation.company_id, self.co.id)
        self.assertEqual(evaluation.evalue_par_id, self.rh.id)
        # ``case_calculee`` envoyée par le client est IGNORÉE.
        self.assertEqual(evaluation.case_calculee, 6)

    def test_recalibrage_par_patch(self):
        evaluation = EvaluationNeufBox.objects.create(
            company=self.co, employe=self.e1,
            axe_performance=1, axe_potentiel=1)
        resp = self.api.patch(
            f'/api/django/rh/evaluations-neuf-box/{evaluation.id}/',
            {'axe_performance': 3, 'axe_potentiel': 3}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        evaluation.refresh_from_db()
        self.assertEqual(evaluation.case_calculee, 9)

    def test_isolation_societe(self):
        EvaluationNeufBox.objects.create(
            company=self.co, employe=self.e1,
            axe_performance=3, axe_potentiel=3)
        co_b = make_company('nthcm10-b', 'B')
        rh_b = make_user(co_b, 'nthcm10-rh-b')
        grille_b = selectors.grille_neuf_box(co_b)
        self.assertEqual(grille_b['total'], 0)
        resp = auth(rh_b).get('/api/django/rh/evaluations-neuf-box/grille/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], 0)
