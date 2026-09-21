"""Tests FLOTTE30 — Amortissement (lien immobilisations comptables).

Couvre :
- Champ ``Vehicule.immobilisation`` (FK → compta.Immobilisation, nullable).
- Selector ``amortissement_vehicule`` :
  - véhicule sans immobilisation → amortissable=False, montants None ;
  - véhicule rattaché à une immobilisation amortie → VNC lue depuis le module
    compta (lecture cross-app, jamais d'écriture).
- Endpoint ``/vehicules/<id>/amortissement/`` (GET, tout rôle).
"""
import datetime

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta.models import Immobilisation
from apps.compta.services import generer_plan_amortissement
from apps.flotte.models import Vehicule
from apps.flotte.selectors import amortissement_vehicule

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


class AmortissementVehiculeTests(TestCase):
    def setUp(self):
        self.co = make_company("amort", "Amort")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="AM-1", energie="diesel")

    def test_sans_immobilisation(self):
        data = amortissement_vehicule(self.co, self.veh.id)
        self.assertFalse(data["amortissable"])
        self.assertIsNone(data["valeur_nette_comptable"])

    def test_avec_immobilisation_amortie(self):
        immo = Immobilisation.objects.create(
            company=self.co, libelle="Camionnette", categorie="vehicule",
            cout=Decimal("100000.00"),
            date_acquisition=datetime.date(2024, 1, 1))
        generer_plan_amortissement(immo, duree_annees=5)
        self.veh.immobilisation = immo
        self.veh.save(update_fields=["immobilisation"])

        data = amortissement_vehicule(self.co, self.veh.id)
        self.assertTrue(data["amortissable"])
        self.assertEqual(data["immobilisation_id"], immo.id)
        self.assertEqual(data["valeur_origine"], 100000.0)
        # Après plusieurs exercices, la VNC a baissé sous le coût d'origine.
        self.assertLess(data["valeur_nette_comptable"], 100000.0)
        self.assertGreater(data["cumul_amortissements"], 0)


class AmortissementApiTests(TestCase):
    def test_endpoint(self):
        co = make_company("amort-api", "Amort Api")
        admin = make_user(co, "amort-admin", "admin")
        veh = Vehicule.objects.create(
            company=co, immatriculation="AM-API", energie="diesel")
        api = auth(admin)
        resp = api.get(f"/api/django/flotte/vehicules/{veh.id}/amortissement/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data["amortissable"])
