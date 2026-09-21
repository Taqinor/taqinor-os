"""Tests XFLT24 — Géofencing sur les données télématiques.

Couvre :
- Modèle ``ZoneGeographique`` : création + validations (rayon > 0, plage
  horaire cohérente).
- Service ``evaluer_geofencing`` (haversine) :
  - relevé dans une zone interdite -> alerte ;
  - relevé hors zone -> rien ;
  - relevé dans zone dépôt sans dépassement horaire -> rien ;
  - relevé dans zone à plage horaire, hors plage -> alerte ;
  - purement local : aucune dépendance nouvelle, no-op si aucune zone.
- Endpoints API ``/zones-geographiques/`` :
  - CRUD scopé société, lecture tout rôle / écriture responsable-admin ;
  - action ``evaluer`` (POST) renvoie les alertes détectées.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ActifFlotte, ReleveTelematique, Vehicule, ZoneGeographique
from apps.flotte.services import evaluer_geofencing

User = get_user_model()

URL = "/api/django/flotte/zones-geographiques/"

H = datetime.datetime(2026, 6, 1, 8, 0, 0)

# Casablanca (approx) et un point à ~50 m, un autre à plusieurs km.
LAT_CENTRE = 33.573110
LNG_CENTRE = -7.589843
LAT_PROCHE = 33.573450   # ~40 m au nord
LNG_PROCHE = -7.589843
LAT_LOIN = 33.600000     # plusieurs km
LNG_LOIN = -7.620000


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


def make_actif(company, immat="GEO-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


def make_zone(company, type_zone="interdite", rayon=100, **kwargs):
    return ZoneGeographique.objects.create(
        company=company, nom=kwargs.pop("nom", "Zone Test"),
        type_zone=type_zone, centre_lat=LAT_CENTRE, centre_lng=LNG_CENTRE,
        rayon_metres=rayon, **kwargs)


def make_releve(company, actif, lat, lng, horodatage=H):
    return ReleveTelematique.objects.create(
        company=company, actif_flotte=actif, horodatage=horodatage,
        position_lat=lat, position_lng=lng)


# ── Modèle : création + validations ─────────────────────────────────────────────

class ZoneGeographiqueModelTests(TestCase):
    def setUp(self):
        self.co = make_company("geo-model", "Geo Model")

    def test_creation_simple(self):
        zone = make_zone(self.co)
        self.assertEqual(zone.type_zone, ZoneGeographique.TypeZone.INTERDITE)
        self.assertTrue(zone.actif)

    def test_rayon_negatif_rejete(self):
        zone = ZoneGeographique(
            company=self.co, nom="Z", centre_lat=LAT_CENTRE,
            centre_lng=LNG_CENTRE, rayon_metres=0)
        with self.assertRaises(ValidationError):
            zone.full_clean()

    def test_plage_horaire_incoherente_rejetee(self):
        zone = ZoneGeographique(
            company=self.co, nom="Z", centre_lat=LAT_CENTRE,
            centre_lng=LNG_CENTRE, rayon_metres=100,
            heure_debut_autorisee=datetime.time(18, 0),
            heure_fin_autorisee=datetime.time(8, 0))
        with self.assertRaises(ValidationError):
            zone.full_clean()


# ── Service : évaluation géofencing (haversine, purement local) ────────────────

class EvaluerGeofencingTests(TestCase):
    def setUp(self):
        self.co = make_company("geo-svc", "Geo Svc")
        self.actif = make_actif(self.co, "GSVC")

    def test_releve_en_zone_interdite_alerte(self):
        make_zone(self.co, type_zone="interdite", rayon=100)
        releve = make_releve(self.co, self.actif, LAT_PROCHE, LNG_PROCHE)
        alertes = evaluer_geofencing(self.co, alerter=False)
        self.assertEqual(len(alertes), 1)
        self.assertEqual(alertes[0]['releve_id'], releve.id)
        self.assertIn('interdite', alertes[0]['motif'])

    def test_releve_hors_zone_rien(self):
        make_zone(self.co, type_zone="interdite", rayon=100)
        make_releve(self.co, self.actif, LAT_LOIN, LNG_LOIN)
        alertes = evaluer_geofencing(self.co, alerter=False)
        self.assertEqual(alertes, [])

    def test_releve_zone_depot_sans_horaire_rien(self):
        # Zone dépôt sans plage horaire : aucune alerte (pas interdite, pas
        # de contrainte horaire).
        make_zone(self.co, type_zone="depot", rayon=100)
        make_releve(self.co, self.actif, LAT_PROCHE, LNG_PROCHE)
        alertes = evaluer_geofencing(self.co, alerter=False)
        self.assertEqual(alertes, [])

    def test_releve_hors_plage_horaire_alerte(self):
        make_zone(
            self.co, type_zone="chantier", rayon=100,
            heure_debut_autorisee=datetime.time(8, 0),
            heure_fin_autorisee=datetime.time(18, 0))
        # 22h : hors plage 8h-18h.
        soir = H.replace(hour=22)
        make_releve(self.co, self.actif, LAT_PROCHE, LNG_PROCHE, soir)
        alertes = evaluer_geofencing(self.co, alerter=False)
        self.assertEqual(len(alertes), 1)
        self.assertIn('plage horaire', alertes[0]['motif'])

    def test_releve_dans_plage_horaire_rien(self):
        make_zone(
            self.co, type_zone="chantier", rayon=100,
            heure_debut_autorisee=datetime.time(8, 0),
            heure_fin_autorisee=datetime.time(18, 0))
        make_releve(self.co, self.actif, LAT_PROCHE, LNG_PROCHE, H)  # 8h
        alertes = evaluer_geofencing(self.co, alerter=False)
        self.assertEqual(alertes, [])

    def test_aucune_zone_noop(self):
        make_releve(self.co, self.actif, LAT_PROCHE, LNG_PROCHE)
        self.assertEqual(evaluer_geofencing(self.co, alerter=False), [])

    def test_releve_sans_position_ignore(self):
        make_zone(self.co, type_zone="interdite", rayon=100)
        ReleveTelematique.objects.create(
            company=self.co, actif_flotte=self.actif, horodatage=H)
        self.assertEqual(evaluer_geofencing(self.co, alerter=False), [])

    def test_zone_inactive_ignoree(self):
        make_zone(self.co, type_zone="interdite", rayon=100, actif=False)
        make_releve(self.co, self.actif, LAT_PROCHE, LNG_PROCHE)
        self.assertEqual(evaluer_geofencing(self.co, alerter=False), [])


# ── Endpoints API ────────────────────────────────────────────────────────────────

class ZoneGeographiqueApiTests(TestCase):
    def setUp(self):
        self.co = make_company("geo-api", "Geo Api")
        self.admin = make_user(self.co, "geo-admin", role="admin")
        self.normal = make_user(self.co, "geo-normal", role="normal")

    def test_creation_scopee_societe(self):
        resp = auth(self.admin).post(URL, {
            "nom": "Dépôt Ain Sebaa", "type_zone": "depot",
            "centre_lat": str(LAT_CENTRE), "centre_lng": str(LNG_CENTRE),
            "rayon_metres": 200,
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        zone = ZoneGeographique.objects.get(id=resp.data["id"])
        self.assertEqual(zone.company_id, self.co.id)

    def test_lecture_tout_role(self):
        make_zone(self.co)
        resp = auth(self.normal).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_ecriture_refusee_normal(self):
        resp = auth(self.normal).post(URL, {
            "nom": "Z", "type_zone": "depot",
            "centre_lat": str(LAT_CENTRE), "centre_lng": str(LNG_CENTRE),
            "rayon_metres": 100,
        })
        self.assertEqual(resp.status_code, 403)

    def test_isolation_multi_tenant(self):
        autre = make_company("geo-api-b", "Geo Api B")
        make_zone(autre, nom="Autre société")
        resp = auth(self.admin).get(URL)
        self.assertEqual(rows(resp), [])

    def test_action_evaluer(self):
        make_zone(self.co, type_zone="interdite", rayon=100)
        actif = make_actif(self.co, "GAPI")
        make_releve(self.co, actif, LAT_PROCHE, LNG_PROCHE)
        resp = auth(self.admin).post(URL + "evaluer/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["nb_alertes"], 1)

    def test_filtre_type_zone(self):
        make_zone(self.co, type_zone="depot", nom="D")
        make_zone(self.co, type_zone="interdite", nom="I")
        resp = auth(self.admin).get(URL + "?type_zone=interdite")
        self.assertEqual(len(rows(resp)), 1)
        self.assertEqual(rows(resp)[0]["nom"], "I")
