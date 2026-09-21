"""Tests ZRH3 — Rapport congés par type et par employé.

``selectors.rapport_conges`` agrège les demandes VALIDÉES de l'année, par
type d'absence et par employé (croisé type) + solde disponible courant.
Endpoint ``demandes-conge/rapport/?annee=&employe=&departement=``.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import (
    Departement, DemandeConge, DossierEmploye, SoldeConge, TypeAbsence,
)

User = get_user_model()

URL = '/api/django/rh/demandes-conge/rapport/'


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


def make_type(company, code, libelle=None):
    return TypeAbsence.objects.create(
        company=company, code=code, libelle=libelle or code)


def make_demande(company, employe, type_absence, jours, annee=2026,
                 statut=DemandeConge.Statut.VALIDEE):
    return DemandeConge.objects.create(
        company=company, employe=employe, type_absence=type_absence,
        date_debut=date(annee, 3, 1), date_fin=date(annee, 3, 10),
        jours=Decimal(str(jours)), statut=statut)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RapportCongesSelectorTests(TestCase):
    def setUp(self):
        self.company = make_company('zrh3-a', 'A')
        self.dep1 = Departement.objects.create(company=self.company, nom='Dep1')
        self.dep2 = Departement.objects.create(company=self.company, nom='Dep2')
        self.emp1 = make_employe(self.company, 'ZRH3-1', departement=self.dep1)
        self.emp2 = make_employe(self.company, 'ZRH3-2', departement=self.dep2)
        self.cp = make_type(self.company, 'CP', 'Congé payé')
        self.mal = make_type(self.company, 'MAL', 'Maladie')

    def test_agregat_par_type_et_employe(self):
        make_demande(self.company, self.emp1, self.cp, 5)
        make_demande(self.company, self.emp1, self.mal, 2)
        make_demande(self.company, self.emp2, self.cp, 3)
        report = selectors.rapport_conges(self.company, 2026)

        par_type = {t['code']: t['jours'] for t in report['par_type']}
        self.assertEqual(par_type['CP'], Decimal('8'))
        self.assertEqual(par_type['MAL'], Decimal('2'))

        par_emp = {e['employe_id']: e for e in report['par_employe']}
        self.assertEqual(par_emp[self.emp1.id]['jours'], Decimal('7'))
        self.assertEqual(
            par_emp[self.emp1.id]['par_type']['CP'], Decimal('5'))
        self.assertEqual(par_emp[self.emp2.id]['jours'], Decimal('3'))

    def test_filtre_departement(self):
        make_demande(self.company, self.emp1, self.cp, 5)
        make_demande(self.company, self.emp2, self.cp, 3)
        report = selectors.rapport_conges(
            self.company, 2026, departement_id=self.dep1.id)
        self.assertEqual(len(report['par_employe']), 1)
        self.assertEqual(report['par_employe'][0]['employe_id'], self.emp1.id)

    def test_seules_les_validees_comptent(self):
        make_demande(
            self.company, self.emp1, self.cp, 5,
            statut=DemandeConge.Statut.SOUMISE)
        report = selectors.rapport_conges(self.company, 2026)
        self.assertEqual(report['par_type'], [])
        self.assertEqual(report['par_employe'], [])

    def test_solde_disponible_inclus(self):
        SoldeConge.objects.create(
            company=self.company, employe=self.emp1, annee=2026,
            acquis=Decimal('18'), report=Decimal('0'), pris=Decimal('5'))
        make_demande(self.company, self.emp1, self.cp, 5)
        report = selectors.rapport_conges(self.company, 2026)
        entry = next(
            e for e in report['par_employe'] if e['employe_id'] == self.emp1.id)
        self.assertEqual(entry['solde_disponible'], Decimal('13'))

    def test_isolation_tenant(self):
        autre = make_company('zrh3-b', 'B')
        emp_autre = make_employe(autre, 'ZRH3-AUTRE')
        type_autre = make_type(autre, 'CP')
        make_demande(autre, emp_autre, type_autre, 5)
        report = selectors.rapport_conges(self.company, 2026)
        self.assertEqual(report['par_type'], [])


class RapportCongesEndpointTests(TestCase):
    def setUp(self):
        self.company = make_company('zrh3-c', 'C')
        self.user = make_user(self.company, 'zrh3-user')
        self.emp = make_employe(self.company, 'ZRH3-EP')
        self.cp = make_type(self.company, 'CP', 'Congé payé')
        make_demande(self.company, self.emp, self.cp, 6)

    def test_endpoint_annee_filtrable(self):
        resp = auth(self.user).get(f'{URL}?annee=2026')
        self.assertEqual(resp.status_code, 200, resp.data)
        codes = {t['code'] for t in resp.data['par_type']}
        self.assertIn('CP', codes)

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'zrh3-normal', role='normal')
        resp = auth(normal).get(URL)
        self.assertEqual(resp.status_code, 403)
