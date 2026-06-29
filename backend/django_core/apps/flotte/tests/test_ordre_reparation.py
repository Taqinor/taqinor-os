"""Tests FLOTTE17 — Garage + OrdreReparation (ordres de réparation + coûts).

Couvre :
- Modèle ``OrdreReparation`` :
  - ``cout_total`` CALCULÉ (main d'œuvre + pièces) figé en base à chaque save.
  - validations ``clean`` (société des FKs, dates, coûts négatifs).
- Service ``cloturer_ordre_reparation`` :
  - clôture l'OR (statut + date) et l'échéance liée (``fait``) par défaut ;
  - ``cloturer_echeance=False`` laisse l'échéance intacte ; idempotent.
- Selector ``couts_reparation`` : totaux + moyenne (garde-fou division par zéro)
  + scope société + filtres.
- Endpoints API ``/garages/`` et ``/ordres-reparation/`` :
  - CRUD scopé société (multi-tenant : company posée serveur, jamais du body) ;
  - lecture tout rôle, écriture responsable/admin (role gate) ;
  - action ``couts`` (lecture) et ``cloturer`` (écriture) ;
  - ``cout_total`` jamais accepté du body (lecture seule).
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    EcheanceEntretien,
    Garage,
    OrdreReparation,
    PlanEntretien,
    Vehicule,
)
from apps.flotte.selectors import couts_reparation
from apps.flotte.services import cloturer_ordre_reparation

User = get_user_model()

URL_GARAGES = "/api/django/flotte/garages/"
URL_OR = "/api/django/flotte/ordres-reparation/"
URL_COUTS = "/api/django/flotte/ordres-reparation/couts/"


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


def make_vehicule(company, immat="OR-1", km=0):
    return Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel",
        kilometrage=km)


def actif_pour_vehicule(company, vehicule):
    return ActifFlotte.objects.create(company=company, vehicule=vehicule)


def make_garage(company, nom="Atelier Central"):
    return Garage.objects.create(company=company, nom=nom)


def make_or(company, actif, garage=None, mo=0, pieces=0, **kwargs):
    return OrdreReparation.objects.create(
        company=company, actif_flotte=actif, garage=garage,
        date_ouverture=kwargs.pop("date_ouverture", datetime.date.today()),
        cout_main_oeuvre=mo, cout_pieces=pieces, **kwargs)


# ── Modèle : coût total calculé + validations ─────────────────────────────────

class ModelTests(TestCase):
    def setUp(self):
        self.co = make_company("or-model", "OR Model")
        self.veh = make_vehicule(self.co, "MOD")
        self.actif = actif_pour_vehicule(self.co, self.veh)

    def test_cout_total_calcule_au_save(self):
        ordre = make_or(self.co, self.actif, mo=300, pieces=200)
        self.assertEqual(float(ordre.cout_total), 500.0)

    def test_cout_total_recalcule_a_chaque_save(self):
        ordre = make_or(self.co, self.actif, mo=100, pieces=50)
        ordre.cout_pieces = 250
        ordre.save()
        ordre.refresh_from_db()
        self.assertEqual(float(ordre.cout_total), 350.0)

    def test_actif_autre_societe_rejete(self):
        autre = make_company("or-model-b", "OR Model B")
        veh_b = make_vehicule(autre, "B")
        actif_b = actif_pour_vehicule(autre, veh_b)
        ordre = OrdreReparation(
            company=self.co, actif_flotte=actif_b,
            date_ouverture=datetime.date.today())
        with self.assertRaises(ValidationError):
            ordre.full_clean()

    def test_garage_autre_societe_rejete(self):
        autre = make_company("or-model-c", "OR Model C")
        garage_b = make_garage(autre, "Atelier B")
        ordre = OrdreReparation(
            company=self.co, actif_flotte=self.actif, garage=garage_b,
            date_ouverture=datetime.date.today())
        with self.assertRaises(ValidationError):
            ordre.full_clean()

    def test_cloture_avant_ouverture_rejete(self):
        ordre = OrdreReparation(
            company=self.co, actif_flotte=self.actif,
            date_ouverture=datetime.date(2026, 6, 10),
            date_cloture=datetime.date(2026, 6, 1))
        with self.assertRaises(ValidationError):
            ordre.full_clean()

    def test_cout_negatif_rejete(self):
        ordre = OrdreReparation(
            company=self.co, actif_flotte=self.actif,
            date_ouverture=datetime.date.today(), cout_pieces=-10)
        with self.assertRaises(ValidationError):
            ordre.full_clean()


# ── Service : clôture de l'OR + échéance liée ─────────────────────────────────

class ClotureTests(TestCase):
    def setUp(self):
        self.co = make_company("or-clot", "OR Clot")
        self.veh = make_vehicule(self.co, "CLOT", km=25000)
        self.actif = actif_pour_vehicule(self.co, self.veh)
        self.plan = PlanEntretien.objects.create(
            company=self.co, actif_flotte=self.actif, type_entretien="vidange",
            intervalle_km=10000, dernier_km=10000)
        self.echeance = EcheanceEntretien.objects.create(
            company=self.co, plan=self.plan, actif_flotte=self.actif,
            type_entretien="vidange", due_km=20000)

    def test_cloture_solde_l_echeance(self):
        ordre = make_or(self.co, self.actif, echeance=self.echeance)
        cloturer_ordre_reparation(ordre)
        ordre.refresh_from_db()
        self.echeance.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreReparation.Statut.CLOTURE)
        self.assertIsNotNone(ordre.date_cloture)
        self.assertEqual(self.echeance.statut, EcheanceEntretien.Statut.FAIT)

    def test_cloture_sans_toucher_echeance(self):
        ordre = make_or(self.co, self.actif, echeance=self.echeance)
        cloturer_ordre_reparation(ordre, cloturer_echeance=False)
        self.echeance.refresh_from_db()
        self.assertEqual(self.echeance.statut, EcheanceEntretien.Statut.A_FAIRE)

    def test_cloture_sans_echeance_liee_ne_crash_pas(self):
        ordre = make_or(self.co, self.actif)
        ordre, close = cloturer_ordre_reparation(ordre)
        self.assertEqual(ordre.statut, OrdreReparation.Statut.CLOTURE)
        self.assertIsNone(close)

    def test_cloture_idempotente(self):
        ordre = make_or(self.co, self.actif)
        cloturer_ordre_reparation(ordre, date_cloture=datetime.date(2026, 6, 1))
        first_date = ordre.date_cloture
        cloturer_ordre_reparation(ordre)
        ordre.refresh_from_db()
        self.assertEqual(ordre.date_cloture, first_date)


# ── Selector couts_reparation ─────────────────────────────────────────────────

class CoutsSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("or-couts", "OR Couts")
        self.co_b = make_company("or-couts-b", "OR Couts B")
        self.veh = make_vehicule(self.co, "C1")
        self.actif = actif_pour_vehicule(self.co, self.veh)

    def test_totaux_et_moyenne(self):
        make_or(self.co, self.actif, mo=300, pieces=200)   # total 500
        make_or(self.co, self.actif, mo=100, pieces=100)   # total 200
        res = couts_reparation(self.co)
        self.assertEqual(res["nb_ordres"], 2)
        self.assertEqual(res["cout_main_oeuvre"], 400.0)
        self.assertEqual(res["cout_pieces"], 300.0)
        self.assertEqual(res["cout_total"], 700.0)
        self.assertEqual(res["cout_moyen"], 350.0)

    def test_aucun_ordre_pas_de_division_par_zero(self):
        res = couts_reparation(self.co)
        self.assertEqual(res["nb_ordres"], 0)
        self.assertEqual(res["cout_total"], 0.0)
        self.assertIsNone(res["cout_moyen"])

    def test_scoped_to_company(self):
        make_or(self.co, self.actif, mo=500)
        self.assertEqual(couts_reparation(self.co)["nb_ordres"], 1)
        self.assertEqual(couts_reparation(self.co_b)["nb_ordres"], 0)


# ── Endpoint API ──────────────────────────────────────────────────────────────

class ApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("or-api-a", "OR Api A")
        self.co_b = make_company("or-api-b", "OR Api B")
        self.admin_a = make_user(self.co_a, "or-admin-a", "admin")
        self.user_a = make_user(self.co_a, "or-user-a", "normal")
        self.veh = make_vehicule(self.co_a, "API")
        self.actif_a = actif_pour_vehicule(self.co_a, self.veh)
        self.garage_a = make_garage(self.co_a)

    def test_create_garage_company_server_side(self):
        resp = auth(self.admin_a).post(URL_GARAGES, {
            "nom": "Garage du Sud", "telephone": "0600000000",
            "company": self.co_b.id,  # tentative d'injection : ignorée.
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        garage = Garage.objects.get(nom="Garage du Sud")
        self.assertEqual(garage.company_id, self.co_a.id)

    def test_create_or_company_server_side_and_cout_total(self):
        resp = auth(self.admin_a).post(URL_OR, {
            "actif_flotte": self.actif_a.id,
            "garage": self.garage_a.id,
            "date_ouverture": "2026-06-10",
            "cout_main_oeuvre": "300.00",
            "cout_pieces": "200.00",
            "cout_total": "999.00",  # ignoré (lecture seule).
            "company": self.co_b.id,  # injection ignorée.
            "description": "Remplacement plaquettes",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        ordre = OrdreReparation.objects.get()
        self.assertEqual(ordre.company_id, self.co_a.id)
        self.assertEqual(float(ordre.cout_total), 500.0)  # calculé, pas 999.

    def test_create_or_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL_OR, {
            "actif_flotte": self.actif_a.id,
            "date_ouverture": "2026-06-10",
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(OrdreReparation.objects.count(), 0)

    def test_list_scoped_and_read_any_role(self):
        make_or(self.co_a, self.actif_a, mo=100)
        # Lecture autorisée à tout rôle.
        resp = auth(self.user_a).get(URL_OR)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
        # Société B ne voit rien.
        admin_b = make_user(self.co_b, "or-admin-b", "admin")
        self.assertEqual(rows(auth(admin_b).get(URL_OR)), [])

    def test_actif_autre_societe_refuse(self):
        veh_b = make_vehicule(self.co_b, "B")
        actif_b = actif_pour_vehicule(self.co_b, veh_b)
        resp = auth(self.admin_a).post(URL_OR, {
            "actif_flotte": actif_b.id,
            "date_ouverture": "2026-06-10",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_couts_action_read_any_role(self):
        make_or(self.co_a, self.actif_a, mo=300, pieces=200)
        resp = auth(self.user_a).get(URL_COUTS)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["cout_total"], 500.0)
        self.assertEqual(resp.data["cout_moyen"], 500.0)

    def test_cloturer_action_admin(self):
        ordre = make_or(self.co_a, self.actif_a)
        resp = auth(self.admin_a).post(f"{URL_OR}{ordre.id}/cloturer/")
        self.assertEqual(resp.status_code, 200, resp.data)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreReparation.Statut.CLOTURE)

    def test_cloturer_action_forbidden_for_normal_role(self):
        ordre = make_or(self.co_a, self.actif_a)
        resp = auth(self.user_a).post(f"{URL_OR}{ordre.id}/cloturer/")
        self.assertEqual(resp.status_code, 403, resp.data)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreReparation.Statut.OUVERT)

    def test_filtre_ouverts(self):
        make_or(self.co_a, self.actif_a)  # ouvert
        clos = make_or(self.co_a, self.actif_a, statut="cloture")
        clos.save()
        resp = auth(self.admin_a).get(f"{URL_OR}?ouverts=true")
        self.assertEqual(len(rows(resp)), 1)
