"""NTASS17 — Attestations d'assurance émises par NOS assureurs (GED).

Critère d'acceptation : une attestation RC pro valable 1 an est uploadée et
liée à sa police, consultable depuis la fiche police."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import (
    Assureur, AttestationAssurance, PoliceAssurance,
)

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class AttestationAssuranceApiTests(TestCase):
    BASE = '/api/django/assurances/attestations/'

    def setUp(self):
        self.company = make_company('assurances-p17', 'P17')
        self.user = make_user(self.company, 'assur-p17')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='RC-2026-001',
            type_police=PoliceAssurance.TypePolice.RC_PRO,
            date_effet=today, date_echeance=today + datetime.timedelta(days=365))

    def test_creer_attestation_rc_pro_liee_a_la_police(self):
        api = auth(self.user)
        today = datetime.date.today()
        resp = api.post(self.BASE, {
            'police': self.police.id,
            'date_emission': today.isoformat(),
            'date_validite': (today + datetime.timedelta(days=365)).isoformat(),
            'emise_pour': 'Client X — Marché Y',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        att = AttestationAssurance.objects.get(id=resp.data['id'])
        self.assertEqual(att.police_id, self.police.id)
        self.assertEqual(att.company, self.company)
        self.assertEqual(att.statut, AttestationAssurance.Statut.VALIDE)

    def test_liste_attestations_par_police(self):
        AttestationAssurance.objects.create(
            company=self.company, police=self.police,
            date_emission=datetime.date.today(),
            date_validite=datetime.date.today() + datetime.timedelta(days=365),
            emise_pour='Marché BTP')
        api = auth(self.user)
        resp = api.get(self.BASE, {'police': self.police.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)
