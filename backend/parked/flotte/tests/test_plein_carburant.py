"""Tests FLOTTE12 — PleinCarburant (carnet de carburant).

Couvre :
- Création (company forcée côté serveur), prix_unitaire calculé.
- Isolation multi-tenant (liste + retrieve).
- Cohérence du kilométrage (compteur ne recule pas → 400) via le service.
- Validation cross-société + quantité/prix négatifs.
- Filtres ``?vehicule=``, ``?unite=``.
- Selector ``pleins_du_vehicule`` + service ``kilometrage_incoherent``.
- Permissions.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import Conducteur, PleinCarburant, Vehicule
from apps.flotte.selectors import pleins_du_vehicule
from apps.flotte.services import kilometrage_incoherent

User = get_user_model()

URL = "/api/django/flotte/pleins/"


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


def make_plein(company, vehicule, km, date=None, quantite=50, prix=600):
    if date is None:
        date = datetime.date.today()
    return PleinCarburant.objects.create(
        company=company, vehicule=vehicule, date_plein=date,
        kilometrage=km, quantite=quantite, prix_total=prix)


# ── Service de cohérence (unité) ──────────────────────────────────────────────

class KilometrageServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("plein-svc", "Plein Svc")
        self.co_b = make_company("plein-svc-b", "Plein Svc B")
        self.veh = make_vehicule(self.co, "FF-1")
        self.today = datetime.date.today()

    def test_increasing_ok(self):
        make_plein(self.co, self.veh, 10000,
                   date=self.today - datetime.timedelta(days=10))
        incoherent, _ = kilometrage_incoherent(
            self.co, self.veh, 11000, self.today)
        self.assertFalse(incoherent)

    def test_decreasing_flagged(self):
        make_plein(self.co, self.veh, 10000,
                   date=self.today - datetime.timedelta(days=10))
        incoherent, msg = kilometrage_incoherent(
            self.co, self.veh, 9000, self.today)
        self.assertTrue(incoherent)
        self.assertIn("inférieur", msg)

    def test_inserted_between_too_high(self):
        """Un plein intercalé dont le km dépasse un relevé postérieur → flag."""
        make_plein(self.co, self.veh, 10000,
                   date=self.today - datetime.timedelta(days=10))
        make_plein(self.co, self.veh, 12000,
                   date=self.today + datetime.timedelta(days=10))
        incoherent, msg = kilometrage_incoherent(
            self.co, self.veh, 13000, self.today)
        self.assertTrue(incoherent)
        self.assertIn("postérieur", msg)

    def test_tenant_isolation(self):
        make_plein(self.co, self.veh, 10000,
                   date=self.today - datetime.timedelta(days=10))
        # Pour une autre société, aucun historique → cohérent.
        incoherent, _ = kilometrage_incoherent(
            self.co_b, self.veh, 5000, self.today)
        self.assertFalse(incoherent)


# ── Selector + propriété ──────────────────────────────────────────────────────

class PleinSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company("plein-sel-a", "Plein Sel A")
        self.co_b = make_company("plein-sel-b", "Plein Sel B")
        self.veh_a = make_vehicule(self.co_a, "GG-1")
        self.veh_b = make_vehicule(self.co_b, "GG-2")

    def test_scope(self):
        make_plein(self.co_a, self.veh_a, 100)
        make_plein(self.co_b, self.veh_b, 100)
        self.assertEqual(
            pleins_du_vehicule(self.co_a, self.veh_a.id).count(), 1)

    def test_prix_unitaire(self):
        plein = make_plein(self.co_a, self.veh_a, 100, quantite=50, prix=600)
        self.assertEqual(plein.prix_unitaire, 12.0)

    def test_prix_unitaire_zero_quantite(self):
        plein = make_plein(self.co_a, self.veh_a, 100, quantite=0, prix=0)
        self.assertIsNone(plein.prix_unitaire)


# ── API ───────────────────────────────────────────────────────────────────────

class PleinApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("plein-api-a", "Plein API A")
        self.co_b = make_company("plein-api-b", "Plein API B")
        self.admin_a = make_user(self.co_a, "plein-admin-a", "admin")
        self.user_a = make_user(self.co_a, "plein-user-a", "normal")
        self.veh_a = make_vehicule(self.co_a, "HH-1")
        self.veh_b = make_vehicule(self.co_b, "HH-2")
        self.cond_b = Conducteur.objects.create(
            company=self.co_b, nom="Cond B")
        self.today = datetime.date.today().isoformat()

    def test_create_forces_company_and_prix_unitaire(self):
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh_a.id,
            "date_plein": self.today,
            "kilometrage": 10000,
            "quantite": "50.00",
            "prix_total": "600.00",
            "company": self.co_b.id,  # ignorée
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        plein = PleinCarburant.objects.get(id=resp.data["id"])
        self.assertEqual(plein.company_id, self.co_a.id)
        self.assertEqual(resp.data["prix_unitaire"], 12.0)

    def test_decreasing_km_rejected(self):
        api = auth(self.admin_a)
        make_plein(self.co_a, self.veh_a, 10000,
                   date=datetime.date.today() - datetime.timedelta(days=5))
        resp = api.post(URL, {
            "vehicule": self.veh_a.id,
            "date_plein": self.today,
            "kilometrage": 9000,
            "quantite": "40.00",
            "prix_total": "500.00",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("kilometrage", resp.data)

    def test_increasing_km_ok(self):
        make_plein(self.co_a, self.veh_a, 10000,
                   date=datetime.date.today() - datetime.timedelta(days=5))
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh_a.id,
            "date_plein": self.today,
            "kilometrage": 11000,
            "quantite": "40.00",
            "prix_total": "500.00",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_negative_quantite_rejected(self):
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh_a.id,
            "date_plein": self.today,
            "kilometrage": 100,
            "quantite": "-5.00",
            "prix_total": "10.00",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_vehicule_other_company_rejected(self):
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh_b.id,
            "date_plein": self.today,
            "kilometrage": 100,
            "quantite": "5.00",
            "prix_total": "60.00",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_conducteur_other_company_rejected(self):
        resp = auth(self.admin_a).post(URL, {
            "vehicule": self.veh_a.id,
            "conducteur": self.cond_b.id,
            "date_plein": self.today,
            "kilometrage": 100,
            "quantite": "5.00",
            "prix_total": "60.00",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_tenant_isolation_list(self):
        make_plein(self.co_a, self.veh_a, 100)
        plein_b = make_plein(self.co_b, self.veh_b, 100)
        resp = auth(self.admin_a).get(URL)
        ids = {r["id"] for r in rows(resp)}
        self.assertNotIn(plein_b.id, ids)

    def test_cannot_retrieve_other_company(self):
        plein_b = make_plein(self.co_b, self.veh_b, 100)
        resp = auth(self.admin_a).get(f"{URL}{plein_b.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_filter_by_unite(self):
        p1 = PleinCarburant.objects.create(
            company=self.co_a, vehicule=self.veh_a,
            date_plein=datetime.date.today(), kilometrage=100,
            quantite=50, prix_total=600, unite="litre")
        veh2 = make_vehicule(self.co_a, "HH-3")
        PleinCarburant.objects.create(
            company=self.co_a, vehicule=veh2,
            date_plein=datetime.date.today(), kilometrage=100,
            quantite=30, prix_total=400, unite="kwh")
        resp = auth(self.admin_a).get(f"{URL}?unite=litre")
        ids = [r["id"] for r in rows(resp)]
        self.assertEqual(ids, [p1.id])

    def test_read_allowed_for_any_role(self):
        self.assertEqual(auth(self.user_a).get(URL).status_code, 200)

    def test_write_requires_responsable_or_admin(self):
        resp = auth(self.user_a).post(URL, {
            "vehicule": self.veh_a.id,
            "date_plein": self.today,
            "kilometrage": 100,
            "quantite": "5.00",
            "prix_total": "60.00",
        }, format="json")
        self.assertEqual(resp.status_code, 403)
