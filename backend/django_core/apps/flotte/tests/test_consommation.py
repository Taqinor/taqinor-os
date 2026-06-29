"""Tests FLOTTE13 — Calcul de consommation (L/100 km et kWh/100 km).

Couvre :
- Math L/100 km plein-à-plein (segment = quantité du plein d'arrivée / distance).
- Math kWh/100 km (véhicule électrique).
- Garde divide-by-zero : distance nulle / kilométrage en recul → aucun segment,
  pas de division par zéro.
- Unités mixtes (litre + kWh) agrégées séparément.
- Cas vide (0 plein) / 1 seul plein (aucun segment).
- Isolation multi-tenant du selector.
- Endpoint API ``/pleins/consommation/`` (param obligatoire, scope société,
  404 cross-société, permissions de lecture).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import PleinCarburant, Vehicule
from apps.flotte.selectors import consommation_vehicule

User = get_user_model()

URL = "/api/django/flotte/pleins/consommation/"


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


def make_vehicule(company, immat="1234-A-00", energie="diesel"):
    return Vehicule.objects.create(
        company=company, immatriculation=immat, energie=energie)


def make_plein(company, vehicule, km, quantite, unite="litre", days_ago=0):
    return PleinCarburant.objects.create(
        company=company, vehicule=vehicule,
        date_plein=datetime.date.today() - datetime.timedelta(days=days_ago),
        kilometrage=km, quantite=quantite, prix_total=0, unite=unite)


# ── Selector — math L/100 km ──────────────────────────────────────────────────

class ConsommationLitreTests(TestCase):
    def setUp(self):
        self.co = make_company("conso-l", "Conso L")
        self.veh = make_vehicule(self.co, "CL-1")

    def test_single_segment_l_100km(self):
        # 10000 → 10500 = 500 km, 50 L sur le 2e plein → 10 L/100 km.
        make_plein(self.co, self.veh, 10000, 60, days_ago=10)
        make_plein(self.co, self.veh, 10500, 50, days_ago=0)
        res = consommation_vehicule(self.co, self.veh.id)
        self.assertEqual(res["nb_pleins"], 2)
        self.assertEqual(res["nb_segments"], 1)
        self.assertEqual(res["distance_totale_km"], 500)
        self.assertEqual(res["litres"]["conso_l_100km"], 10.0)
        self.assertIsNone(res["kwh"])
        seg = res["segments"][0]
        self.assertEqual(seg["distance_km"], 500)
        self.assertEqual(seg["conso_100km"], 10.0)

    def test_multi_segment_aggregate(self):
        # Seg1: +500 km / 50 L ; Seg2: +500 km / 30 L.
        # Agrégat : 80 L / 1000 km → 8 L/100 km.
        make_plein(self.co, self.veh, 10000, 40, days_ago=20)
        make_plein(self.co, self.veh, 10500, 50, days_ago=10)
        make_plein(self.co, self.veh, 11000, 30, days_ago=0)
        res = consommation_vehicule(self.co, self.veh.id)
        self.assertEqual(res["nb_segments"], 2)
        self.assertEqual(res["distance_totale_km"], 1000)
        self.assertEqual(res["litres"]["distance_km"], 1000)
        self.assertEqual(res["litres"]["quantite"], 80.0)
        self.assertEqual(res["litres"]["conso_l_100km"], 8.0)


# ── Selector — math kWh/100 km ────────────────────────────────────────────────

class ConsommationKwhTests(TestCase):
    def setUp(self):
        self.co = make_company("conso-k", "Conso K")
        self.veh = make_vehicule(self.co, "CK-1", energie="electrique")

    def test_single_segment_kwh_100km(self):
        # 5000 → 5200 = 200 km, 30 kWh → 15 kWh/100 km.
        make_plein(self.co, self.veh, 5000, 28, unite="kwh", days_ago=5)
        make_plein(self.co, self.veh, 5200, 30, unite="kwh", days_ago=0)
        res = consommation_vehicule(self.co, self.veh.id)
        self.assertIsNone(res["litres"])
        self.assertEqual(res["kwh"]["conso_kwh_100km"], 15.0)
        self.assertEqual(res["kwh"]["distance_km"], 200)


# ── Garde divide-by-zero + cas limites ────────────────────────────────────────

class ConsommationEdgeTests(TestCase):
    def setUp(self):
        self.co = make_company("conso-edge", "Conso Edge")
        self.veh = make_vehicule(self.co, "CE-1")

    def test_no_pleins(self):
        res = consommation_vehicule(self.co, self.veh.id)
        self.assertEqual(res["nb_pleins"], 0)
        self.assertEqual(res["nb_segments"], 0)
        self.assertEqual(res["distance_totale_km"], 0)
        self.assertIsNone(res["litres"])
        self.assertIsNone(res["kwh"])

    def test_single_plein_no_segment(self):
        make_plein(self.co, self.veh, 10000, 50)
        res = consommation_vehicule(self.co, self.veh.id)
        self.assertEqual(res["nb_pleins"], 1)
        self.assertEqual(res["nb_segments"], 0)
        self.assertIsNone(res["litres"])

    def test_zero_distance_guarded(self):
        # Deux pleins au MÊME kilométrage → distance 0 → aucun segment,
        # aucune division par zéro.
        make_plein(self.co, self.veh, 10000, 50, days_ago=2)
        make_plein(self.co, self.veh, 10000, 40, days_ago=0)
        res = consommation_vehicule(self.co, self.veh.id)
        self.assertEqual(res["nb_segments"], 0)
        self.assertIsNone(res["litres"])
        self.assertEqual(res["distance_totale_km"], 0)

    def test_mixed_units_aggregated_separately(self):
        # Un véhicule avec des pleins L puis des relevés kWh : agrégats séparés,
        # jamais additionnés. Tri par kilométrage croissant.
        make_plein(self.co, self.veh, 10000, 40, unite="litre", days_ago=30)
        make_plein(self.co, self.veh, 10500, 50, unite="litre", days_ago=20)
        make_plein(self.co, self.veh, 11000, 30, unite="kwh", days_ago=10)
        res = consommation_vehicule(self.co, self.veh.id)
        # Seg1 (L) : 500 km / 50 L → 10 L/100 km.
        # Seg2 (kWh): 500 km / 30 kWh → 6 kWh/100 km.
        self.assertEqual(res["litres"]["distance_km"], 500)
        self.assertEqual(res["litres"]["conso_l_100km"], 10.0)
        self.assertEqual(res["kwh"]["distance_km"], 500)
        self.assertEqual(res["kwh"]["conso_kwh_100km"], 6.0)

    def test_tenant_isolation(self):
        co_b = make_company("conso-edge-b", "Conso Edge B")
        make_plein(self.co, self.veh, 10000, 50, days_ago=10)
        make_plein(self.co, self.veh, 10500, 50, days_ago=0)
        # Autre société : aucun plein de ce véhicule → vide.
        res = consommation_vehicule(co_b, self.veh.id)
        self.assertEqual(res["nb_pleins"], 0)
        self.assertIsNone(res["litres"])


# ── API ───────────────────────────────────────────────────────────────────────

class ConsommationApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("conso-api-a", "Conso API A")
        self.co_b = make_company("conso-api-b", "Conso API B")
        self.admin_a = make_user(self.co_a, "conso-admin-a", "admin")
        self.user_a = make_user(self.co_a, "conso-user-a", "normal")
        self.veh_a = make_vehicule(self.co_a, "CA-1")
        self.veh_b = make_vehicule(self.co_b, "CA-2")

    def test_consommation_endpoint(self):
        make_plein(self.co_a, self.veh_a, 10000, 50, days_ago=10)
        make_plein(self.co_a, self.veh_a, 10500, 50, days_ago=0)
        resp = auth(self.admin_a).get(f"{URL}?vehicule={self.veh_a.id}")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["litres"]["conso_l_100km"], 10.0)
        self.assertEqual(resp.data["nb_segments"], 1)

    def test_missing_vehicule_param(self):
        resp = auth(self.admin_a).get(URL)
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_non_integer_vehicule_param(self):
        resp = auth(self.admin_a).get(f"{URL}?vehicule=abc")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_other_company_vehicule_404(self):
        resp = auth(self.admin_a).get(f"{URL}?vehicule={self.veh_b.id}")
        self.assertEqual(resp.status_code, 404, resp.data)

    def test_read_allowed_for_any_role(self):
        resp = auth(self.user_a).get(f"{URL}?vehicule={self.veh_a.id}")
        self.assertEqual(resp.status_code, 200, resp.data)
