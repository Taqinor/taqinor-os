"""Tests FLOTTE25 — Sinistre (accident / constat / assurance).

Couvre :
- Modèle ``Sinistre`` :
  - création simple + valeurs par défaut ;
  - validations ``clean`` (actif d'une autre société, police d'une autre
    société, montant estimé / franchise négatifs).
- Selector ``sinistres_de_la_societe`` : scope société + filtres
  (statut, actif, type).
- Endpoints API ``/sinistres/`` :
  - CRUD scopé société (multi-tenant : company posée serveur, jamais du body) ;
  - lecture tout rôle, écriture responsable/admin (role gate) ;
  - actif / police d'une autre société refusés ;
  - filtres ``?statut=`` / ``?actif_flotte=`` / ``?type_sinistre=`` ;
  - champ fichier (constat amiable).
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    AssuranceVehicule,
    Sinistre,
    Vehicule,
)
from apps.flotte.selectors import sinistres_de_la_societe

User = get_user_model()

URL = "/api/django/flotte/sinistres/"


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


def make_actif(company, immat="SIN-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


def make_assurance(company, actif, police="POL-1"):
    return AssuranceVehicule.objects.create(
        company=company, actif_flotte=actif, assureur="Wafa",
        numero_police=police, date_echeance=datetime.date(2027, 1, 1))


# ── Modèle : création + validations ─────────────────────────────────────────────

class SinistreModelTests(TestCase):
    def setUp(self):
        self.co = make_company("sin-model", "Sin Model")
        self.actif = make_actif(self.co, "SMOD")

    def test_creation_simple_defaults(self):
        s = Sinistre.objects.create(
            company=self.co, actif_flotte=self.actif,
            date_sinistre=datetime.date(2026, 6, 1),
            description="Choc arrière au feu rouge.")
        self.assertEqual(s.statut, Sinistre.Statut.DECLARE)
        self.assertEqual(
            s.type_sinistre, Sinistre.TypeSinistre.ACCIDENT_MATERIEL)
        self.assertIsNone(s.montant_estime)

    def test_actif_autre_societe_rejete(self):
        autre = make_company("sin-model-b", "Sin Model B")
        actif_b = make_actif(autre, "B")
        s = Sinistre(
            company=self.co, actif_flotte=actif_b,
            date_sinistre=datetime.date(2026, 6, 1), description="x")
        with self.assertRaises(ValidationError):
            s.full_clean()

    def test_assurance_autre_societe_rejete(self):
        autre = make_company("sin-model-c", "Sin Model C")
        actif_b = make_actif(autre, "C")
        assur_b = make_assurance(autre, actif_b, "POL-B")
        s = Sinistre(
            company=self.co, actif_flotte=self.actif, assurance=assur_b,
            date_sinistre=datetime.date(2026, 6, 1), description="x")
        with self.assertRaises(ValidationError):
            s.full_clean()

    def test_montant_negatif_rejete(self):
        s = Sinistre(
            company=self.co, actif_flotte=self.actif,
            date_sinistre=datetime.date(2026, 6, 1), description="x",
            montant_estime=-1)
        with self.assertRaises(ValidationError):
            s.full_clean()

    def test_franchise_negative_rejete(self):
        s = Sinistre(
            company=self.co, actif_flotte=self.actif,
            date_sinistre=datetime.date(2026, 6, 1), description="x",
            franchise=-5)
        with self.assertRaises(ValidationError):
            s.full_clean()


# ── Selector : scope société + filtres ───────────────────────────────────────────

class SinistreSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("sin-sel", "Sin Sel")
        self.actif = make_actif(self.co, "SSEL")
        self.s1 = Sinistre.objects.create(
            company=self.co, actif_flotte=self.actif,
            date_sinistre=datetime.date(2026, 6, 1), description="a",
            statut=Sinistre.Statut.DECLARE,
            type_sinistre=Sinistre.TypeSinistre.VOL)
        self.s2 = Sinistre.objects.create(
            company=self.co, actif_flotte=self.actif,
            date_sinistre=datetime.date(2026, 5, 1), description="b",
            statut=Sinistre.Statut.CLOS,
            type_sinistre=Sinistre.TypeSinistre.BRIS_DE_GLACE)

    def test_scope_societe(self):
        autre = make_company("sin-sel-b", "Sin Sel B")
        actif_b = make_actif(autre, "B")
        Sinistre.objects.create(
            company=autre, actif_flotte=actif_b,
            date_sinistre=datetime.date(2026, 6, 1), description="x")
        self.assertEqual(sinistres_de_la_societe(self.co).count(), 2)
        self.assertEqual(sinistres_de_la_societe(autre).count(), 1)

    def test_filtre_par_statut(self):
        qs = sinistres_de_la_societe(
            self.co, statut=Sinistre.Statut.CLOS)
        self.assertEqual([s.id for s in qs], [self.s2.id])

    def test_filtre_par_type(self):
        qs = sinistres_de_la_societe(
            self.co, type_sinistre=Sinistre.TypeSinistre.VOL)
        self.assertEqual([s.id for s in qs], [self.s1.id])

    def test_filtre_par_actif(self):
        actif2 = make_actif(self.co, "SSEL-2")
        autre = Sinistre.objects.create(
            company=self.co, actif_flotte=actif2,
            date_sinistre=datetime.date(2026, 6, 1), description="c")
        qs = sinistres_de_la_societe(self.co, actif_flotte_id=actif2.id)
        self.assertEqual([s.id for s in qs], [autre.id])


# ── API : CRUD scopé + role gate + filtres + fichier ─────────────────────────────

class SinistreApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("sin-a", "Sin A")
        self.co_b = make_company("sin-b", "Sin B")
        self.admin_a = make_user(self.co_a, "sin-admin-a", "admin")
        self.user_a = make_user(self.co_a, "sin-user-a", "normal")
        self.actif = make_actif(self.co_a, "API")

    def test_create_company_server_side(self):
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "date_sinistre": "2026-06-01",
            "type_sinistre": "accident_materiel",
            "description": "Choc latéral parking.",
            "lieu": "Casablanca",
            "numero_declaration": "DECL-2026-001",
            "montant_estime": "8500.00",
            "franchise": "2500.00",
            "company": self.co_b.id,  # injection ignorée.
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        s = Sinistre.objects.get()
        self.assertEqual(s.company_id, self.co_a.id)
        self.assertEqual(resp.data["statut"], "declare")
        self.assertIn("type_sinistre_display", resp.data)

    def test_create_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL, {
            "actif_flotte": self.actif.id,
            "date_sinistre": "2026-06-01",
            "description": "x",
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(Sinistre.objects.count(), 0)

    def test_actif_autre_societe_refuse(self):
        actif_b = make_actif(self.co_b, "B")
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": actif_b.id,
            "date_sinistre": "2026-06-01",
            "description": "x",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_assurance_autre_societe_refuse(self):
        actif_b = make_actif(self.co_b, "B")
        assur_b = make_assurance(self.co_b, actif_b, "POL-B")
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "assurance": assur_b.id,
            "date_sinistre": "2026-06-01",
            "description": "x",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_list_scoped_and_read_any_role(self):
        Sinistre.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            date_sinistre=datetime.date(2026, 6, 1), description="a")
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
        admin_b = make_user(self.co_b, "sin-admin-b", "admin")
        self.assertEqual(rows(auth(admin_b).get(URL)), [])

    def test_update_and_delete(self):
        s = Sinistre.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            date_sinistre=datetime.date(2026, 6, 1), description="a")
        resp = auth(self.admin_a).patch(
            f"{URL}{s.id}/", {"statut": "indemnise"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        s.refresh_from_db()
        self.assertEqual(s.statut, "indemnise")
        resp = auth(self.admin_a).delete(f"{URL}{s.id}/")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(Sinistre.objects.count(), 0)

    def test_filtre_par_statut(self):
        Sinistre.objects.create(
            company=self.co_a, actif_flotte=self.actif, statut="declare",
            date_sinistre=datetime.date(2026, 6, 1), description="a")
        Sinistre.objects.create(
            company=self.co_a, actif_flotte=self.actif, statut="clos",
            date_sinistre=datetime.date(2026, 5, 1), description="b")
        resp = auth(self.admin_a).get(f"{URL}?statut=clos")
        self.assertEqual(len(rows(resp)), 1)

    def test_filtre_par_type(self):
        Sinistre.objects.create(
            company=self.co_a, actif_flotte=self.actif, type_sinistre="vol",
            date_sinistre=datetime.date(2026, 6, 1), description="a")
        Sinistre.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            type_sinistre="bris_de_glace",
            date_sinistre=datetime.date(2026, 5, 1), description="b")
        resp = auth(self.admin_a).get(f"{URL}?type_sinistre=vol")
        self.assertEqual(len(rows(resp)), 1)

    def test_filtre_par_actif_flotte(self):
        actif2 = make_actif(self.co_a, "API-2")
        Sinistre.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            date_sinistre=datetime.date(2026, 6, 1), description="a")
        Sinistre.objects.create(
            company=self.co_a, actif_flotte=actif2,
            date_sinistre=datetime.date(2026, 6, 1), description="b")
        resp = auth(self.admin_a).get(f"{URL}?actif_flotte={self.actif.id}")
        self.assertEqual(len(rows(resp)), 1)

    def test_constat_fichier_upload(self):
        f = SimpleUploadedFile(
            "constat.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "date_sinistre": "2026-06-01",
            "description": "Accrochage avec constat.",
            "constat_fichier": f,
        }, format="multipart")
        self.assertEqual(resp.status_code, 201, resp.data)
        s = Sinistre.objects.get()
        self.assertTrue(s.constat_fichier.name)
        self.assertIn("flotte/sinistres/constats/", s.constat_fichier.name)
