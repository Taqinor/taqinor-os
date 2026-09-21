"""NTASS19 — Checklist conformité assurance par marché/appel d'offres.

Critère d'acceptation : un marché BTP exigeant une DÉCENNALE ≥ 2M MAD affiche
``conforme`` si une police correspondante est active, sinon ``non_conforme``."""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import (
    Assureur, ExigenceAssuranceMarche, GarantiePolice, PoliceAssurance,
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


class ConformiteMarcheTests(TestCase):
    BASE = '/api/django/assurances/exigences-assurance-marche/'

    def setUp(self):
        self.company = make_company('assurances-p19', 'P19')
        self.user = make_user(self.company, 'assur-p19')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        self.today = datetime.date.today()

    def _exigence(self):
        return ExigenceAssuranceMarche.objects.create(
            company=self.company, marche_ref=777,
            type_police_requis=PoliceAssurance.TypePolice.DECENNALE,
            montant_couverture_minimum=Decimal('2000000.00'))

    def test_non_conforme_sans_police_decennale(self):
        exigence = self._exigence()
        api = auth(self.user)
        resp = api.post(f'{self.BASE}{exigence.id}/verifier/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            resp.data['statut_verification'],
            ExigenceAssuranceMarche.StatutVerification.NON_CONFORME)

    def test_conforme_avec_police_decennale_couverture_suffisante(self):
        police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='DEC-2026-070',
            type_police=PoliceAssurance.TypePolice.DECENNALE,
            date_effet=self.today,
            date_echeance=self.today + datetime.timedelta(days=365),
            statut=PoliceAssurance.Statut.ACTIVE)
        GarantiePolice.objects.create(
            company=self.company, police=police,
            libelle_garantie='Responsabilité décennale',
            plafond_indemnisation=Decimal('3000000.00'))
        exigence = self._exigence()
        api = auth(self.user)
        resp = api.post(f'{self.BASE}{exigence.id}/verifier/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            resp.data['statut_verification'],
            ExigenceAssuranceMarche.StatutVerification.CONFORME)
