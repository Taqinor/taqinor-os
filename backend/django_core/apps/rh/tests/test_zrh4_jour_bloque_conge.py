"""Tests ZRH4 — Jours de blocage congés (Mandatory/Stress Days).

Une ``DemandeConge`` chevauchant un ``JourBloqueConge`` du département de
l'employé est refusée (400) ; un autre département n'est pas affecté ; le RH
peut forcer (``?forcer=1``) ; CRUD company-scopé.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import Departement, DossierEmploye, JourBloqueConge, \
    TypeAbsence

User = get_user_model()

DEMANDES_URL = '/api/django/rh/demandes-conge/'
BLOQUES_URL = '/api/django/rh/jours-bloques-conge/'
PORTAIL_URL = '/api/django/rh/portail/demander-conge/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, departement=None, user=None):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P',
        departement=departement, user=user)


def make_type_absence(company):
    return TypeAbsence.objects.create(
        company=company, code='CP', libelle='Congé payé',
        decompte_jours_ouvres=False)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class JourBloqueCongeTests(TestCase):
    def setUp(self):
        self.company = make_company('zrh4-a', 'A')
        self.rh = make_user(self.company, 'zrh4-rh')
        self.dep1 = Departement.objects.create(company=self.company, nom='Dep1')
        self.dep2 = Departement.objects.create(company=self.company, nom='Dep2')
        self.emp1 = make_employe(self.company, 'ZRH4-1', departement=self.dep1)
        self.emp2 = make_employe(self.company, 'ZRH4-2', departement=self.dep2)
        self.type_absence = make_type_absence(self.company)

    def test_creation_jour_bloque_company_cote_serveur(self):
        resp = auth(self.rh).post(BLOQUES_URL, {
            'libelle': 'Haute saison', 'date_debut': '2026-07-01',
            'date_fin': '2026-07-15', 'departements': [self.dep1.id],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        bloc = JourBloqueConge.objects.get(id=resp.data['id'])
        self.assertEqual(bloc.company, self.company)

    def test_demande_chevauchant_bloque_refusee(self):
        JourBloqueConge.objects.create(
            company=self.company, libelle='Haute saison',
            date_debut=date(2026, 7, 1), date_fin=date(2026, 7, 15),
        ).departements.set([self.dep1])

        resp = auth(self.rh).post(DEMANDES_URL, {
            'employe': self.emp1.id, 'type_absence': self.type_absence.id,
            'date_debut': '2026-07-05', 'date_fin': '2026-07-10',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('bloqu', resp.data['detail'].lower())

    def test_autre_departement_non_affecte(self):
        JourBloqueConge.objects.create(
            company=self.company, libelle='Haute saison',
            date_debut=date(2026, 7, 1), date_fin=date(2026, 7, 15),
        ).departements.set([self.dep1])

        resp = auth(self.rh).post(DEMANDES_URL, {
            'employe': self.emp2.id, 'type_absence': self.type_absence.id,
            'date_debut': '2026-07-05', 'date_fin': '2026-07-10',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_blocage_societe_entiere_sans_departement(self):
        JourBloqueConge.objects.create(
            company=self.company, libelle='Inventaire',
            date_debut=date(2026, 8, 1), date_fin=date(2026, 8, 5))
        resp = auth(self.rh).post(DEMANDES_URL, {
            'employe': self.emp2.id, 'type_absence': self.type_absence.id,
            'date_debut': '2026-08-02', 'date_fin': '2026-08-03',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_rh_peut_forcer(self):
        JourBloqueConge.objects.create(
            company=self.company, libelle='Haute saison',
            date_debut=date(2026, 7, 1), date_fin=date(2026, 7, 15),
        ).departements.set([self.dep1])

        resp = auth(self.rh).post(f'{DEMANDES_URL}?forcer=1', {
            'employe': self.emp1.id, 'type_absence': self.type_absence.id,
            'date_debut': '2026-07-05', 'date_fin': '2026-07-10',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_isolation_tenant(self):
        autre = make_company('zrh4-b', 'B')
        JourBloqueConge.objects.create(
            company=autre, libelle='Autre société bloque tout',
            date_debut=date(2026, 7, 1), date_fin=date(2026, 7, 15))
        resp = auth(self.rh).post(DEMANDES_URL, {
            'employe': self.emp1.id, 'type_absence': self.type_absence.id,
            'date_debut': '2026-07-05', 'date_fin': '2026-07-10',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_portail_employe_normal_ne_peut_pas_forcer(self):
        user_normal = make_user(self.company, 'zrh4-normal', role='normal')
        emp_normal = make_employe(
            self.company, 'ZRH4-N', departement=self.dep1, user=user_normal)
        JourBloqueConge.objects.create(
            company=self.company, libelle='Haute saison',
            date_debut=date(2026, 7, 1), date_fin=date(2026, 7, 15),
        ).departements.set([self.dep1])
        resp = auth(user_normal).post(f'{PORTAIL_URL}?forcer=1', {
            'type_absence': self.type_absence.id,
            'date_debut': '2026-07-05', 'date_fin': '2026-07-10',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(DossierEmploye.objects.filter(id=emp_normal.id).exists())
