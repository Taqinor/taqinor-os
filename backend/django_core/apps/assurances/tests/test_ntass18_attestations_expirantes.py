"""NTASS18 — Alertes d'expiration d'attestations.

Critère d'acceptation : une attestation expirant dans 15 jours apparaît en
alerte distincte de l'alerte police."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import (
    Assureur, AttestationAssurance, PoliceAssurance,
)
from apps.assurances.selectors import attestations_expirantes

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


class AttestationsExpirantesTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p18', 'P18')
        self.user = make_user(self.company, 'assur-p18')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        # Police active NON expirante (échéance loin) : prouve que l'alerte
        # attestation est DISTINCTE de l'alerte police.
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='RC-2026-002',
            type_police=PoliceAssurance.TypePolice.RC_PRO,
            date_effet=today - datetime.timedelta(days=30),
            date_echeance=today + datetime.timedelta(days=300))
        self.attestation = AttestationAssurance.objects.create(
            company=self.company, police=self.police,
            date_emission=today - datetime.timedelta(days=350),
            date_validite=today + datetime.timedelta(days=15),
            emise_pour='Marché BTP X')

    def test_attestation_15j_apparait_sous_30_pas_sous_10(self):
        self.assertIn(
            self.attestation,
            list(attestations_expirantes(self.company, within=30)))
        self.assertNotIn(
            self.attestation,
            list(attestations_expirantes(self.company, within=10)))

    def test_endpoint_attestations_expirantes(self):
        api = auth(self.user)
        resp = api.get(
            '/api/django/assurances/attestations/expirantes/', {'within': 30})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)
