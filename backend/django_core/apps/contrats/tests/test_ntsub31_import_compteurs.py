"""Tests NTSUB31 — Import CSV en masse des compteurs d'usage."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import CompteurUsage

User = get_user_model()

IMPORT = "/api/django/contrats/compteurs-usage/import-csv/"

CSV_HEADER = "cible_id,code_compteur,periode_debut,periode_fin,quantite\n"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy="admin")


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


class ImportCompteursServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub31-svc", "Ntsub31Svc")

    def test_import_trois_lignes_dont_un_doublon(self):
        csv_content = CSV_HEADER + (
            "1,interventions,2026-01-01,2026-01-31,5\n"
            "1,interventions,2026-01-01,2026-01-31,8\n"  # doublon → update
            "2,appels_api,2026-01-01,2026-01-31,10\n"
        )
        rapport = services.importer_compteurs_usage_csv(self.co, csv_content)
        # 2 clés distinctes insérées, 1 mise à jour.
        self.assertEqual(rapport['inserees'], 2)
        self.assertEqual(rapport['mises_a_jour'], 1)
        self.assertEqual(rapport['erreurs'], [])
        self.assertEqual(
            CompteurUsage.objects.filter(company=self.co).count(), 2)
        c = CompteurUsage.objects.get(
            company=self.co, cible_id=1, code_compteur='interventions')
        self.assertEqual(c.quantite, Decimal('8'))  # dernière valeur

    def test_lignes_invalides_rapportees(self):
        csv_content = CSV_HEADER + (
            "1,interventions,2026-01-01,2026-01-31,5\n"
            "x,interventions,2026-01-01,2026-01-31,5\n"  # cible_id non int
            "2,,2026-01-01,2026-01-31,5\n"  # code manquant
            "3,c,2026-02-01,2026-01-01,5\n"  # fin < début
        )
        rapport = services.importer_compteurs_usage_csv(self.co, csv_content)
        self.assertEqual(rapport['inserees'], 1)
        self.assertEqual(len(rapport['erreurs']), 3)


class ImportCompteursApiTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub31-api", "Ntsub31Api")
        self.admin = make_user(self.co, "ntsub31-admin")

    def test_endpoint_import(self):
        api = auth(self.admin)
        csv_content = CSV_HEADER + "1,interventions,2026-01-01,2026-01-31,5\n"
        res = api.post(IMPORT, {"contenu": csv_content}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['inserees'], 1)

    def test_endpoint_sans_contenu_400(self):
        api = auth(self.admin)
        res = api.post(IMPORT, {}, format="json")
        self.assertEqual(res.status_code, 400, res.content)
