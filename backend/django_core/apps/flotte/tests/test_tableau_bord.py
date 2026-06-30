"""Tests FLOTTE35 — Tableau de bord flotte (dispo/échéances/coûts/conso).

Couvre :
- Selector ``tableau_bord_flotte`` :
  - ventilation véhicules/engins par statut + disponibles ;
  - coûts (réparations + carburant) ;
  - demandes de pool en attente ;
  - scope société.
- Endpoint ``/vehicules/tableau-bord/`` (GET, tout rôle).
"""
import datetime

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    DemandeVehicule,
    EnginRoulant,
    PleinCarburant,
    Vehicule,
)
from apps.flotte.selectors import tableau_bord_flotte

User = get_user_model()

URL = "/api/django/flotte/vehicules/tableau-bord/"


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


class TableauBordTests(TestCase):
    def setUp(self):
        self.co = make_company("tdb", "TDB")

    def test_synthese(self):
        Vehicule.objects.create(
            company=self.co, immatriculation="V1", energie="diesel",
            statut="actif")
        veh2 = Vehicule.objects.create(
            company=self.co, immatriculation="V2", energie="diesel",
            statut="maintenance")
        EnginRoulant.objects.create(
            company=self.co, nom="Nacelle", statut="actif")
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh2, date_plein=D,
            kilometrage=10, quantite=Decimal("30"), prix_total=Decimal("450"))
        u = make_user(self.co, "tdb-u", "normal")
        DemandeVehicule.objects.create(
            company=self.co, demandeur=u, besoin="x",
            date_debut_souhaitee=D, date_fin_souhaitee=D)

        data = tableau_bord_flotte(self.co)
        self.assertEqual(data["vehicules"]["total"], 2)
        self.assertEqual(data["vehicules"]["disponibles"], 1)
        self.assertEqual(data["engins"]["total"], 1)
        self.assertEqual(data["couts"]["carburant_total"], 450.0)
        self.assertEqual(data["pool"]["demandes_en_attente"], 1)

    def test_scope_societe(self):
        autre = make_company("tdb-b", "B")
        Vehicule.objects.create(
            company=autre, immatriculation="B", energie="diesel")
        data = tableau_bord_flotte(self.co)
        self.assertEqual(data["vehicules"]["total"], 0)


class TableauBordApiTests(TestCase):
    def test_endpoint(self):
        co = make_company("tdb-api", "TDB Api")
        admin = make_user(co, "tdb-admin", "admin")
        api = auth(admin)
        resp = api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn("vehicules", resp.data)
        self.assertIn("echeances", resp.data)
