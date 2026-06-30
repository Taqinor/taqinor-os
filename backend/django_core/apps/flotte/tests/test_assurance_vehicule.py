"""Tests FLOTTE21 — AssuranceVehicule (police d'assurance auto).

Couvre :
- Modèle ``AssuranceVehicule`` :
  - validations ``clean`` (société de l'actif, échéance < début de couverture,
    franchise négative) ;
  - ``statut_calcule(today)`` (valide / a_renouveler / expiree), date injectable.
- Selectors :
  - ``assurances_vehicule_de_la_societe(company, ...)`` — scope société, filtres ;
  - ``assurances_vehicule_expirantes(company, within, today=...)``.
- Endpoints API ``/assurances/`` :
  - CRUD scopé société (multi-tenant : company posée serveur, jamais du body) ;
  - lecture tout rôle, écriture responsable/admin (role gate) ;
  - filtres ``?statut=`` / ``?actif_flotte=`` ;
  - action ``expirantes/?within=N`` (lecture).
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ActifFlotte, AssuranceVehicule, Vehicule
from apps.flotte.selectors import (
    assurances_vehicule_de_la_societe,
    assurances_vehicule_expirantes,
)

User = get_user_model()

URL = "/api/django/flotte/assurances/"
URL_EXPIRANTES = "/api/django/flotte/assurances/expirantes/"


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


def make_actif(company, immat="AS-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


# ── Modèle : validations + statut calculé ──────────────────────────────────────

class AssuranceVehiculeModelTests(TestCase):
    def setUp(self):
        self.co = make_company("assur-model", "Assur Model")
        self.actif = make_actif(self.co, "AMOD")

    def test_creation_simple(self):
        pol = AssuranceVehicule.objects.create(
            company=self.co, actif_flotte=self.actif,
            assureur="Wafa Assurance", numero_police="POL-123",
            date_echeance=datetime.date(2026, 12, 1), franchise=2500)
        self.assertEqual(pol.statut, AssuranceVehicule.Statut.VALIDE)
        self.assertEqual(float(pol.franchise), 2500.0)

    def test_actif_autre_societe_rejete(self):
        autre = make_company("assur-model-b", "Assur Model B")
        actif_b = make_actif(autre, "B")
        pol = AssuranceVehicule(
            company=self.co, actif_flotte=actif_b, assureur="X",
            numero_police="P", date_echeance=datetime.date(2026, 12, 1))
        with self.assertRaises(ValidationError):
            pol.full_clean()

    def test_echeance_avant_debut_rejete(self):
        pol = AssuranceVehicule(
            company=self.co, actif_flotte=self.actif, assureur="X",
            numero_police="P",
            date_debut=datetime.date(2026, 6, 1),
            date_echeance=datetime.date(2026, 1, 1))
        with self.assertRaises(ValidationError):
            pol.full_clean()

    def test_franchise_negative_rejete(self):
        pol = AssuranceVehicule(
            company=self.co, actif_flotte=self.actif, assureur="X",
            numero_police="P",
            date_echeance=datetime.date(2026, 12, 1), franchise=-5)
        with self.assertRaises(ValidationError):
            pol.full_clean()

    def test_statut_calcule_expiree(self):
        today = datetime.date(2026, 6, 15)
        pol = AssuranceVehicule(
            company=self.co, actif_flotte=self.actif, assureur="X",
            numero_police="P",
            date_echeance=datetime.date(2026, 6, 1), alerte_jours=30)
        self.assertEqual(
            pol.statut_calcule(today=today),
            AssuranceVehicule.Statut.EXPIREE)

    def test_statut_calcule_a_renouveler(self):
        today = datetime.date(2026, 6, 15)
        # échéance dans 20 j, marge 30 j → à renouveler.
        pol = AssuranceVehicule(
            company=self.co, actif_flotte=self.actif, assureur="X",
            numero_police="P",
            date_echeance=datetime.date(2026, 7, 5), alerte_jours=30)
        self.assertEqual(
            pol.statut_calcule(today=today),
            AssuranceVehicule.Statut.A_RENOUVELER)

    def test_statut_calcule_valide(self):
        today = datetime.date(2026, 6, 15)
        # échéance dans 100 j, marge 30 j → valide.
        pol = AssuranceVehicule(
            company=self.co, actif_flotte=self.actif, assureur="X",
            numero_police="P",
            date_echeance=datetime.date(2026, 9, 23), alerte_jours=30)
        self.assertEqual(
            pol.statut_calcule(today=today),
            AssuranceVehicule.Statut.VALIDE)


# ── Selectors : scope société + expirantes (date injectable) ───────────────────

class AssuranceVehiculeSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("assur-sel", "Assur Sel")
        self.actif = make_actif(self.co, "ASEL")
        self.today = datetime.date(2026, 6, 15)

        # Expirée (overdue).
        self.exp = AssuranceVehicule.objects.create(
            company=self.co, actif_flotte=self.actif, assureur="A",
            numero_police="P1",
            date_echeance=datetime.date(2026, 6, 1), alerte_jours=30)
        # Imminente — dans 10 j.
        self.upc = AssuranceVehicule.objects.create(
            company=self.co, actif_flotte=self.actif, assureur="B",
            numero_police="P2",
            date_echeance=datetime.date(2026, 6, 25), alerte_jours=30)
        # Valide — dans 200 j.
        self.ok = AssuranceVehicule.objects.create(
            company=self.co, actif_flotte=self.actif, assureur="C",
            numero_police="P3",
            date_echeance=datetime.date(2027, 1, 1), alerte_jours=30)

    def test_scope_societe(self):
        autre = make_company("assur-sel-b", "Assur Sel B")
        actif_b = make_actif(autre, "B")
        AssuranceVehicule.objects.create(
            company=autre, actif_flotte=actif_b, assureur="X",
            numero_police="PX", date_echeance=datetime.date(2026, 6, 1))
        self.assertEqual(
            assurances_vehicule_de_la_societe(self.co).count(), 3)
        self.assertEqual(
            assurances_vehicule_de_la_societe(autre).count(), 1)

    def test_filtre_par_statut(self):
        self.exp.statut = AssuranceVehicule.Statut.EXPIREE
        self.exp.save()
        qs = assurances_vehicule_de_la_societe(
            self.co, statut=AssuranceVehicule.Statut.EXPIREE)
        self.assertEqual([p.id for p in qs], [self.exp.id])

    def test_filtre_par_actif(self):
        actif2 = make_actif(self.co, "ASEL-2")
        autre_pol = AssuranceVehicule.objects.create(
            company=self.co, actif_flotte=actif2, assureur="D",
            numero_police="P4", date_echeance=datetime.date(2026, 12, 1))
        qs = assurances_vehicule_de_la_societe(
            self.co, actif_flotte_id=actif2.id)
        self.assertEqual([p.id for p in qs], [autre_pol.id])

    def test_expirantes_within(self):
        # within=15 j → expirée + imminente (10 j), pas la "valide".
        qs = assurances_vehicule_expirantes(
            self.co, within=15, today=self.today)
        ids = {p.id for p in qs}
        self.assertEqual(ids, {self.exp.id, self.upc.id})


# ── API : CRUD scopé + role gate + filtres + action expirantes ────────────────

class AssuranceVehiculeApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("assur-a", "Assur A")
        self.co_b = make_company("assur-b", "Assur B")
        self.admin_a = make_user(self.co_a, "as-admin-a", "admin")
        self.user_a = make_user(self.co_a, "as-user-a", "normal")
        self.actif = make_actif(self.co_a, "API")

    def test_create_company_server_side(self):
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "assureur": "Wafa Assurance",
            "numero_police": "WAF-2026-001",
            "date_debut": "2026-01-01",
            "date_echeance": "2026-12-31",
            "franchise": "2500.00",
            "company": self.co_b.id,  # injection ignorée.
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        pol = AssuranceVehicule.objects.get()
        self.assertEqual(pol.company_id, self.co_a.id)
        self.assertIn("statut_calcule", resp.data)

    def test_create_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL, {
            "actif_flotte": self.actif.id,
            "assureur": "X",
            "numero_police": "P",
            "date_echeance": "2026-12-01",
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(AssuranceVehicule.objects.count(), 0)

    def test_actif_autre_societe_refuse(self):
        actif_b = make_actif(self.co_b, "B")
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": actif_b.id,
            "assureur": "X",
            "numero_police": "P",
            "date_echeance": "2026-12-01",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_echeance_avant_debut_refuse(self):
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "assureur": "X",
            "numero_police": "P",
            "date_debut": "2026-12-01",
            "date_echeance": "2026-01-01",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_list_scoped_and_read_any_role(self):
        AssuranceVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif, assureur="A",
            numero_police="P", date_echeance=datetime.date(2026, 12, 1))
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
        admin_b = make_user(self.co_b, "as-admin-b", "admin")
        self.assertEqual(rows(auth(admin_b).get(URL)), [])

    def test_filtre_par_statut(self):
        AssuranceVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif, assureur="A",
            numero_police="P1", statut="expiree",
            date_echeance=datetime.date(2026, 1, 1))
        AssuranceVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif, assureur="B",
            numero_police="P2", statut="valide",
            date_echeance=datetime.date(2027, 1, 1))
        resp = auth(self.admin_a).get(f"{URL}?statut=expiree")
        self.assertEqual(len(rows(resp)), 1)

    def test_filtre_par_actif_flotte(self):
        actif2 = make_actif(self.co_a, "API-2")
        AssuranceVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif, assureur="A",
            numero_police="P1", date_echeance=datetime.date(2026, 12, 1))
        AssuranceVehicule.objects.create(
            company=self.co_a, actif_flotte=actif2, assureur="B",
            numero_police="P2", date_echeance=datetime.date(2026, 12, 1))
        resp = auth(self.admin_a).get(f"{URL}?actif_flotte={self.actif.id}")
        self.assertEqual(len(rows(resp)), 1)

    def test_expirantes_action_read_any_role(self):
        AssuranceVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif, assureur="A",
            numero_police="P1", date_echeance=datetime.date(2000, 1, 1))
        AssuranceVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif, assureur="B",
            numero_police="P2", date_echeance=datetime.date(2099, 1, 1))
        resp = auth(self.user_a).get(f"{URL_EXPIRANTES}?within=30")
        self.assertEqual(resp.status_code, 200, resp.data)
        # Seule l'expirée tombe dans la fenêtre (within ne capte pas 2099).
        self.assertEqual(len(rows(resp)), 1)

    def test_expirantes_within_invalide_retombe_30(self):
        AssuranceVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif, assureur="A",
            numero_police="P1", date_echeance=datetime.date(2000, 1, 1))
        resp = auth(self.admin_a).get(f"{URL_EXPIRANTES}?within=abc")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
