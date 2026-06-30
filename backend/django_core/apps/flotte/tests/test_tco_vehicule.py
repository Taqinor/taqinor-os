"""Tests FLOTTE31 — Coût total de possession (TCO) par véhicule.

Couvre :
- Selector ``tco_vehicule`` :
  - véhicule sans coûts → tous postes à 0, cout_total 0 ;
  - agrégation carburant (FLOTTE12) + réparations (FLOTTE17) + infractions
    (FLOTTE26) + sinistres (FLOTTE25) ; coût par km dérivé du carnet ;
  - scope société (n'inclut pas les coûts d'une autre société).
- Endpoint ``/vehicules/<id>/tco/`` (GET, tout rôle).
"""
import datetime

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    Infraction,
    OrdreReparation,
    PleinCarburant,
    Sinistre,
    Vehicule,
)
from apps.flotte.selectors import tco_vehicule

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


class TcoVehiculeTests(TestCase):
    def setUp(self):
        self.co = make_company("tco", "TCO")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="TCO-1", energie="diesel")
        self.actif = ActifFlotte.objects.create(
            company=self.co, vehicule=self.veh)

    def test_sans_couts(self):
        data = tco_vehicule(self.co, self.veh.id)
        self.assertEqual(data["cout_total"], 0)
        self.assertIsNone(data["cout_par_km"])

    def test_agregation_couts(self):
        PleinCarburant.objects.create(
            company=self.co, vehicule=self.veh, date_plein=D,
            kilometrage=1000, quantite=Decimal("40"), prix_total=Decimal("500"))
        PleinCarburant.objects.create(
            company=self.co, vehicule=self.veh, date_plein=D,
            kilometrage=1500, quantite=Decimal("45"), prix_total=Decimal("600"))
        OrdreReparation.objects.create(
            company=self.co, actif_flotte=self.actif, date_ouverture=D,
            cout_main_oeuvre=Decimal("300"), cout_pieces=Decimal("200"))
        Infraction.objects.create(
            company=self.co, actif_flotte=self.actif, date_infraction=D,
            montant_amende=Decimal("400"))
        Sinistre.objects.create(
            company=self.co, actif_flotte=self.actif, date_sinistre=D,
            description="x", franchise=Decimal("1000"))

        data = tco_vehicule(self.co, self.veh.id)
        self.assertEqual(data["carburant"], 1100.0)
        self.assertEqual(data["reparations"], 500.0)
        self.assertEqual(data["infractions"], 400.0)
        self.assertEqual(data["sinistres"], 1000.0)
        self.assertEqual(data["cout_total"], 3000.0)
        # Distance carnet = 500 km → coût/km = 3000 / 500 = 6.0.
        self.assertEqual(data["distance_totale_km"], 500)
        self.assertEqual(data["cout_par_km"], 6.0)

    def test_scope_societe(self):
        autre = make_company("tco-b", "B")
        veh_b = Vehicule.objects.create(
            company=autre, immatriculation="B", energie="diesel")
        PleinCarburant.objects.create(
            company=autre, vehicule=veh_b, date_plein=D,
            kilometrage=1, quantite=Decimal("10"), prix_total=Decimal("999"))
        data = tco_vehicule(self.co, self.veh.id)
        self.assertEqual(data["carburant"], 0)


class TcoApiTests(TestCase):
    def test_endpoint(self):
        co = make_company("tco-api", "TCO Api")
        admin = make_user(co, "tco-admin", "admin")
        veh = Vehicule.objects.create(
            company=co, immatriculation="TCO-API", energie="diesel")
        api = auth(admin)
        resp = api.get(f"/api/django/flotte/vehicules/{veh.id}/tco/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["cout_total"], 0)
