"""Tests FLOTTE8 — AffectationConducteur (conducteur ↔ véhicule datée).

Couvre :
- Création d'une affectation (company forcée côté serveur).
- Isolation multi-tenant (société A ne voit pas les affectations de société B).
- Validation plage de dates (date_fin < date_debut → 400).
- Validation cross-société (conducteur/véhicule d'une autre société → 400).
- Filtres ``?vehicule=``, ``?conducteur=``, ``?actif=``.
- Sélecteurs ``conducteur_actuel_du_vehicule``, ``affectations_du_vehicule``,
  ``affectations_du_conducteur``.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import AffectationConducteur, Conducteur, Vehicule
from apps.flotte.selectors import (
    affectations_du_conducteur,
    affectations_du_vehicule,
    conducteur_actuel_du_vehicule,
)

User = get_user_model()

URL = "/api/django/flotte/affectations/"


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


def make_conducteur(company, nom="Conducteur Test"):
    return Conducteur.objects.create(company=company, nom=nom)


def make_affectation(company, conducteur, vehicule, date_debut=None,
                     date_fin=None, actif=True):
    if date_debut is None:
        date_debut = datetime.date.today()
    return AffectationConducteur.objects.create(
        company=company,
        conducteur=conducteur,
        vehicule=vehicule,
        date_debut=date_debut,
        date_fin=date_fin,
        actif=actif,
    )


# ── Modèle (unité) ────────────────────────────────────────────────────────────

class AffectationConducteurModelTests(TestCase):
    def setUp(self):
        self.co = make_company("aff-model", "Aff Model")
        self.conducteur = make_conducteur(self.co, "Ali Benali")
        self.vehicule = make_vehicule(self.co, "7890-B-12")

    def test_create_basic(self):
        today = datetime.date.today()
        aff = AffectationConducteur.objects.create(
            company=self.co,
            conducteur=self.conducteur,
            vehicule=self.vehicule,
            date_debut=today,
        )
        self.assertEqual(aff.company_id, self.co.id)
        self.assertEqual(aff.conducteur_id, self.conducteur.id)
        self.assertEqual(aff.vehicule_id, self.vehicule.id)
        self.assertIsNone(aff.date_fin)
        self.assertTrue(aff.actif)

    def test_str(self):
        today = datetime.date.today()
        aff = make_affectation(self.co, self.conducteur, self.vehicule,
                               date_debut=today)
        s = str(aff)
        self.assertIn("Ali Benali", s)
        self.assertIn(today.isoformat(), s)

    def test_str_with_date_fin(self):
        today = datetime.date.today()
        fin = today + datetime.timedelta(days=30)
        aff = make_affectation(self.co, self.conducteur, self.vehicule,
                               date_debut=today, date_fin=fin)
        self.assertIn(fin.isoformat(), str(aff))


# ── Sélecteurs ────────────────────────────────────────────────────────────────

class AffectationSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company("aff-sel-a", "Aff Sel A")
        self.co_b = make_company("aff-sel-b", "Aff Sel B")
        self.cond_a = make_conducteur(self.co_a, "Conducteur A")
        self.cond_a2 = make_conducteur(self.co_a, "Conducteur A2")
        self.veh_a = make_vehicule(self.co_a, "1111-A-11")
        self.veh_b = make_vehicule(self.co_b, "2222-B-22")
        self.today = datetime.date.today()

    def test_conducteur_actuel_actif(self):
        make_affectation(
            self.co_a, self.cond_a, self.veh_a,
            date_debut=self.today - datetime.timedelta(days=5),
            actif=True,
        )
        result = conducteur_actuel_du_vehicule(self.co_a, self.veh_a.id)
        self.assertEqual(result.id, self.cond_a.id)

    def test_conducteur_actuel_avec_date_fin_future(self):
        make_affectation(
            self.co_a, self.cond_a, self.veh_a,
            date_debut=self.today - datetime.timedelta(days=3),
            date_fin=self.today + datetime.timedelta(days=10),
            actif=True,
        )
        result = conducteur_actuel_du_vehicule(self.co_a, self.veh_a.id)
        self.assertEqual(result.id, self.cond_a.id)

    def test_conducteur_actuel_expire(self):
        """Affectation terminée (date_fin dans le passé) → None."""
        make_affectation(
            self.co_a, self.cond_a, self.veh_a,
            date_debut=self.today - datetime.timedelta(days=10),
            date_fin=self.today - datetime.timedelta(days=1),
            actif=True,
        )
        result = conducteur_actuel_du_vehicule(self.co_a, self.veh_a.id)
        self.assertIsNone(result)

    def test_conducteur_actuel_inactif(self):
        """Affectation avec actif=False → None."""
        make_affectation(
            self.co_a, self.cond_a, self.veh_a,
            date_debut=self.today,
            actif=False,
        )
        result = conducteur_actuel_du_vehicule(self.co_a, self.veh_a.id)
        self.assertIsNone(result)

    def test_conducteur_actuel_tenant_isolation(self):
        """Le sélecteur ne remonte que les données de la société demandée."""
        make_affectation(
            self.co_a, self.cond_a, self.veh_a,
            date_debut=self.today,
            actif=True,
        )
        # La société B n'a aucune affectation pour ce véhicule.
        result = conducteur_actuel_du_vehicule(self.co_b, self.veh_a.id)
        self.assertIsNone(result)

    def test_conducteur_actuel_picks_most_recent(self):
        """Deux affectations actives → la plus récente l'emporte."""
        make_affectation(
            self.co_a, self.cond_a, self.veh_a,
            date_debut=self.today - datetime.timedelta(days=10),
            actif=True,
        )
        make_affectation(
            self.co_a, self.cond_a2, self.veh_a,
            date_debut=self.today - datetime.timedelta(days=2),
            actif=True,
        )
        result = conducteur_actuel_du_vehicule(self.co_a, self.veh_a.id)
        self.assertEqual(result.id, self.cond_a2.id)

    def test_affectations_du_vehicule(self):
        make_affectation(self.co_a, self.cond_a, self.veh_a,
                         date_debut=self.today)
        make_affectation(self.co_a, self.cond_a2, self.veh_a,
                         date_debut=self.today - datetime.timedelta(days=5))
        qs = affectations_du_vehicule(self.co_a, self.veh_a.id)
        self.assertEqual(qs.count(), 2)

    def test_affectations_du_vehicule_scope(self):
        make_affectation(self.co_a, self.cond_a, self.veh_a,
                         date_debut=self.today)
        # La société B ne doit pas voir les affectations de A.
        qs = affectations_du_vehicule(self.co_b, self.veh_a.id)
        self.assertEqual(qs.count(), 0)

    def test_affectations_du_conducteur(self):
        make_affectation(self.co_a, self.cond_a, self.veh_a,
                         date_debut=self.today)
        qs = affectations_du_conducteur(self.co_a, self.cond_a.id)
        self.assertEqual(qs.count(), 1)


