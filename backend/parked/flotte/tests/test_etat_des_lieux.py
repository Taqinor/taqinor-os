"""Tests FLOTTE11 — EtatDesLieux (check-list départ/retour + photos).

Couvre :
- Création (company forcée côté serveur), points + photos JSON, nb_photos.
- Isolation multi-tenant (liste + retrieve).
- Validation niveau_carburant (hors 0-100 → 400).
- Validation cross-société (véhicule/réservation d'une autre société → 400).
- Filtres ``?vehicule=``, ``?moment=``, ``?reservation=``.
- Selector ``etats_des_lieux_du_vehicule`` scopé société.
- Permissions.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import EtatDesLieux, ReservationVehicule, Vehicule
from apps.flotte.selectors import etats_des_lieux_du_vehicule

User = get_user_model()

URL = "/api/django/flotte/etats-des-lieux/"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


def make_vehicule(company, immat="1234-A-00"):
    return Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel"
    )


def now_iso():
    return timezone.now().replace(microsecond=0).isoformat()


# ── Selector ──────────────────────────────────────────────────────────────────

class EtatDesLieuxSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company("edl-sel-a", "EDL Sel A")
        self.co_b = make_company("edl-sel-b", "EDL Sel B")
        self.veh_a = make_vehicule(self.co_a, "DD-1")
        self.veh_b = make_vehicule(self.co_b, "DD-2")

    def test_scope(self):
        EtatDesLieux.objects.create(
            company=self.co_a, vehicule=self.veh_a,
            date_constat=timezone.now())
        EtatDesLieux.objects.create(
            company=self.co_b, vehicule=self.veh_b,
            date_constat=timezone.now())
        qs = etats_des_lieux_du_vehicule(self.co_a, self.veh_a.id)
        self.assertEqual(qs.count(), 1)
        # La société B ne voit pas l'EDL de A.
        self.assertEqual(
            etats_des_lieux_du_vehicule(self.co_b, self.veh_a.id).count(), 0)


# ── API ───────────────────────────────────────────────────────────────────────

class EtatDesLieuxApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("edl-api-a", "EDL API A")
        self.co_b = make_company("edl-api-b", "EDL API B")
        self.admin_a = make_user(self.co_a, "edl-admin-a", "admin")
        self.user_a = make_user(self.co_a, "edl-user-a", "normal")
        self.veh_a = make_vehicule(self.co_a, "EE-1")
        self.veh_b = make_vehicule(self.co_b, "EE-2")

    def test_create_forces_company_and_photos(self):
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh_a.id,
            "moment": "depart",
            "date_constat": now_iso(),
            "kilometrage": 12000,
            "niveau_carburant": 80,
            "points": [{"point": "Pneus", "ok": True}],
            "photos": ["flotte/edl/a.jpg", "flotte/edl/b.jpg"],
            "company": self.co_b.id,  # ignorée
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        edl = EtatDesLieux.objects.get(id=resp.data["id"])
        self.assertEqual(edl.company_id, self.co_a.id)
        self.assertEqual(resp.data["nb_photos"], 2)
        self.assertEqual(len(resp.data["points"]), 1)

    def test_niveau_carburant_out_of_range_rejected(self):
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh_a.id,
            "moment": "depart",
            "date_constat": now_iso(),
            "niveau_carburant": 150,
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("niveau_carburant", resp.data)

    def test_photos_must_be_list(self):
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh_a.id,
            "moment": "depart",
            "date_constat": now_iso(),
            "photos": "pas-une-liste",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_vehicule_other_company_rejected(self):
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh_b.id,
            "moment": "depart",
            "date_constat": now_iso(),
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_reservation_other_company_rejected(self):
        resa_b = ReservationVehicule.objects.create(
            company=self.co_b, vehicule=self.veh_b,
            debut=timezone.now(),
            fin=timezone.now() + datetime.timedelta(hours=2))
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh_a.id,
            "reservation": resa_b.id,
            "moment": "depart",
            "date_constat": now_iso(),
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_tenant_isolation_list(self):
        EtatDesLieux.objects.create(
            company=self.co_a, vehicule=self.veh_a,
            date_constat=timezone.now())
        edl_b = EtatDesLieux.objects.create(
            company=self.co_b, vehicule=self.veh_b,
            date_constat=timezone.now())
        resp = auth(self.admin_a).get(URL)
        ids = {r["id"] for r in rows(resp)}
        self.assertNotIn(edl_b.id, ids)

    def test_cannot_retrieve_other_company(self):
        edl_b = EtatDesLieux.objects.create(
            company=self.co_b, vehicule=self.veh_b,
            date_constat=timezone.now())
        resp = auth(self.admin_a).get(f"{URL}{edl_b.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_filter_by_moment(self):
        e1 = EtatDesLieux.objects.create(
            company=self.co_a, vehicule=self.veh_a,
            moment="depart", date_constat=timezone.now())
        EtatDesLieux.objects.create(
            company=self.co_a, vehicule=self.veh_a,
            moment="retour", date_constat=timezone.now())
        resp = auth(self.admin_a).get(f"{URL}?moment=depart")
        ids = [r["id"] for r in rows(resp)]
        self.assertEqual(ids, [e1.id])

    def test_filter_by_vehicule(self):
        veh2 = make_vehicule(self.co_a, "EE-3")
        e1 = EtatDesLieux.objects.create(
            company=self.co_a, vehicule=self.veh_a,
            date_constat=timezone.now())
        EtatDesLieux.objects.create(
            company=self.co_a, vehicule=veh2, date_constat=timezone.now())
        resp = auth(self.admin_a).get(f"{URL}?vehicule={self.veh_a.id}")
        ids = [r["id"] for r in rows(resp)]
        self.assertEqual(ids, [e1.id])

    def test_read_allowed_for_any_role(self):
        self.assertEqual(auth(self.user_a).get(URL).status_code, 200)

    def test_write_requires_responsable_or_admin(self):
        resp = auth(self.user_a).post(URL, {
            "vehicule": self.veh_a.id,
            "moment": "depart",
            "date_constat": now_iso(),
        }, format="json")
        self.assertEqual(resp.status_code, 403)
