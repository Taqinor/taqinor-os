"""NTASS15 — Lien sinistre → risque ERM (string-FK vers futur NTGRC).

Critère d'acceptation : tant que l'app risques n'existe pas, l'API répond
normalement avec ``risque_libelle=null`` ; une fois construite, un sinistre
lié à un risque affiche son libellé sans FK réelle."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import (
    Assureur, DeclarationSinistre, PoliceAssurance,
)
from apps.assurances.selectors import libelle_risque

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


class RisqueRefTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p15', 'P15')
        self.user = make_user(self.company, 'assur-p15')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='MR-2026-015',
            type_police=PoliceAssurance.TypePolice.MULTIRISQUE,
            date_effet=today, date_echeance=today + datetime.timedelta(days=365))
        self.declaration = DeclarationSinistre.objects.create(
            company=self.company, police=self.police, reference='SIN-2026-500',
            date_survenance=today,
            type_sinistre=DeclarationSinistre.TypeSinistre.INCENDIE,
            risque_ref=42)

    def test_libelle_risque_none_sans_module_ngrc(self):
        # Tant que apps.grc (NTGRC) n'existe pas, la résolution renvoie None.
        self.assertIsNone(libelle_risque(42))
        self.assertIsNone(libelle_risque(None))

    def test_api_repond_risque_libelle_null(self):
        api = auth(self.user)
        resp = api.get(
            f'/api/django/assurances/declarations-sinistre/{self.declaration.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['risque_ref'], 42)
        self.assertIsNone(resp.data['risque_libelle'])
