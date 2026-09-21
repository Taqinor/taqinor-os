"""Tests FLOTTE15 — PlanEntretien (plans d'entretien préventif km/date/heures).

Couvre :
- CRUD plan (company forcée côté serveur), isolation multi-tenant (liste).
- Validation : actif d'une autre société → 400 ; aucun intervalle → 400.
- Selector ``plans_entretien_status`` :
  - échéance kilométrique (due / upcoming / ok) vs le km courant du véhicule.
  - échéance horaire (due) vs le compteur d'heures courant de l'engin.
  - échéance calendaire (due) vs la date du jour.
  - garde divide-by-zero (calcul additif : aucune division ⇒ aucun crash).
  - isolation multi-tenant.
- Endpoint API ``/plans-entretien/echeances/`` (scope société, filtre statut,
  lecture pour tout rôle, écriture interdite au rôle normal).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    EnginRoulant,
    PlanEntretien,
    Vehicule,
)
from apps.flotte.selectors import (
    plans_de_la_societe,
    plans_entretien_status,
)

User = get_user_model()

URL = "/api/django/flotte/plans-entretien/"
URL_ECHEANCES = "/api/django/flotte/plans-entretien/echeances/"


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def make_vehicule(company, immat="PE-1", km=0):
    return Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel",
        kilometrage=km)


def make_engin(company, nom="Nacelle", heures=0):
    return EnginRoulant.objects.create(
        company=company, nom=nom, type_engin="nacelle",
        compteur_heures=heures)


def actif_pour_vehicule(company, vehicule):
    return ActifFlotte.objects.create(company=company, vehicule=vehicule)


def actif_pour_engin(company, engin):
    return ActifFlotte.objects.create(company=company, engin=engin)


# ── CRUD plan + scope société ─────────────────────────────────────────────────

class PlanCrudTests(TestCase):
    def setUp(self):
        self.co_a = make_company("plan-a", "Plan A")
        self.co_b = make_company("plan-b", "Plan B")
        self.admin_a = make_user(self.co_a, "plan-admin-a", "admin")
        self.user_a = make_user(self.co_a, "plan-user-a", "normal")
        self.veh_a = make_vehicule(self.co_a, "PA-1", km=10000)
        self.veh_b = make_vehicule(self.co_b, "PB-1", km=10000)
        self.actif_a = actif_pour_vehicule(self.co_a, self.veh_a)
        self.actif_b = actif_pour_vehicule(self.co_b, self.veh_b)

    def test_create_forces_company_server_side(self):
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif_a.id,
            "type_entretien": "vidange",
            "intervalle_km": 10000,
            "company": self.co_b.id,  # ignoré, posé côté serveur
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        plan = PlanEntretien.objects.get(id=resp.data["id"])
        self.assertEqual(plan.company_id, self.co_a.id)

    def test_list_scoped_to_company(self):
        PlanEntretien.objects.create(
            company=self.co_a, actif_flotte=self.actif_a,
            type_entretien="vidange", intervalle_km=10000)
        PlanEntretien.objects.create(
            company=self.co_b, actif_flotte=self.actif_b,
            type_entretien="revision", intervalle_km=20000)
        resp = auth(self.admin_a).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        types = {r["type_entretien"] for r in rows(resp)}
        self.assertIn("vidange", types)
        self.assertNotIn("revision", types)

    def test_other_company_actif_rejected(self):
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif_b.id,
            "type_entretien": "vidange",
            "intervalle_km": 10000,
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("actif_flotte", resp.data)

    def test_no_interval_rejected(self):
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif_a.id,
            "type_entretien": "vidange",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_write_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL, {
            "actif_flotte": self.actif_a.id,
            "type_entretien": "vidange", "intervalle_km": 10000,
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_filter_actif(self):
        PlanEntretien.objects.create(
            company=self.co_a, actif_flotte=self.actif_a,
            type_entretien="on", intervalle_km=10000, actif=True)
        PlanEntretien.objects.create(
            company=self.co_a, actif_flotte=self.actif_a,
            type_entretien="off", intervalle_km=10000, actif=False)
        resp = auth(self.admin_a).get(f"{URL}?actif=false")
        types = {r["type_entretien"] for r in rows(resp)}
        self.assertEqual(types, {"off"})

    def test_selector_plans_de_la_societe(self):
        PlanEntretien.objects.create(
            company=self.co_a, actif_flotte=self.actif_a,
            type_entretien="s-on", intervalle_km=10000, actif=True)
        PlanEntretien.objects.create(
            company=self.co_a, actif_flotte=self.actif_a,
            type_entretien="s-off", intervalle_km=10000, actif=False)
        PlanEntretien.objects.create(
            company=self.co_b, actif_flotte=self.actif_b,
            type_entretien="s-b", intervalle_km=10000, actif=True)
        actifs = plans_de_la_societe(self.co_a, actif_only=True)
        self.assertEqual({p.type_entretien for p in actifs}, {"s-on"})


# ── Selector plans_entretien_status ───────────────────────────────────────────

class StatusSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("status", "Status")

    def _status_of(self, type_entretien, **plan_kwargs):
        res = plans_entretien_status(self.co)
        for p in res["plans"]:
            if p["type_entretien"] == type_entretien:
                return p["statut"]
        return None

    def test_km_due(self):
        # dernier=10000, intervalle=10000 → prochaine=20000 ; km courant 25000.
        veh = make_vehicule(self.co, "KM-DUE", km=25000)
        actif = actif_pour_vehicule(self.co, veh)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="km-due",
            intervalle_km=10000, dernier_km=10000)
        self.assertEqual(self._status_of("km-due"), "due")

    def test_km_upcoming(self):
        # prochaine=20000 ; courant 19800 → restant 200 ≤ marge 500 → upcoming.
        veh = make_vehicule(self.co, "KM-UP", km=19800)
        actif = actif_pour_vehicule(self.co, veh)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="km-up",
            intervalle_km=10000, dernier_km=10000, seuil_alerte_km=500)
        self.assertEqual(self._status_of("km-up"), "upcoming")

    def test_km_ok(self):
        # prochaine=20000 ; courant 12000 → restant 8000 > marge → ok.
        veh = make_vehicule(self.co, "KM-OK", km=12000)
        actif = actif_pour_vehicule(self.co, veh)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="km-ok",
            intervalle_km=10000, dernier_km=10000, seuil_alerte_km=500)
        self.assertEqual(self._status_of("km-ok"), "ok")

    def test_heures_due(self):
        # engin à 1200 h ; dernier=0, intervalle=500 → prochaine 500 ⇒ due.
        engin = make_engin(self.co, "GE-DUE", heures=1200)
        actif = actif_pour_engin(self.co, engin)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="h-due",
            intervalle_heures=500, dernier_heures=0)
        self.assertEqual(self._status_of("h-due"), "due")

    def test_jours_due(self):
        # derniere_date il y a 400 j, intervalle 365 → échéance passée ⇒ due.
        veh = make_vehicule(self.co, "J-DUE", km=0)
        actif = actif_pour_vehicule(self.co, veh)
        past = datetime.date.today() - datetime.timedelta(days=400)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="j-due",
            intervalle_jours=365, derniere_date=past)
        self.assertEqual(self._status_of("j-due"), "due")

    def test_jours_upcoming(self):
        # derniere_date il y a 360 j, intervalle 365 → 5 j restants ≤ marge 14.
        veh = make_vehicule(self.co, "J-UP", km=0)
        actif = actif_pour_vehicule(self.co, veh)
        past = datetime.date.today() - datetime.timedelta(days=360)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="j-up",
            intervalle_jours=365, derniere_date=past, seuil_alerte_jours=14)
        self.assertEqual(self._status_of("j-up"), "upcoming")

    def test_no_division_by_zero_additive_math(self):
        # Tous les seuils à 0 et km courant pile sur l'échéance : aucun crash,
        # restant 0 ⇒ due (le calcul est purement additif, jamais de division).
        veh = make_vehicule(self.co, "Z-1", km=20000)
        actif = actif_pour_vehicule(self.co, veh)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="zero",
            intervalle_km=10000, dernier_km=10000, seuil_alerte_km=0)
        # Ne lève pas et classe le plan.
        res = plans_entretien_status(self.co)
        statut = next(p["statut"] for p in res["plans"]
                      if p["type_entretien"] == "zero")
        self.assertEqual(statut, "due")

    def test_counts_due_and_upcoming(self):
        veh = make_vehicule(self.co, "CNT", km=25000)
        actif = actif_pour_vehicule(self.co, veh)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="d",
            intervalle_km=10000, dernier_km=10000)  # due (20000 < 25000)
        res = plans_entretien_status(self.co)
        self.assertGreaterEqual(res["nb_due"], 1)

    def test_statut_filter(self):
        veh = make_vehicule(self.co, "FLT", km=25000)
        actif = actif_pour_vehicule(self.co, veh)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="due-only",
            intervalle_km=10000, dernier_km=10000)  # due
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="ok-only",
            intervalle_km=10000, dernier_km=20000, seuil_alerte_km=10)  # ok
        res = plans_entretien_status(self.co, statut="due")
        types = {p["type_entretien"] for p in res["plans"]}
        self.assertIn("due-only", types)
        self.assertNotIn("ok-only", types)

    def test_inactive_plan_excluded(self):
        veh = make_vehicule(self.co, "INA", km=25000)
        actif = actif_pour_vehicule(self.co, veh)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="inactif",
            intervalle_km=10000, dernier_km=10000, actif=False)
        res = plans_entretien_status(self.co)  # actif_only=True
        types = {p["type_entretien"] for p in res["plans"]}
        self.assertNotIn("inactif", types)

    def test_tenant_isolation(self):
        co_b = make_company("status-b", "Status B")
        veh = make_vehicule(self.co, "ISO", km=25000)
        actif = actif_pour_vehicule(self.co, veh)
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=actif, type_entretien="iso",
            intervalle_km=10000, dernier_km=10000)
        res_b = plans_entretien_status(co_b)
        self.assertEqual(res_b["nb_plans"], 0)
        self.assertEqual(res_b["plans"], [])


# ── API endpoint /plans-entretien/echeances/ ──────────────────────────────────

class EcheancesApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("ech-a", "Ech A")
        self.co_b = make_company("ech-b", "Ech B")
        self.admin_a = make_user(self.co_a, "ech-admin-a", "admin")
        self.user_a = make_user(self.co_a, "ech-user-a", "normal")
        self.veh_a = make_vehicule(self.co_a, "EA-1", km=25000)
        self.actif_a = actif_pour_vehicule(self.co_a, self.veh_a)
        PlanEntretien.objects.create(
            company=self.co_a, actif_flotte=self.actif_a,
            type_entretien="vidange", intervalle_km=10000, dernier_km=10000)

    def test_echeances_endpoint(self):
        resp = auth(self.admin_a).get(URL_ECHEANCES)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertGreaterEqual(resp.data["nb_due"], 1)
        types = {p["type_entretien"] for p in resp.data["plans"]}
        self.assertIn("vidange", types)

    def test_echeances_statut_filter(self):
        resp = auth(self.admin_a).get(f"{URL_ECHEANCES}?statut=due")
        self.assertEqual(resp.status_code, 200, resp.data)
        for p in resp.data["plans"]:
            self.assertEqual(p["statut"], "due")

    def test_echeances_scoped_to_company(self):
        # Société B ne voit aucun plan de A.
        admin_b = make_user(self.co_b, "ech-admin-b", "admin")
        resp = auth(admin_b).get(URL_ECHEANCES)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["plans"], [])

    def test_read_allowed_for_any_role(self):
        resp = auth(self.user_a).get(URL_ECHEANCES)
        self.assertEqual(resp.status_code, 200, resp.data)
