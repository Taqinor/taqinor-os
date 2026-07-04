"""Tests XFLT14 — Garanties véhicule & pièces + alerte réparation sous garantie.

Couvre :
- Modèle ``GarantieFlotte`` :
  - ``date_fin()`` calculée depuis ``date_debut`` + ``duree_mois`` ;
  - ``couvre(today, kilometrage)`` : dans la fenêtre durée + km → True ;
    date expirée → False ; km dépassé → False.
- Service ``garantie_active_pour(actif, today)`` : retourne les garanties
  actives, lit le kilométrage courant du véhicule.
- Endpoint ``POST /ordres-reparation/`` : actif sous garantie active →
  ``sous_garantie=True`` posé automatiquement (jamais accepté du body) ;
  garantie expirée (date ou km) → ``sous_garantie=False``.
- CRUD ``/garanties/`` scopé société.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ActifFlotte, GarantieFlotte, Vehicule
from apps.flotte.services import garantie_active_pour

User = get_user_model()

URL_OR = "/api/django/flotte/ordres-reparation/"
URL_GARANTIES = "/api/django/flotte/garanties/"


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


def make_actif(company, immat="GAR-1", kilometrage=0):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel",
        kilometrage=kilometrage)
    return ActifFlotte.objects.create(company=company, vehicule=veh)


class GarantieFlotteModelTests(TestCase):
    def setUp(self):
        self.co = make_company("gar-model", "Gar Model")
        self.actif = make_actif(self.co)

    def test_date_fin_calculee(self):
        garantie = GarantieFlotte.objects.create(
            company=self.co, actif_flotte=self.actif, composant="vehicule",
            duree_mois=24, date_debut=datetime.date(2025, 1, 15))
        self.assertEqual(garantie.date_fin(), datetime.date(2027, 1, 15))

    def test_couvre_dans_la_fenetre(self):
        garantie = GarantieFlotte.objects.create(
            company=self.co, actif_flotte=self.actif, composant="moteur",
            duree_mois=12, date_debut=datetime.date(2026, 1, 1))
        self.assertTrue(garantie.couvre(today=datetime.date(2026, 6, 1)))

    def test_couvre_date_expiree(self):
        garantie = GarantieFlotte.objects.create(
            company=self.co, actif_flotte=self.actif, composant="moteur",
            duree_mois=12, date_debut=datetime.date(2024, 1, 1))
        self.assertFalse(garantie.couvre(today=datetime.date(2026, 6, 1)))

    def test_couvre_km_depasse(self):
        garantie = GarantieFlotte.objects.create(
            company=self.co, actif_flotte=self.actif, composant="moteur",
            duree_km=50000, date_debut=datetime.date(2020, 1, 1))
        self.assertFalse(garantie.couvre(
            today=datetime.date(2026, 1, 1), kilometrage=60000))
        self.assertTrue(garantie.couvre(
            today=datetime.date(2026, 1, 1), kilometrage=40000))


class GarantieActiveServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("gar-svc", "Gar Svc")

    def test_retourne_garanties_actives(self):
        actif = make_actif(self.co, kilometrage=10000)
        GarantieFlotte.objects.create(
            company=self.co, actif_flotte=actif, composant="vehicule",
            duree_mois=24, date_debut=datetime.date(2026, 1, 1))
        actives = garantie_active_pour(actif, today=datetime.date(2026, 6, 1))
        self.assertEqual(len(actives), 1)

    def test_aucune_garantie_active(self):
        actif = make_actif(self.co)
        actives = garantie_active_pour(actif, today=datetime.date(2026, 6, 1))
        self.assertEqual(actives, [])


class OrdreReparationSousGarantieApiTests(TestCase):
    def setUp(self):
        self.co = make_company("gar-api", "Gar Api")
        self.user = make_user(self.co, "gar-user")

    def test_or_sur_actif_garanti_flag_et_warning(self):
        actif = make_actif(self.co, immat="GAR-A1", kilometrage=5000)
        GarantieFlotte.objects.create(
            company=self.co, actif_flotte=actif, composant="vehicule",
            duree_mois=36, date_debut=datetime.date(2026, 1, 1))
        resp = auth(self.user).post(URL_OR, {
            "actif_flotte": actif.id,
            "date_ouverture": "2026-06-01",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data["sous_garantie"])

    def test_or_garantie_expiree_pas_de_flag(self):
        actif = make_actif(self.co, immat="GAR-A2", kilometrage=5000)
        GarantieFlotte.objects.create(
            company=self.co, actif_flotte=actif, composant="vehicule",
            duree_mois=12, date_debut=datetime.date(2020, 1, 1))
        resp = auth(self.user).post(URL_OR, {
            "actif_flotte": actif.id,
            "date_ouverture": "2026-06-01",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data["sous_garantie"])

    def test_sous_garantie_non_acceptee_du_body(self):
        actif = make_actif(self.co, immat="GAR-A3")
        resp = auth(self.user).post(URL_OR, {
            "actif_flotte": actif.id,
            "date_ouverture": "2026-06-01",
            "sous_garantie": True,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data["sous_garantie"])


class GarantieFlotteCrudApiTests(TestCase):
    def setUp(self):
        self.co = make_company("gar-crud", "Gar Crud")
        self.user = make_user(self.co, "gar-crud-user")

    def test_creation_et_filtre_actif(self):
        actif = make_actif(self.co, immat="GAR-C1")
        resp = auth(self.user).post(URL_GARANTIES, {
            "actif_flotte": actif.id,
            "composant": "batterie",
            "duree_mois": 60,
            "date_debut": "2026-01-01",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)

        resp = auth(self.user).get(URL_GARANTIES, {"actif_flotte": actif.id})
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        rows = data["results"] if isinstance(data, dict) and "results" in data \
            else data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["composant"], "batterie")
