"""Tests FLOTTE26 — Infraction / PV de circulation.

Couvre :
- Modèle ``Infraction`` :
  - création simple + valeurs par défaut ;
  - validations ``clean`` (actif d'une autre société, conducteur d'une autre
    société, montant d'amende négatif).
- Selector ``infractions_de_la_societe`` : scope société + filtres
  (statut, actif, type).
- Endpoints API ``/infractions/`` :
  - CRUD scopé société (multi-tenant : company posée serveur, jamais du body) ;
  - lecture tout rôle, écriture responsable/admin (role gate) ;
  - actif / conducteur d'une autre société refusés ;
  - filtres ``?statut=`` / ``?actif_flotte=`` / ``?type_infraction=`` ;
  - champ fichier (PV scanné).
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
    Conducteur,
    Infraction,
    Vehicule,
)
from apps.flotte.selectors import infractions_de_la_societe

User = get_user_model()

URL = "/api/django/flotte/infractions/"


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


def make_actif(company, immat="INF-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


def make_conducteur(company, nom="Ahmed"):
    return Conducteur.objects.create(company=company, nom=nom)


# ── Modèle : création + validations ─────────────────────────────────────────────

class InfractionModelTests(TestCase):
    def setUp(self):
        self.co = make_company("inf-model", "Inf Model")
        self.actif = make_actif(self.co, "IMOD")

    def test_creation_simple_defaults(self):
        i = Infraction.objects.create(
            company=self.co, actif_flotte=self.actif,
            date_infraction=datetime.date(2026, 6, 1))
        self.assertEqual(i.statut, Infraction.Statut.A_PAYER)
        self.assertEqual(
            i.type_infraction, Infraction.TypeInfraction.EXCES_VITESSE)
        self.assertIsNone(i.montant_amende)
        self.assertIsNone(i.conducteur_id)

    def test_actif_autre_societe_rejete(self):
        autre = make_company("inf-model-b", "Inf Model B")
        actif_b = make_actif(autre, "B")
        i = Infraction(
            company=self.co, actif_flotte=actif_b,
            date_infraction=datetime.date(2026, 6, 1))
        with self.assertRaises(ValidationError):
            i.full_clean()

    def test_conducteur_autre_societe_rejete(self):
        autre = make_company("inf-model-c", "Inf Model C")
        cond_b = make_conducteur(autre, "Karim")
        i = Infraction(
            company=self.co, actif_flotte=self.actif, conducteur=cond_b,
            date_infraction=datetime.date(2026, 6, 1))
        with self.assertRaises(ValidationError):
            i.full_clean()

    def test_montant_negatif_rejete(self):
        i = Infraction(
            company=self.co, actif_flotte=self.actif,
            date_infraction=datetime.date(2026, 6, 1),
            montant_amende=-1)
        with self.assertRaises(ValidationError):
            i.full_clean()


# ── Selector : scope société + filtres ───────────────────────────────────────────

class InfractionSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("inf-sel", "Inf Sel")
        self.actif = make_actif(self.co, "ISEL")
        self.i1 = Infraction.objects.create(
            company=self.co, actif_flotte=self.actif,
            date_infraction=datetime.date(2026, 6, 1),
            statut=Infraction.Statut.A_PAYER,
            type_infraction=Infraction.TypeInfraction.EXCES_VITESSE)
        self.i2 = Infraction.objects.create(
            company=self.co, actif_flotte=self.actif,
            date_infraction=datetime.date(2026, 5, 1),
            statut=Infraction.Statut.PAYEE,
            type_infraction=Infraction.TypeInfraction.STATIONNEMENT)

    def test_scope_societe(self):
        autre = make_company("inf-sel-b", "Inf Sel B")
        actif_b = make_actif(autre, "B")
        Infraction.objects.create(
            company=autre, actif_flotte=actif_b,
            date_infraction=datetime.date(2026, 6, 1))
        self.assertEqual(infractions_de_la_societe(self.co).count(), 2)
        self.assertEqual(infractions_de_la_societe(autre).count(), 1)

    def test_filtre_par_statut(self):
        qs = infractions_de_la_societe(
            self.co, statut=Infraction.Statut.PAYEE)
        self.assertEqual([i.id for i in qs], [self.i2.id])

    def test_filtre_par_type(self):
        qs = infractions_de_la_societe(
            self.co, type_infraction=Infraction.TypeInfraction.EXCES_VITESSE)
        self.assertEqual([i.id for i in qs], [self.i1.id])

    def test_filtre_par_actif(self):
        actif2 = make_actif(self.co, "ISEL-2")
        autre = Infraction.objects.create(
            company=self.co, actif_flotte=actif2,
            date_infraction=datetime.date(2026, 6, 1))
        qs = infractions_de_la_societe(self.co, actif_flotte_id=actif2.id)
        self.assertEqual([i.id for i in qs], [autre.id])


# ── API : CRUD scopé + role gate + filtres + fichier ─────────────────────────────

class InfractionApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("inf-a", "Inf A")
        self.co_b = make_company("inf-b", "Inf B")
        self.admin_a = make_user(self.co_a, "inf-admin-a", "admin")
        self.user_a = make_user(self.co_a, "inf-user-a", "normal")
        self.actif = make_actif(self.co_a, "API")

    def test_create_company_server_side(self):
        cond = make_conducteur(self.co_a, "Said")
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "conducteur": cond.id,
            "date_infraction": "2026-06-01",
            "type_infraction": "feu_rouge",
            "lieu": "Casablanca",
            "reference_pv": "PV-2026-001",
            "montant_amende": "700.00",
            "company": self.co_b.id,  # injection ignorée.
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        i = Infraction.objects.get()
        self.assertEqual(i.company_id, self.co_a.id)
        self.assertEqual(resp.data["statut"], "a_payer")
        self.assertIn("type_infraction_display", resp.data)
        self.assertEqual(resp.data["conducteur_nom"], "Said")

    def test_create_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL, {
            "actif_flotte": self.actif.id,
            "date_infraction": "2026-06-01",
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(Infraction.objects.count(), 0)

    def test_actif_autre_societe_refuse(self):
        actif_b = make_actif(self.co_b, "B")
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": actif_b.id,
            "date_infraction": "2026-06-01",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_conducteur_autre_societe_refuse(self):
        cond_b = make_conducteur(self.co_b, "Brahim")
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "conducteur": cond_b.id,
            "date_infraction": "2026-06-01",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_list_scoped_and_read_any_role(self):
        Infraction.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            date_infraction=datetime.date(2026, 6, 1))
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
        admin_b = make_user(self.co_b, "inf-admin-b", "admin")
        self.assertEqual(rows(auth(admin_b).get(URL)), [])

    def test_update_and_delete(self):
        i = Infraction.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            date_infraction=datetime.date(2026, 6, 1))
        resp = auth(self.admin_a).patch(
            f"{URL}{i.id}/",
            {"statut": "payee", "date_paiement": "2026-06-15"},
            format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        i.refresh_from_db()
        self.assertEqual(i.statut, "payee")
        self.assertEqual(i.date_paiement, datetime.date(2026, 6, 15))
        resp = auth(self.admin_a).delete(f"{URL}{i.id}/")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(Infraction.objects.count(), 0)

    def test_filtre_par_statut(self):
        Infraction.objects.create(
            company=self.co_a, actif_flotte=self.actif, statut="a_payer",
            date_infraction=datetime.date(2026, 6, 1))
        Infraction.objects.create(
            company=self.co_a, actif_flotte=self.actif, statut="payee",
            date_infraction=datetime.date(2026, 5, 1))
        resp = auth(self.admin_a).get(f"{URL}?statut=payee")
        self.assertEqual(len(rows(resp)), 1)

    def test_filtre_par_type(self):
        Infraction.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            type_infraction="exces_vitesse",
            date_infraction=datetime.date(2026, 6, 1))
        Infraction.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            type_infraction="stationnement",
            date_infraction=datetime.date(2026, 5, 1))
        resp = auth(self.admin_a).get(f"{URL}?type_infraction=exces_vitesse")
        self.assertEqual(len(rows(resp)), 1)

    def test_filtre_par_actif_flotte(self):
        actif2 = make_actif(self.co_a, "API-2")
        Infraction.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            date_infraction=datetime.date(2026, 6, 1))
        Infraction.objects.create(
            company=self.co_a, actif_flotte=actif2,
            date_infraction=datetime.date(2026, 6, 1))
        resp = auth(self.admin_a).get(f"{URL}?actif_flotte={self.actif.id}")
        self.assertEqual(len(rows(resp)), 1)

    def test_pv_fichier_upload(self):
        f = SimpleUploadedFile(
            "pv.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "date_infraction": "2026-06-01",
            "pv_fichier": f,
        }, format="multipart")
        self.assertEqual(resp.status_code, 201, resp.data)
        i = Infraction.objects.get()
        self.assertTrue(i.pv_fichier.name)
        self.assertIn("flotte/infractions/pv/", i.pv_fichier.name)
