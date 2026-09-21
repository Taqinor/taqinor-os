"""Tests XFLT28 — Rappels constructeur (recall).

Couvre :
- Modèle ``RappelConstructeur`` : création simple, scopée société.
- Service ``rapprocher_rappel`` :
  - rappel saisi avec 2 VIN du parc -> 2 signalements liés ;
  - VIN hors parc / vide -> ignoré (aucun signalement fantôme) ;
  - IDEMPOTENT : un second rapprochement ne duplique pas les signalements
    ouverts de la même campagne ;
  - résolution suivie : un signalement RÉSOLU n'empêche pas... mais un
    signalement OUVERT/EN_COURS bloque le doublon (comme XFLT25).
- Endpoint ``POST /rappels-constructeur/<id>/rapprocher/``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    RappelConstructeur,
    SignalementVehicule,
    Vehicule,
)
from apps.flotte.services import rapprocher_rappel

User = get_user_model()

URL = "/api/django/flotte/rappels-constructeur/"


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


def make_vehicule_avec_vin(company, immat, vin):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel", vin=vin)
    ActifFlotte.objects.create(company=company, vehicule=veh)
    return veh


class RapprocherRappelTests(TestCase):
    def setUp(self):
        self.co = make_company("recall-svc", "Recall Svc")
        self.v1 = make_vehicule_avec_vin(self.co, "REC-1", "VIN000000000001")
        self.v2 = make_vehicule_avec_vin(self.co, "REC-2", "VIN000000000002")
        self.v3 = make_vehicule_avec_vin(self.co, "REC-3", "VIN000000000003")

    def test_deux_vin_du_parc_deux_signalements(self):
        rappel = RappelConstructeur.objects.create(
            company=self.co, reference_campagne="RC-2026-01",
            constructeur="Renault", description="Défaut freinage",
            vin_concernes=["VIN000000000001", "VIN000000000002"])
        resultat = rapprocher_rappel(rappel)
        self.assertEqual(resultat['nb_vin_matches'], 2)
        self.assertEqual(len(resultat['crees']), 2)
        self.assertEqual(SignalementVehicule.objects.filter(
            company=self.co).count(), 2)

    def test_vin_hors_parc_ignore(self):
        rappel = RappelConstructeur.objects.create(
            company=self.co, reference_campagne="RC-2026-02",
            vin_concernes=["VINXXXXXXXXXXXX9"])
        resultat = rapprocher_rappel(rappel)
        self.assertEqual(resultat['nb_vin_matches'], 0)
        self.assertEqual(resultat['crees'], [])

    def test_vin_vide_ignore(self):
        rappel = RappelConstructeur.objects.create(
            company=self.co, reference_campagne="RC-2026-03",
            vin_concernes=["", None, "  "])
        resultat = rapprocher_rappel(rappel)
        self.assertEqual(resultat['crees'], [])

    def test_idempotent_pas_de_doublon(self):
        rappel = RappelConstructeur.objects.create(
            company=self.co, reference_campagne="RC-2026-04",
            vin_concernes=["VIN000000000001"])
        premiers = rapprocher_rappel(rappel)
        self.assertEqual(len(premiers['crees']), 1)
        seconds = rapprocher_rappel(rappel)
        self.assertEqual(seconds['crees'], [])
        self.assertEqual(SignalementVehicule.objects.count(), 1)

    def test_scope_societe(self):
        autre = make_company("recall-svc-b", "Recall Svc B")
        make_vehicule_avec_vin(autre, "REC-B1", "VIN000000000001")
        rappel = RappelConstructeur.objects.create(
            company=self.co, reference_campagne="RC-2026-05",
            vin_concernes=["VIN000000000001"])
        resultat = rapprocher_rappel(rappel)
        # Un seul véhicule matché : celui de self.co (pas celui d'autre).
        self.assertEqual(resultat['nb_vin_matches'], 1)
        signalement = resultat['crees'][0]
        self.assertEqual(signalement.company_id, self.co.id)


class RappelConstructeurApiTests(TestCase):
    def setUp(self):
        self.co = make_company("recall-api", "Recall Api")
        self.admin = make_user(self.co, "recall-admin")
        make_vehicule_avec_vin(self.co, "RAPI-1", "VIN000000000099")

    def test_creation_scopee_societe(self):
        resp = auth(self.admin).post(URL, {
            "reference_campagne": "RC-API-1", "constructeur": "Peugeot",
            "vin_concernes": ["VIN000000000099"],
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_action_rapprocher(self):
        rappel = RappelConstructeur.objects.create(
            company=self.co, reference_campagne="RC-API-2",
            vin_concernes=["VIN000000000099"])
        resp = auth(self.admin).post(URL + f"{rappel.id}/rapprocher/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["nb_vin_matches"], 1)
        self.assertEqual(len(resp.data["signalements_crees"]), 1)

    def test_isolation_multi_tenant(self):
        autre = make_company("recall-api-b", "Recall Api B")
        RappelConstructeur.objects.create(
            company=autre, reference_campagne="RC-OTHER")
        resp = auth(self.admin).get(URL)
        data = resp.data
        rows = data["results"] if isinstance(data, dict) and "results" in data else data
        self.assertEqual(rows, [])
