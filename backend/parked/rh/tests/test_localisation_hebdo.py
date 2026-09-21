"""Tests ZRH16 — localisation de télétravail par jour de semaine.

Couvre : réglage par jour, défaut bureau si non réglé, congé validé ->
absent, isolation tenant, accès à tout employé authentifié.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DemandeConge, DossierEmploye, TypeAbsence

User = get_user_model()

URL = '/api/django/rh/employes/localisation-du-jour/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class LocalisationHebdoTests(TestCase):
    def setUp(self):
        self.co_a = make_company('lh-a', 'A')
        self.co_b = make_company('lh-b', 'B')
        self.user_a = make_user(self.co_a, 'lh-user-a')
        self.user_b = make_user(self.co_b, 'lh-user-b')
        # Vendredi 2026-01-02.
        self.vendredi = date(2026, 1, 2)
        self.emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='LH1', nom='N', prenom='P',
            localisation_hebdo={'vendredi': 'domicile'})

    def test_localisation_reglee(self):
        resp = auth(self.user_a).get(
            URL, {'jour': self.vendredi.isoformat()})
        self.assertEqual(resp.status_code, 200, resp.data)
        entry = next(
            e for e in resp.data if e['employe_id'] == self.emp.id)
        self.assertEqual(entry['localisation'], 'domicile')

    def test_defaut_bureau(self):
        autre = DossierEmploye.objects.create(
            company=self.co_a, matricule='LH2', nom='N2', prenom='P2')
        resp = auth(self.user_a).get(
            URL, {'jour': self.vendredi.isoformat()})
        entry = next(e for e in resp.data if e['employe_id'] == autre.id)
        self.assertEqual(entry['localisation'], 'bureau')

    def test_conge_valide_prevaut_absent(self):
        type_absence = TypeAbsence.objects.create(
            company=self.co_a, code='CP', libelle='Congé payé')
        DemandeConge.objects.create(
            company=self.co_a, employe=self.emp, type_absence=type_absence,
            date_debut=self.vendredi, date_fin=self.vendredi,
            statut=DemandeConge.Statut.VALIDEE)
        resp = auth(self.user_a).get(
            URL, {'jour': self.vendredi.isoformat()})
        entry = next(
            e for e in resp.data if e['employe_id'] == self.emp.id)
        self.assertEqual(entry['localisation'], 'absent')

    def test_isolation_tenant(self):
        resp = auth(self.user_b).get(
            URL, {'jour': self.vendredi.isoformat()})
        ids = [e['employe_id'] for e in resp.data]
        self.assertNotIn(self.emp.id, ids)

    def test_accessible_employe_normal(self):
        resp = auth(self.user_a).get(
            URL, {'jour': self.vendredi.isoformat()})
        self.assertEqual(resp.status_code, 200)
