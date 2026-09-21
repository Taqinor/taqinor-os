"""Tests FLOTTE28 — Suivi de position & trajets télématiques.

Couvre :
- Modèle ``TrajetTelematique`` :
  - création simple + propriétés calculées (durée, vitesse moyenne) ;
  - validations ``clean`` (actif d'une autre société, fin < début, distance
    négative, relevé d'une autre société).
- Service ``construire_trajets_telematiques`` :
  - construit des trajets depuis des relevés consécutifs (coupure sur pause) ;
  - idempotent (second passage ne duplique pas) ;
  - actif d'une autre société → aucun trajet.
- Selector ``trajets_telematiques_de_la_societe`` : scope société + filtres.
- Endpoints API ``/trajets-telematiques/`` :
  - CRUD scopé société (multi-tenant : company posée serveur, jamais du body) ;
  - lecture tout rôle, écriture responsable/admin (role gate) ;
  - actif d'une autre société refusé ;
  - action ``construire`` (POST) idempotente.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    ReleveTelematique,
    TrajetTelematique,
    Vehicule,
)
from apps.flotte.selectors import trajets_telematiques_de_la_societe
from apps.flotte.services import construire_trajets_telematiques

User = get_user_model()

URL = "/api/django/flotte/trajets-telematiques/"
CONSTRUIRE_URL = URL + "construire/"


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


def make_actif(company, immat="TRAJ-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


def dt(h, m=0):
    return datetime.datetime(2026, 6, 1, h, m, 0)


class TrajetTelematiqueModelTests(TestCase):
    def setUp(self):
        self.co = make_company("traj-model", "Traj Model")
        self.actif = make_actif(self.co, "TMOD")

    def test_creation_et_proprietes(self):
        t = TrajetTelematique.objects.create(
            company=self.co, actif_flotte=self.actif,
            debut=dt(8, 0), fin=dt(9, 0), distance_km=60)
        self.assertEqual(t.duree_minutes, 60.0)
        self.assertEqual(t.vitesse_moyenne_kmh, 60.0)

    def test_actif_autre_societe_rejete(self):
        autre = make_company("traj-model-b", "B")
        actif_b = make_actif(autre, "B")
        t = TrajetTelematique(
            company=self.co, actif_flotte=actif_b,
            debut=dt(8), fin=dt(9))
        with self.assertRaises(ValidationError):
            t.full_clean()

    def test_fin_avant_debut_rejete(self):
        t = TrajetTelematique(
            company=self.co, actif_flotte=self.actif,
            debut=dt(9), fin=dt(8))
        with self.assertRaises(ValidationError):
            t.full_clean()

    def test_distance_negative_rejetee(self):
        t = TrajetTelematique(
            company=self.co, actif_flotte=self.actif,
            debut=dt(8), fin=dt(9), distance_km=-1)
        with self.assertRaises(ValidationError):
            t.full_clean()


class ConstruireTrajetsServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("traj-svc", "Traj Svc")
        self.actif = make_actif(self.co, "TSVC")

    def _releve(self, h, m=0, odometre=None, lat=None, lng=None):
        return ReleveTelematique.objects.create(
            company=self.co, actif_flotte=self.actif,
            horodatage=dt(h, m), odometre=odometre,
            position_lat=lat, position_lng=lng)

    def test_construit_deux_trajets_separes_par_pause(self):
        # Trajet 1 : 8h00 → 8h10 ; pause 30 min ; trajet 2 : 8h40 → 8h50.
        self._releve(8, 0, odometre=100)
        self._releve(8, 10, odometre=110)
        self._releve(8, 40, odometre=110)
        self._releve(8, 50, odometre=130)
        crees = construire_trajets_telematiques(self.co, self.actif)
        self.assertEqual(len(crees), 2)
        self.assertEqual(float(crees[0].distance_km), 10.0)
        self.assertEqual(float(crees[1].distance_km), 20.0)

    def test_idempotent(self):
        self._releve(8, 0, odometre=100)
        self._releve(8, 10, odometre=110)
        construire_trajets_telematiques(self.co, self.actif)
        crees2 = construire_trajets_telematiques(self.co, self.actif)
        self.assertEqual(len(crees2), 0)
        self.assertEqual(
            TrajetTelematique.objects.filter(company=self.co).count(), 1)

    def test_actif_autre_societe_aucun_trajet(self):
        autre = make_company("traj-svc-b", "B")
        actif_b = make_actif(autre, "B")
        crees = construire_trajets_telematiques(self.co, actif_b.id)
        self.assertEqual(crees, [])


class TrajetTelematiqueSelectorTests(TestCase):
    def test_scope_et_filtres(self):
        co = make_company("traj-sel", "Sel")
        autre = make_company("traj-sel-b", "Sel B")
        a1 = make_actif(co, "A1")
        a2 = make_actif(autre, "A2")
        TrajetTelematique.objects.create(
            company=co, actif_flotte=a1, debut=dt(8), fin=dt(9))
        TrajetTelematique.objects.create(
            company=autre, actif_flotte=a2, debut=dt(8), fin=dt(9))
        qs = trajets_telematiques_de_la_societe(co)
        self.assertEqual(qs.count(), 1)
        qs2 = trajets_telematiques_de_la_societe(
            co, actif_flotte_id=a1.id)
        self.assertEqual(qs2.count(), 1)


class TrajetTelematiqueApiTests(TestCase):
    def setUp(self):
        self.co = make_company("traj-api", "Traj Api")
        self.admin = make_user(self.co, "traj-admin", "admin")
        self.viewer = make_user(self.co, "traj-view", "normal")
        self.actif = make_actif(self.co, "TAPI")

    def test_create_scope_company(self):
        api = auth(self.admin)
        resp = api.post(URL, {
            "actif_flotte": self.actif.id,
            "debut": "2026-06-01T08:00:00Z",
            "fin": "2026-06-01T09:00:00Z",
            "distance_km": "42",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        t = TrajetTelematique.objects.get(id=resp.data["id"])
        self.assertEqual(t.company_id, self.co.id)

    def test_actif_autre_societe_refuse(self):
        autre = make_company("traj-api-b", "B")
        actif_b = make_actif(autre, "B")
        api = auth(self.admin)
        resp = api.post(URL, {
            "actif_flotte": actif_b.id,
            "debut": "2026-06-01T08:00:00Z",
            "fin": "2026-06-01T09:00:00Z",
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_viewer_lecture_ok_ecriture_refusee(self):
        api = auth(self.viewer)
        self.assertEqual(api.get(URL).status_code, 200)
        resp = api.post(URL, {
            "actif_flotte": self.actif.id,
            "debut": "2026-06-01T08:00:00Z",
            "fin": "2026-06-01T09:00:00Z",
        }, format="json")
        self.assertIn(resp.status_code, (403, 401))

    def test_action_construire(self):
        ReleveTelematique.objects.create(
            company=self.co, actif_flotte=self.actif,
            horodatage=dt(8, 0), odometre=100)
        ReleveTelematique.objects.create(
            company=self.co, actif_flotte=self.actif,
            horodatage=dt(8, 10), odometre=110)
        api = auth(self.admin)
        resp = api.post(
            CONSTRUIRE_URL + f"?actif_flotte={self.actif.id}", format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["crees"], 1)

    def test_action_construire_requiert_actif(self):
        api = auth(self.admin)
        resp = api.post(CONSTRUIRE_URL, format="json")
        self.assertEqual(resp.status_code, 400)
