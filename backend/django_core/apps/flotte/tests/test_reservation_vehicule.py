"""Tests FLOTTE10 — ReservationVehicule + détection de conflit.

Couvre :
- Création d'une réservation (company forcée côté serveur).
- Isolation multi-tenant (société A ne voit pas les réservations de société B).
- Validation plage horaire (fin <= debut → 400).
- Validation cross-société (véhicule/conducteur d'une autre société → 400).
- Détection de conflit : chevauchement de deux réservations actives → 400 ;
  créneaux adjacents (bornes demi-ouvertes) → OK ; réservation annulée n'occupe
  pas le véhicule ; un autre véhicule ne conflitte pas.
- Service ``reservations_en_conflit`` et selector ``reservations_de_la_societe``.
- Filtres ``?vehicule=``, ``?statut=``, ``?actives=``.
- Permissions (lecture tout rôle, écriture responsable/admin).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import Conducteur, ReservationVehicule, Vehicule
from apps.flotte.selectors import reservations_de_la_societe
from apps.flotte.services import reservations_en_conflit

User = get_user_model()

URL = "/api/django/flotte/reservations/"


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def dt(day, hour=8):
    base = timezone.now().replace(
        hour=hour, minute=0, second=0, microsecond=0)
    return base + datetime.timedelta(days=day)


def make_resa(company, vehicule, debut, fin, statut="confirmee"):
    return ReservationVehicule.objects.create(
        company=company, vehicule=vehicule, debut=debut, fin=fin, statut=statut)


# ── Service de conflit (unité) ────────────────────────────────────────────────

class ConflitServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("resa-svc", "Resa Svc")
        self.co_b = make_company("resa-svc-b", "Resa Svc B")
        self.veh = make_vehicule(self.co, "AA-1")
        self.veh2 = make_vehicule(self.co, "AA-2")

    def test_overlap_detected(self):
        make_resa(self.co, self.veh, dt(0, 8), dt(0, 12))
        conflits = reservations_en_conflit(
            self.co, self.veh, dt(0, 10), dt(0, 14))
        self.assertEqual(conflits.count(), 1)

    def test_adjacent_no_conflict(self):
        """Une réservation finit exactement où une autre commence → pas de
        conflit (bornes demi-ouvertes)."""
        make_resa(self.co, self.veh, dt(0, 8), dt(0, 12))
        conflits = reservations_en_conflit(
            self.co, self.veh, dt(0, 12), dt(0, 16))
        self.assertEqual(conflits.count(), 0)

    def test_cancelled_not_counted(self):
        make_resa(self.co, self.veh, dt(0, 8), dt(0, 12), statut="annulee")
        conflits = reservations_en_conflit(
            self.co, self.veh, dt(0, 9), dt(0, 11))
        self.assertEqual(conflits.count(), 0)

    def test_other_vehicule_no_conflict(self):
        make_resa(self.co, self.veh, dt(0, 8), dt(0, 12))
        conflits = reservations_en_conflit(
            self.co, self.veh2, dt(0, 9), dt(0, 11))
        self.assertEqual(conflits.count(), 0)

    def test_tenant_isolation(self):
        make_resa(self.co, self.veh, dt(0, 8), dt(0, 12))
        conflits = reservations_en_conflit(
            self.co_b, self.veh, dt(0, 9), dt(0, 11))
        self.assertEqual(conflits.count(), 0)

    def test_exclude_pk(self):
        resa = make_resa(self.co, self.veh, dt(0, 8), dt(0, 12))
        conflits = reservations_en_conflit(
            self.co, self.veh, dt(0, 9), dt(0, 11), exclude_pk=resa.pk)
        self.assertEqual(conflits.count(), 0)


# ── Selector ──────────────────────────────────────────────────────────────────

class ReservationSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company("resa-sel-a", "Resa Sel A")
        self.co_b = make_company("resa-sel-b", "Resa Sel B")
        self.veh_a = make_vehicule(self.co_a, "BB-1")
        self.veh_b = make_vehicule(self.co_b, "BB-2")

    def test_scope_par_societe(self):
        make_resa(self.co_a, self.veh_a, dt(0), dt(1))
        make_resa(self.co_b, self.veh_b, dt(0), dt(1))
        self.assertEqual(reservations_de_la_societe(self.co_a).count(), 1)

    def test_actives_only(self):
        make_resa(self.co_a, self.veh_a, dt(0), dt(1), statut="confirmee")
        make_resa(self.co_a, self.veh_a, dt(2), dt(3), statut="annulee")
        qs = reservations_de_la_societe(self.co_a, actives_only=True)
        self.assertEqual(qs.count(), 1)


# ── API ───────────────────────────────────────────────────────────────────────

class ReservationApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("resa-api-a", "Resa API A")
        self.co_b = make_company("resa-api-b", "Resa API B")
        self.admin_a = make_user(self.co_a, "resa-admin-a", "admin")
        self.user_a = make_user(self.co_a, "resa-user-a", "normal")
        self.veh_a = make_vehicule(self.co_a, "CC-1")
        self.veh_b = make_vehicule(self.co_b, "CC-2")
        self.cond_b = Conducteur.objects.create(
            company=self.co_b, nom="Cond B")

    def test_create_forces_company_server_side(self):
        api = auth(self.admin_a)
        resp = api.post(URL, {
            "vehicule": self.veh_a.id,
            "debut": dt(0, 8).isoformat(),
            "fin": dt(0, 12).isoformat(),
            "company": self.co_b.id,  # injection — ignorée
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        resa = ReservationVehicule.objects.get(id=resp.data["id"])
        self.assertEqual(resa.company_id, self.co_a.id)

    def test_create_returns_labels(self):
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh_a.id,
            "debut": dt(0, 8).isoformat(),
            "fin": dt(0, 12).isoformat(),
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn("CC-1", resp.data["vehicule_label"])

    def test_fin_before_debut_rejected(self):
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh_a.id,
            "debut": dt(0, 12).isoformat(),
            "fin": dt(0, 8).isoformat(),
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("fin", resp.data)

    def test_conflict_rejected(self):
        api = auth(self.admin_a)
        api.post(URL, {
            "vehicule": self.veh_a.id,
            "debut": dt(0, 8).isoformat(),
            "fin": dt(0, 12).isoformat(),
        }, format="json")
        resp = api.post(URL, {
            "vehicule": self.veh_a.id,
            "debut": dt(0, 10).isoformat(),
            "fin": dt(0, 14).isoformat(),
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_adjacent_ok(self):
        api = auth(self.admin_a)
        api.post(URL, {
            "vehicule": self.veh_a.id,
            "debut": dt(0, 8).isoformat(),
            "fin": dt(0, 12).isoformat(),
        }, format="json")
        resp = api.post(URL, {
            "vehicule": self.veh_a.id,
            "debut": dt(0, 12).isoformat(),
            "fin": dt(0, 16).isoformat(),
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_cancelled_does_not_block(self):
        api = auth(self.admin_a)
        api.post(URL, {
            "vehicule": self.veh_a.id,
            "debut": dt(0, 8).isoformat(),
            "fin": dt(0, 12).isoformat(),
            "statut": "annulee",
        }, format="json")
        resp = api.post(URL, {
            "vehicule": self.veh_a.id,
            "debut": dt(0, 9).isoformat(),
            "fin": dt(0, 11).isoformat(),
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_vehicule_other_company_rejected(self):
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh_b.id,
            "debut": dt(0, 8).isoformat(),
            "fin": dt(0, 12).isoformat(),
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_conducteur_other_company_rejected(self):
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh_a.id,
            "conducteur": self.cond_b.id,
            "debut": dt(0, 8).isoformat(),
            "fin": dt(0, 12).isoformat(),
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_tenant_isolation_list(self):
        make_resa(self.co_a, self.veh_a, dt(0), dt(1))
        resa_b = make_resa(self.co_b, self.veh_b, dt(0), dt(1))
        resp = auth(self.admin_a).get(URL)
        ids = {r["id"] for r in rows(resp)}
        self.assertNotIn(resa_b.id, ids)

    def test_cannot_retrieve_other_company(self):
        resa_b = make_resa(self.co_b, self.veh_b, dt(0), dt(1))
        resp = auth(self.admin_a).get(f"{URL}{resa_b.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_filter_by_vehicule(self):
        veh2 = make_vehicule(self.co_a, "CC-3")
        r1 = make_resa(self.co_a, self.veh_a, dt(0), dt(1))
        make_resa(self.co_a, veh2, dt(0), dt(1))
        resp = auth(self.admin_a).get(f"{URL}?vehicule={self.veh_a.id}")
        ids = [r["id"] for r in rows(resp)]
        self.assertEqual(ids, [r1.id])

    def test_filter_actives(self):
        r1 = make_resa(self.co_a, self.veh_a, dt(0), dt(1), statut="confirmee")
        r2 = make_resa(self.co_a, self.veh_a, dt(2), dt(3), statut="annulee")
        resp = auth(self.admin_a).get(f"{URL}?actives=true")
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(r1.id, ids)
        self.assertNotIn(r2.id, ids)

    def test_read_allowed_for_any_role(self):
        self.assertEqual(auth(self.user_a).get(URL).status_code, 200)

    def test_write_requires_responsable_or_admin(self):
        resp = auth(self.user_a).post(URL, {
            "vehicule": self.veh_a.id,
            "debut": dt(0, 8).isoformat(),
            "fin": dt(0, 12).isoformat(),
        }, format="json")
        self.assertEqual(resp.status_code, 403)
