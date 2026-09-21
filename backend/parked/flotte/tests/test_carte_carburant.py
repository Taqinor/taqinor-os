"""Tests FLOTTE14 — CarteCarburant + alertes anomalie (km incohérent / fraude).

Couvre :
- CRUD carte (company forcée côté serveur), isolation multi-tenant (liste).
- Validation cross-société (vehicule/conducteur d'une autre société → 400).
- Plafond négatif → 400.
- Selector ``anomalies_pleins`` :
  - kilométrage en recul → ``km_recul``.
  - saut de kilométrage invraisemblable → ``km_saut``.
  - consommation aberrante vs ligne de base → ``conso_aberrante``.
  - dépassement du plafond carte → ``plafond_depasse``.
  - garde divide-by-zero (distance nulle → pas de conso calculée).
  - isolation multi-tenant.
- Endpoint API ``/cartes/anomalies/`` (scope société, 404 cross-société,
  param non entier → 400, permissions de lecture pour tout rôle).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import CarteCarburant, PleinCarburant, Vehicule
from apps.flotte.selectors import anomalies_pleins, cartes_de_la_societe

User = get_user_model()

URL = "/api/django/flotte/cartes/"
URL_ANOMALIES = "/api/django/flotte/cartes/anomalies/"


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
        company=company, immatriculation=immat, energie="diesel")


def make_plein(company, vehicule, km, quantite=50, prix=600, days_ago=0,
               unite="litre"):
    return PleinCarburant.objects.create(
        company=company, vehicule=vehicule,
        date_plein=datetime.date.today() - datetime.timedelta(days=days_ago),
        kilometrage=km, quantite=quantite, prix_total=prix, unite=unite)


# ── CRUD carte + scope société ────────────────────────────────────────────────

class CarteCrudTests(TestCase):
    def setUp(self):
        self.co_a = make_company("carte-a", "Carte A")
        self.co_b = make_company("carte-b", "Carte B")
        self.admin_a = make_user(self.co_a, "carte-admin-a", "admin")
        self.user_a = make_user(self.co_a, "carte-user-a", "normal")
        self.veh_a = make_vehicule(self.co_a, "KA-1")
        self.veh_b = make_vehicule(self.co_b, "KB-1")

    def test_create_forces_company_server_side(self):
        # Même si on tente de passer une société, elle est ignorée (posée
        # côté serveur depuis le token).
        resp = auth(self.admin_a).post(URL, {
            "numero": "CARD-001", "plafond": "800.00", "actif": True,
            "company": self.co_b.id,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        carte = CarteCarburant.objects.get(id=resp.data["id"])
        self.assertEqual(carte.company_id, self.co_a.id)

    def test_list_scoped_to_company(self):
        CarteCarburant.objects.create(company=self.co_a, numero="A-1")
        CarteCarburant.objects.create(company=self.co_b, numero="B-1")
        resp = auth(self.admin_a).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        numeros = {r["numero"] for r in rows(resp)}
        self.assertIn("A-1", numeros)
        self.assertNotIn("B-1", numeros)

    def test_other_company_vehicule_rejected(self):
        resp = auth(self.admin_a).post(URL, {
            "numero": "CARD-X", "vehicule": self.veh_b.id,
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("vehicule", resp.data)

    def test_negative_plafond_rejected(self):
        resp = auth(self.admin_a).post(URL, {
            "numero": "CARD-NEG", "plafond": "-1.00",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("plafond", resp.data)

    def test_write_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL, {"numero": "NOPE"}, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_filter_actif(self):
        CarteCarburant.objects.create(
            company=self.co_a, numero="ON", actif=True)
        CarteCarburant.objects.create(
            company=self.co_a, numero="OFF", actif=False)
        resp = auth(self.admin_a).get(f"{URL}?actif=false")
        numeros = {r["numero"] for r in rows(resp)}
        self.assertEqual(numeros, {"OFF"})

    def test_selector_cartes_de_la_societe(self):
        CarteCarburant.objects.create(
            company=self.co_a, numero="S-ON", actif=True)
        CarteCarburant.objects.create(
            company=self.co_a, numero="S-OFF", actif=False)
        CarteCarburant.objects.create(company=self.co_b, numero="S-B")
        actives = cartes_de_la_societe(self.co_a, actif_only=True)
        self.assertEqual({c.numero for c in actives}, {"S-ON"})


# ── Selector anomalies_pleins ─────────────────────────────────────────────────

class AnomaliesSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("anom", "Anom")
        self.veh = make_vehicule(self.co, "AN-1")

    def _types(self, vehicule_id=None):
        res = anomalies_pleins(self.co, vehicule_id)
        return [a["type"] for a in res["anomalies"]]

    def test_km_recul_flagged(self):
        # Plein plus récent à un km INFÉRIEUR au précédent → recul.
        make_plein(self.co, self.veh, 10000, days_ago=10)
        make_plein(self.co, self.veh, 9000, days_ago=0)
        types = self._types()
        self.assertIn("km_recul", types)

    def test_km_saut_flagged(self):
        # Distance > seuil (5000) entre deux pleins → saut invraisemblable.
        make_plein(self.co, self.veh, 10000, days_ago=10)
        make_plein(self.co, self.veh, 20000, days_ago=0)
        types = self._types()
        self.assertIn("km_saut", types)

    def test_plafond_depasse_flagged(self):
        CarteCarburant.objects.create(
            company=self.co, numero="P-1", plafond="500.00", actif=True)
        # Plein à 900 MAD > plafond 500.
        make_plein(self.co, self.veh, 10000, prix=900, days_ago=0)
        res = anomalies_pleins(self.co, self.veh.id)
        types = [a["type"] for a in res["anomalies"]]
        self.assertIn("plafond_depasse", types)

    def test_plafond_inactive_card_ignored(self):
        CarteCarburant.objects.create(
            company=self.co, numero="P-OFF", plafond="100.00", actif=False)
        make_plein(self.co, self.veh, 10000, prix=900, days_ago=0)
        res = anomalies_pleins(self.co, self.veh.id)
        types = [a["type"] for a in res["anomalies"]]
        self.assertNotIn("plafond_depasse", types)

    def test_conso_aberrante_flagged(self):
        # Trois segments normaux (~10 L/100) puis un segment à conso x3.
        make_plein(self.co, self.veh, 10000, quantite=50, days_ago=40)
        make_plein(self.co, self.veh, 10500, quantite=50, days_ago=30)  # 10/100
        make_plein(self.co, self.veh, 11000, quantite=50, days_ago=20)  # 10/100
        make_plein(self.co, self.veh, 11500, quantite=50, days_ago=10)  # 10/100
        # +100 km mais 50 L → 50 L/100 km : très au-dessus de la médiane (10).
        make_plein(self.co, self.veh, 11600, quantite=50, days_ago=0)
        res = anomalies_pleins(self.co, self.veh.id)
        types = [a["type"] for a in res["anomalies"]]
        self.assertIn("conso_aberrante", types)

    def test_zero_distance_guarded_no_div_by_zero(self):
        # Deux pleins au MÊME km → distance 0 : pas de division par zéro, et
        # l'anomalie remontée est le recul/stagnation, pas une conso.
        make_plein(self.co, self.veh, 10000, quantite=40, days_ago=2)
        make_plein(self.co, self.veh, 10000, quantite=50, days_ago=0)
        res = anomalies_pleins(self.co, self.veh.id)
        types = [a["type"] for a in res["anomalies"]]
        self.assertIn("km_recul", types)
        self.assertNotIn("conso_aberrante", types)

    def test_clean_book_no_anomalies(self):
        make_plein(self.co, self.veh, 10000, quantite=50, days_ago=20)
        make_plein(self.co, self.veh, 10500, quantite=50, days_ago=10)
        make_plein(self.co, self.veh, 11000, quantite=50, days_ago=0)
        res = anomalies_pleins(self.co, self.veh.id)
        self.assertEqual(res["nb_anomalies"], 0)
        self.assertEqual(res["anomalies"], [])

    def test_tenant_isolation(self):
        co_b = make_company("anom-b", "Anom B")
        make_plein(self.co, self.veh, 10000, days_ago=10)
        make_plein(self.co, self.veh, 9000, days_ago=0)  # recul côté co
        res_b = anomalies_pleins(co_b, self.veh.id)
        self.assertEqual(res_b["nb_pleins"], 0)
        self.assertEqual(res_b["nb_anomalies"], 0)


# ── API endpoint /cartes/anomalies/ ───────────────────────────────────────────

class AnomaliesApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("anom-api-a", "Anom API A")
        self.co_b = make_company("anom-api-b", "Anom API B")
        self.admin_a = make_user(self.co_a, "anom-admin-a", "admin")
        self.user_a = make_user(self.co_a, "anom-user-a", "normal")
        self.veh_a = make_vehicule(self.co_a, "AA-1")
        self.veh_b = make_vehicule(self.co_b, "AB-1")

    def test_anomalies_endpoint(self):
        make_plein(self.co_a, self.veh_a, 10000, days_ago=10)
        make_plein(self.co_a, self.veh_a, 9000, days_ago=0)  # recul
        resp = auth(self.admin_a).get(
            f"{URL_ANOMALIES}?vehicule={self.veh_a.id}")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertGreaterEqual(resp.data["nb_anomalies"], 1)
        types = {a["type"] for a in resp.data["anomalies"]}
        self.assertIn("km_recul", types)

    def test_anomalies_no_vehicule_param_all_company(self):
        make_plein(self.co_a, self.veh_a, 10000, days_ago=10)
        make_plein(self.co_a, self.veh_a, 9000, days_ago=0)
        resp = auth(self.admin_a).get(URL_ANOMALIES)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertGreaterEqual(resp.data["nb_anomalies"], 1)

    def test_non_integer_vehicule_param(self):
        resp = auth(self.admin_a).get(f"{URL_ANOMALIES}?vehicule=abc")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_other_company_vehicule_404(self):
        resp = auth(self.admin_a).get(
            f"{URL_ANOMALIES}?vehicule={self.veh_b.id}")
        self.assertEqual(resp.status_code, 404, resp.data)

    def test_read_allowed_for_any_role(self):
        make_plein(self.co_a, self.veh_a, 10000, days_ago=10)
        resp = auth(self.user_a).get(
            f"{URL_ANOMALIES}?vehicule={self.veh_a.id}")
        self.assertEqual(resp.status_code, 200, resp.data)
