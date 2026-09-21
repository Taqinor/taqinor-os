"""Tests ZRH6 — Détection des absences non justifiées.

``selectors.absents_non_justifies`` : employé attendu SANS pointage NI congé
validé remonte ; un employé en congé validé ou pointé n'y figure pas.
Endpoint ``pointages/absents-non-justifies/?jour=`` + génération d'incident.
"""
from datetime import date, datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import DemandeConge, DossierEmploye, IncidentPresence, \
    Pointage, TypeAbsence

User = get_user_model()

URL = '/api/django/rh/pointages/absents-non-justifies/'
GENERER_URL = '/api/django/rh/pointages/generer-incident-absence/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P',
        statut=DossierEmploye.Statut.ACTIF)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AbsentsNonJustifiesSelectorTests(TestCase):
    def setUp(self):
        self.company = make_company('zrh6-a', 'A')
        self.jour = date(2026, 7, 6)  # lundi

    def test_employe_sans_pointage_ni_conge_remonte(self):
        employe = make_employe(self.company, 'ZRH6-1')
        resultats = selectors.absents_non_justifies(self.company, self.jour)
        ids = {r['employe_id'] for r in resultats}
        self.assertIn(employe.id, ids)

    def test_employe_en_conge_valide_absent_de_la_liste(self):
        employe = make_employe(self.company, 'ZRH6-2')
        ta = TypeAbsence.objects.create(
            company=self.company, code='CP', libelle='CP')
        DemandeConge.objects.create(
            company=self.company, employe=employe, type_absence=ta,
            date_debut=self.jour, date_fin=self.jour, jours=1,
            statut=DemandeConge.Statut.VALIDEE)
        resultats = selectors.absents_non_justifies(self.company, self.jour)
        ids = {r['employe_id'] for r in resultats}
        self.assertNotIn(employe.id, ids)

    def test_employe_pointe_absent_de_la_liste(self):
        employe = make_employe(self.company, 'ZRH6-3')
        Pointage.objects.create(
            company=self.company, employe=employe,
            type_pointage=Pointage.TypePointage.ARRIVEE,
            heure_arrivee=datetime(
                2026, 7, 6, 8, 30, tzinfo=dt_timezone.utc))
        resultats = selectors.absents_non_justifies(self.company, self.jour)
        ids = {r['employe_id'] for r in resultats}
        self.assertNotIn(employe.id, ids)

    def test_isolation_tenant(self):
        autre = make_company('zrh6-b', 'B')
        make_employe(autre, 'ZRH6-AUTRE')
        resultats = selectors.absents_non_justifies(self.company, self.jour)
        matricules = {r['matricule'] for r in resultats}
        self.assertNotIn('ZRH6-AUTRE', matricules)


class AbsentsNonJustifiesEndpointTests(TestCase):
    def setUp(self):
        self.company = make_company('zrh6-c', 'C')
        self.rh = make_user(self.company, 'zrh6-rh')
        self.employe = make_employe(self.company, 'ZRH6-EP')

    def test_endpoint_liste_absents(self):
        resp = auth(self.rh).get(f'{URL}?jour=2026-07-06')
        self.assertEqual(resp.status_code, 200, resp.data)
        matricules = {r['matricule'] for r in resp.data}
        self.assertIn('ZRH6-EP', matricules)

    def test_generer_incident(self):
        resp = auth(self.rh).post(GENERER_URL, {
            'employe': self.employe.id, 'jour': '2026-07-06',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            IncidentPresence.objects.filter(
                company=self.company, employe=self.employe,
                type_incident=IncidentPresence.TypeIncident.ABSENCE_INJUSTIFIEE
            ).exists())

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'zrh6-normal', role='normal')
        resp = auth(normal).get(URL)
        self.assertEqual(resp.status_code, 403)
