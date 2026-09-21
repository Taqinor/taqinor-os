"""Tests XFLT11 — Imputation automatique du conducteur sur les infractions.

Couvre :
- Service ``conducteur_a_la_date(vehicule, dt)`` :
  - date couverte par une affectation en cours (date_fin=None) → conducteur ;
  - date couverte par une affectation close (date_fin renseignée) → conducteur ;
  - date hors affectation → None ;
  - vehicule/dt None → None.
- Endpoint ``POST /infractions/`` :
  - infraction datée pendant l'affectation de X et SANS conducteur fourni →
    conducteur=X, imputation_auto=True ;
  - infraction datée HORS affectation → conducteur=None, imputation_auto=False ;
  - conducteur fourni explicitement → imputation_auto=False, jamais écrasé.
- Filtre ``?refacturables=1`` : ne retourne que les infractions
  ``refacture_conducteur=True``.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    AffectationConducteur,
    Conducteur,
    Infraction,
    Vehicule,
)
from apps.flotte.services import conducteur_a_la_date

User = get_user_model()

URL = "/api/django/flotte/infractions/"


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


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


def make_actif(company, immat="IMP-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh), veh


def make_conducteur(company, nom="Ahmed"):
    return Conducteur.objects.create(company=company, nom=nom)


class ConducteurALaDateServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("imp-svc", "Imputation Svc")
        self.actif, self.veh = make_actif(self.co)
        self.cond = make_conducteur(self.co)

    def test_affectation_en_cours_couvre_toute_date_future(self):
        AffectationConducteur.objects.create(
            company=self.co, conducteur=self.cond, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1), date_fin=None)
        resolu = conducteur_a_la_date(self.veh, datetime.date(2026, 6, 1))
        self.assertEqual(resolu, self.cond)

    def test_affectation_close_couvre_sa_periode(self):
        AffectationConducteur.objects.create(
            company=self.co, conducteur=self.cond, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1),
            date_fin=datetime.date(2026, 3, 31))
        resolu = conducteur_a_la_date(self.veh, datetime.date(2026, 2, 15))
        self.assertEqual(resolu, self.cond)

    def test_date_hors_affectation_retourne_none(self):
        AffectationConducteur.objects.create(
            company=self.co, conducteur=self.cond, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1),
            date_fin=datetime.date(2026, 3, 31))
        resolu = conducteur_a_la_date(self.veh, datetime.date(2026, 5, 1))
        self.assertIsNone(resolu)

    def test_vehicule_ou_dt_none(self):
        self.assertIsNone(conducteur_a_la_date(None, datetime.date(2026, 1, 1)))
        self.assertIsNone(conducteur_a_la_date(self.veh, None))


class InfractionImputationApiTests(TestCase):
    def setUp(self):
        self.co = make_company("imp-api", "Imputation Api")
        self.actif, self.veh = make_actif(self.co)
        self.cond = make_conducteur(self.co)
        self.user = make_user(self.co, "imp-user")
        AffectationConducteur.objects.create(
            company=self.co, conducteur=self.cond, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1), date_fin=None)

    def test_infraction_pendant_affectation_impute_automatiquement(self):
        resp = auth(self.user).post(URL, {
            "actif_flotte": self.actif.id,
            "date_infraction": "2026-06-01",
            "type_infraction": "exces_vitesse",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["conducteur"], self.cond.id)
        self.assertTrue(resp.data["imputation_auto"])

    def test_infraction_hors_affectation_conducteur_null(self):
        veh2 = Vehicule.objects.create(
            company=self.co, immatriculation="IMP-2", energie="diesel")
        actif2 = ActifFlotte.objects.create(company=self.co, vehicule=veh2)
        resp = auth(self.user).post(URL, {
            "actif_flotte": actif2.id,
            "date_infraction": "2026-06-01",
            "type_infraction": "stationnement",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data["conducteur"])
        self.assertFalse(resp.data["imputation_auto"])

    def test_conducteur_fourni_explicitement_non_ecrase(self):
        autre = make_conducteur(self.co, nom="Autre")
        resp = auth(self.user).post(URL, {
            "actif_flotte": self.actif.id,
            "conducteur": autre.id,
            "date_infraction": "2026-06-01",
            "type_infraction": "feu_rouge",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["conducteur"], autre.id)
        self.assertFalse(resp.data["imputation_auto"])

    def test_filtre_refacturables(self):
        Infraction.objects.create(
            company=self.co, actif_flotte=self.actif,
            date_infraction=datetime.date(2026, 1, 1),
            refacture_conducteur=True)
        Infraction.objects.create(
            company=self.co, actif_flotte=self.actif,
            date_infraction=datetime.date(2026, 1, 2),
            refacture_conducteur=False)
        resp = auth(self.user).get(URL, {"refacturables": "1"})
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertTrue(data[0]["refacture_conducteur"])