# ── API ───────────────────────────────────────────────────────────────────────

class AffectationConducteurApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("aff-api-a", "Aff API A")
        self.co_b = make_company("aff-api-b", "Aff API B")
        self.admin_a = make_user(self.co_a, "aff-admin-a", "admin")
        self.admin_b = make_user(self.co_b, "aff-admin-b", "admin")
        self.user_a = make_user(self.co_a, "aff-user-a", "normal")
        self.cond_a = make_conducteur(self.co_a, "Cond A")
        self.cond_b = make_conducteur(self.co_b, "Cond B")
        self.veh_a = make_vehicule(self.co_a, "3333-A-33")
        self.veh_b = make_vehicule(self.co_b, "4444-B-44")
        self.today = datetime.date.today().isoformat()

    # ── Création ─────────────────────────────────────────────────────────────

    def test_create_forces_company_server_side(self):
        """La société est posée côté serveur ; l'injection dans le corps est
        ignorée."""
        api = auth(self.admin_a)
        resp = api.post(URL, {
            "conducteur": self.cond_a.id,
            "vehicule": self.veh_a.id,
            "date_debut": self.today,
            "company": self.co_b.id,  # injection — doit être ignorée
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        aff = AffectationConducteur.objects.get(id=resp.data["id"])
        self.assertEqual(aff.company_id, self.co_a.id)

    def test_create_returns_labels(self):
        api = auth(self.admin_a)
        resp = api.post(URL, {
            "conducteur": self.cond_a.id,
            "vehicule": self.veh_a.id,
            "date_debut": self.today,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["conducteur_nom"], "Cond A")
        self.assertIn("3333-A-33", resp.data["vehicule_label"])

    def test_create_with_notes(self):
        api = auth(self.admin_a)
        resp = api.post(URL, {
            "conducteur": self.cond_a.id,
            "vehicule": self.veh_a.id,
            "date_debut": self.today,
            "notes": "Affectation temporaire.",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["notes"], "Affectation temporaire.")

    # ── Validation plage de dates ─────────────────────────────────────────────

    def test_date_fin_before_date_debut_rejected(self):
        """date_fin < date_debut → 400."""
        api = auth(self.admin_a)
        today = datetime.date.today()
        resp = api.post(URL, {
            "conducteur": self.cond_a.id,
            "vehicule": self.veh_a.id,
            "date_debut": today.isoformat(),
            "date_fin": (today - datetime.timedelta(days=1)).isoformat(),
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("date_fin", resp.data)

    def test_date_fin_equal_date_debut_ok(self):
        """date_fin == date_debut → affectation d'un seul jour acceptée."""
        api = auth(self.admin_a)
        resp = api.post(URL, {
            "conducteur": self.cond_a.id,
            "vehicule": self.veh_a.id,
            "date_debut": self.today,
            "date_fin": self.today,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_date_fin_null_ok(self):
        """date_fin nullable → affectation ouverte acceptée."""
        api = auth(self.admin_a)
        resp = api.post(URL, {
            "conducteur": self.cond_a.id,
            "vehicule": self.veh_a.id,
            "date_debut": self.today,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data["date_fin"])

    # ── Validation cross-société ──────────────────────────────────────────────

    def test_conducteur_other_company_rejected(self):
        """Un conducteur d'une autre société → 400."""
        api = auth(self.admin_a)
        resp = api.post(URL, {
            "conducteur": self.cond_b.id,
            "vehicule": self.veh_a.id,
            "date_debut": self.today,
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_vehicule_other_company_rejected(self):
        """Un véhicule d'une autre société → 400."""
        api = auth(self.admin_a)
        resp = api.post(URL, {
            "conducteur": self.cond_a.id,
            "vehicule": self.veh_b.id,
            "date_debut": self.today,
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    # ── Isolation multi-tenant ────────────────────────────────────────────────

    def test_tenant_isolation_list(self):
        today = datetime.date.today()
        AffectationConducteur.objects.create(
            company=self.co_a, conducteur=self.cond_a, vehicule=self.veh_a,
            date_debut=today)
        AffectationConducteur.objects.create(
            company=self.co_b, conducteur=self.cond_b, vehicule=self.veh_b,
            date_debut=today)
        resp = auth(self.admin_a).get(URL)
        ids_in_resp = {r["id"] for r in rows(resp)}
        aff_b = AffectationConducteur.objects.filter(company=self.co_b).first()
        self.assertNotIn(aff_b.id, ids_in_resp)

    def test_cannot_retrieve_other_company_affectation(self):
        today = datetime.date.today()
        aff_b = AffectationConducteur.objects.create(
            company=self.co_b, conducteur=self.cond_b, vehicule=self.veh_b,
            date_debut=today)
        resp = auth(self.admin_a).get(f"{URL}{aff_b.id}/")
        self.assertEqual(resp.status_code, 404)

    # ── Filtres ───────────────────────────────────────────────────────────────

    def test_filter_by_vehicule(self):
        today = datetime.date.today()
        veh2 = make_vehicule(self.co_a, "5555-A-55")
        aff1 = AffectationConducteur.objects.create(
            company=self.co_a, conducteur=self.cond_a, vehicule=self.veh_a,
            date_debut=today)
        AffectationConducteur.objects.create(
            company=self.co_a, conducteur=self.cond_a, vehicule=veh2,
            date_debut=today)
        resp = auth(self.admin_a).get(f"{URL}?vehicule={self.veh_a.id}")
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(aff1.id, ids)
        self.assertEqual(len(ids), 1)

    def test_filter_by_conducteur(self):
        today = datetime.date.today()
        cond2 = make_conducteur(self.co_a, "Cond A2")
        veh2 = make_vehicule(self.co_a, "6666-A-66")
        aff1 = AffectationConducteur.objects.create(
            company=self.co_a, conducteur=self.cond_a, vehicule=self.veh_a,
            date_debut=today)
        AffectationConducteur.objects.create(
            company=self.co_a, conducteur=cond2, vehicule=veh2,
            date_debut=today)
        resp = auth(self.admin_a).get(f"{URL}?conducteur={self.cond_a.id}")
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(aff1.id, ids)
        self.assertEqual(len(ids), 1)

    def test_filter_actif(self):
        today = datetime.date.today()
        veh2 = make_vehicule(self.co_a, "7777-A-77")
        aff_actif = AffectationConducteur.objects.create(
            company=self.co_a, conducteur=self.cond_a, vehicule=self.veh_a,
            date_debut=today, actif=True)
        aff_inactif = AffectationConducteur.objects.create(
            company=self.co_a, conducteur=self.cond_a, vehicule=veh2,
            date_debut=today, actif=False)
        resp = auth(self.admin_a).get(f"{URL}?actif=true")
        ids = [r["id"] for r in rows(resp)]
        self.assertIn(aff_actif.id, ids)
        self.assertNotIn(aff_inactif.id, ids)

    # ── Permissions ───────────────────────────────────────────────────────────

    def test_read_allowed_for_any_role(self):
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200)

    def test_write_requires_responsable_or_admin(self):
        resp = auth(self.user_a).post(URL, {
            "conducteur": self.cond_a.id,
            "vehicule": self.veh_a.id,
            "date_debut": self.today,
        }, format="json")
        self.assertEqual(resp.status_code, 403)
