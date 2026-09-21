"""Tests FLOTTE29 — Journal kilométrique & trajets imputés chantier.

Couvre :
- Modèle ``TrajetChantier`` :
  - création simple + propriété ``distance_calculee_km`` (compteur / saisie) ;
  - validations ``clean`` (actif d'une autre société, km arrivée < départ,
    distance négative).
- Selector ``trajets_chantier_de_la_societe`` / ``journal_kilometrique`` :
  - scope société + filtres ;
  - journal agrégé ventilé par chantier (distance totale + par chantier).
- Endpoints API ``/trajets-chantier/`` :
  - CRUD scopé société (multi-tenant : company posée serveur, jamais du body) ;
  - chantier d'une autre société refusé (validé via installations.selectors) ;
  - action ``journal`` (GET) agrégée.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.flotte.models import (
    ActifFlotte,
    TrajetChantier,
    Vehicule,
)
from apps.flotte.selectors import (
    journal_kilometrique,
    trajets_chantier_de_la_societe,
)

User = get_user_model()

URL = "/api/django/flotte/trajets-chantier/"
JOURNAL_URL = URL + "journal/"


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


def make_actif(company, immat="TRCH-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


def make_chantier(company, ref="CH-1"):
    client = Client.objects.create(company=company, nom="Client " + ref)
    return Installation.objects.create(
        company=company, reference=ref, client=client)


D = datetime.date(2026, 6, 1)


class TrajetChantierModelTests(TestCase):
    def setUp(self):
        self.co = make_company("trch-model", "Trch Model")
        self.actif = make_actif(self.co, "TCMOD")

    def test_distance_calculee_compteur(self):
        t = TrajetChantier.objects.create(
            company=self.co, actif_flotte=self.actif, date_trajet=D,
            km_depart=1000, km_arrivee=1050)
        self.assertEqual(t.distance_calculee_km, 50)

    def test_distance_calculee_saisie(self):
        t = TrajetChantier.objects.create(
            company=self.co, actif_flotte=self.actif, date_trajet=D,
            distance_km=33)
        self.assertEqual(t.distance_calculee_km, 33.0)

    def test_actif_autre_societe_rejete(self):
        autre = make_company("trch-model-b", "B")
        actif_b = make_actif(autre, "B")
        t = TrajetChantier(
            company=self.co, actif_flotte=actif_b, date_trajet=D)
        with self.assertRaises(ValidationError):
            t.full_clean()

    def test_km_arrivee_inferieur_rejete(self):
        t = TrajetChantier(
            company=self.co, actif_flotte=self.actif, date_trajet=D,
            km_depart=1000, km_arrivee=900)
        with self.assertRaises(ValidationError):
            t.full_clean()


class JournalKilometriqueTests(TestCase):
    def setUp(self):
        self.co = make_company("trch-jour", "Trch Jour")
        self.actif = make_actif(self.co, "TCJOUR")
        self.ch = make_chantier(self.co, "CH-J")

    def test_journal_agrege(self):
        TrajetChantier.objects.create(
            company=self.co, actif_flotte=self.actif, date_trajet=D,
            installation_id=self.ch.id, km_depart=0, km_arrivee=50)
        TrajetChantier.objects.create(
            company=self.co, actif_flotte=self.actif, date_trajet=D,
            installation_id=self.ch.id, distance_km=20)
        TrajetChantier.objects.create(
            company=self.co, actif_flotte=self.actif, date_trajet=D,
            distance_km=10)
        data = journal_kilometrique(self.co)
        self.assertEqual(data["nb_trajets"], 3)
        self.assertEqual(data["distance_totale_km"], 80.0)
        # 2 chantiers : l'imputé (id) + le non imputé (None).
        self.assertEqual(len(data["par_chantier"]), 2)
        impute = [ligne for ligne in data["par_chantier"]
                  if ligne["installation_id"] == self.ch.id][0]
        self.assertEqual(impute["distance_km"], 70.0)
        self.assertEqual(impute["chantier_reference"], "CH-J")

    def test_scope_societe(self):
        autre = make_company("trch-jour-b", "B")
        actif_b = make_actif(autre, "B")
        TrajetChantier.objects.create(
            company=autre, actif_flotte=actif_b, date_trajet=D, distance_km=5)
        qs = trajets_chantier_de_la_societe(self.co)
        self.assertEqual(qs.count(), 0)


class TrajetChantierApiTests(TestCase):
    def setUp(self):
        self.co = make_company("trch-api", "Trch Api")
        self.admin = make_user(self.co, "trch-admin", "admin")
        self.actif = make_actif(self.co, "TCAPI")
        self.ch = make_chantier(self.co, "CH-API")

    def test_create_scope_company(self):
        api = auth(self.admin)
        resp = api.post(URL, {
            "actif_flotte": self.actif.id,
            "installation_id": self.ch.id,
            "date_trajet": "2026-06-01",
            "km_depart": 1000, "km_arrivee": 1080,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        t = TrajetChantier.objects.get(id=resp.data["id"])
        self.assertEqual(t.company_id, self.co.id)
        self.assertEqual(t.installation_id, self.ch.id)

    def test_chantier_autre_societe_refuse(self):
        autre = make_company("trch-api-b", "B")
        ch_b = make_chantier(autre, "CH-B")
        api = auth(self.admin)
        resp = api.post(URL, {
            "actif_flotte": self.actif.id,
            "installation_id": ch_b.id,
            "date_trajet": "2026-06-01",
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_action_journal(self):
        TrajetChantier.objects.create(
            company=self.co, actif_flotte=self.actif, date_trajet=D,
            installation_id=self.ch.id, distance_km=25)
        api = auth(self.admin)
        resp = api.get(JOURNAL_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["distance_totale_km"], 25.0)
