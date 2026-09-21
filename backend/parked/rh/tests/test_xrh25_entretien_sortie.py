"""Tests XRH25 — Entretien de sortie (exit interview) + motifs de turnover.

Couvre :
* un entretien de sortie par employé sorti maximum (contrainte OneToOne) ;
* ``selectors.motifs_depart`` compte par motif sur la période ;
* le cockpit RH (FG200) expose ``turnover.motifs_depart`` sans rien casser ;
* isolation société.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import DossierEmploye, EntretienSortie

User = get_user_model()

COCKPIT_URL = '/api/django/rh/cockpit/'
ENTRETIENS_URL = '/api/django/rh/entretiens-sortie/'


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


class EntretienSortieTests(TestCase):
    def setUp(self):
        self.co = make_company('exit-a', 'A')
        self.rh = make_user(self.co, 'exit-rh')
        self.today = timezone.localdate()
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='N', prenom='P',
            statut=DossierEmploye.Statut.SORTI,
            date_sortie=self.today - timedelta(days=10),
            motif_sortie=DossierEmploye.MotifSortie.DEMISSION)

    def test_un_seul_entretien_par_employe(self):
        EntretienSortie.objects.create(
            company=self.co, employe=self.emp,
            motif_principal=EntretienSortie.MotifPrincipal.SALAIRE)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EntretienSortie.objects.create(
                    company=self.co, employe=self.emp,
                    motif_principal=EntretienSortie.MotifPrincipal.AUTRE)

    def test_motifs_depart_compte_par_motif_sur_periode(self):
        emp2 = DossierEmploye.objects.create(
            company=self.co, matricule='E2', nom='N2', prenom='P2',
            statut=DossierEmploye.Statut.SORTI,
            date_sortie=self.today - timedelta(days=5))
        EntretienSortie.objects.create(
            company=self.co, employe=self.emp,
            motif_principal=EntretienSortie.MotifPrincipal.SALAIRE)
        EntretienSortie.objects.create(
            company=self.co, employe=emp2,
            motif_principal=EntretienSortie.MotifPrincipal.SALAIRE)

        result = selectors.motifs_depart(
            self.co, self.today - timedelta(days=30), self.today)
        self.assertEqual(result['salaire'], 2)

    def test_motifs_depart_hors_periode_exclus(self):
        EntretienSortie.objects.create(
            company=self.co, employe=self.emp,
            motif_principal=EntretienSortie.MotifPrincipal.MANAGEMENT)
        result = selectors.motifs_depart(
            self.co, self.today - timedelta(days=400),
            self.today - timedelta(days=200))
        self.assertEqual(result, {})

    def test_motif_vide_non_compte(self):
        EntretienSortie.objects.create(company=self.co, employe=self.emp)
        result = selectors.motifs_depart(
            self.co, self.today - timedelta(days=30), self.today)
        self.assertEqual(result, {})

    def test_cockpit_expose_motifs_depart_sans_casser_turnover(self):
        EntretienSortie.objects.create(
            company=self.co, employe=self.emp,
            motif_principal=EntretienSortie.MotifPrincipal.DISTANCE)
        resp = auth(self.rh).get(COCKPIT_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('motifs_depart', resp.data['turnover'])
        self.assertEqual(
            resp.data['turnover']['motifs_depart']['distance'], 1)
        self.assertEqual(resp.data['turnover']['sorties_12m'], 1)

    def test_crud_entretien_sortie_company_scope(self):
        resp = auth(self.rh).post(ENTRETIENS_URL, {
            'employe': self.emp.id, 'date': str(self.today),
            'motif_principal': 'opportunite',
            'questionnaire': {'q1': 'reponse1'},
            'recommanderait': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['motif_principal'], 'opportunite')
        self.assertTrue(resp.data['recommanderait'])

    def test_isolation_societe(self):
        co_b = make_company('exit-b', 'B')
        rh_b = make_user(co_b, 'exit-rh-b')
        EntretienSortie.objects.create(
            company=self.co, employe=self.emp,
            motif_principal=EntretienSortie.MotifPrincipal.SANTE)
        resp = auth(rh_b).get(ENTRETIENS_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['results']
                             if isinstance(resp.data, dict) else resp.data), 0)

    def test_employe_autre_societe_rejete(self):
        co_b = make_company('exit-c', 'B')
        emp_b = DossierEmploye.objects.create(
            company=co_b, matricule='EB1', nom='N', prenom='P')
        resp = auth(self.rh).post(ENTRETIENS_URL, {
            'employe': emp_b.id, 'motif_principal': 'autre',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
