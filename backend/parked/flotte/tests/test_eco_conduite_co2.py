"""Tests FLOTTE33 — Éco-conduite & CO₂.

Couvre :
- Selector ``eco_conduite_co2`` :
  - véhicule diesel : CO₂ = litres × 2,68 ; intensité g/km ; score éco 100 sans
    anomalie ;
  - véhicule électrique : CO₂ = 0 ;
  - scope société.
- Endpoint ``/vehicules/<id>/eco-conduite/`` (GET, tout rôle).
"""
import datetime

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import PleinCarburant, Vehicule
from apps.flotte.selectors import eco_conduite_co2

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


D = datetime.date(2026, 6, 1)


class EcoConduiteCo2Tests(TestCase):
    def setUp(self):
        self.co = make_company("eco", "Eco")

    def test_diesel_co2(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="ECO-1", energie="diesel")
        # Deux pleins → 1 segment exploitable (45 L sur 500 km).
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh, date_plein=D,
            kilometrage=1000, quantite=Decimal("40"), prix_total=Decimal("500"))
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh, date_plein=D,
            kilometrage=1500, quantite=Decimal("45"), prix_total=Decimal("600"))
        data = eco_conduite_co2(self.co, veh.id)
        # litres_total agrégé = 45 (segment exploitable) ; CO2 = 45 * 2.68.
        self.assertAlmostEqual(data["co2_kg"], round(45 * 2.68, 2), places=2)
        self.assertEqual(data["distance_totale_km"], 500)
        self.assertEqual(data["score_eco"], 100.0)

    def test_electrique_co2_nul(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="ECO-E", energie="electrique")
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh, date_plein=D,
            kilometrage=1000, quantite=Decimal("20"), unite="kwh",
            prix_total=Decimal("40"))
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh, date_plein=D,
            kilometrage=1200, quantite=Decimal("22"), unite="kwh",
            prix_total=Decimal("44"))
        data = eco_conduite_co2(self.co, veh.id)
        self.assertEqual(data["co2_kg"], 0.0)
        self.assertGreater(data["kwh_total"], 0)


class EcoConduiteApiTests(TestCase):
    def test_endpoint(self):
        co = make_company("eco-api", "Eco Api")
        admin = make_user(co, "eco-admin", "admin")
        veh = Vehicule.objects.create(
            company=co, immatriculation="ECO-API", energie="diesel")
        api = auth(admin)
        resp = api.get(f"/api/django/flotte/vehicules/{veh.id}/eco-conduite/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["co2_kg"], 0.0)
