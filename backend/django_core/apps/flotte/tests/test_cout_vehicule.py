"""Tests XFLT3 — Grand livre des coûts par véhicule.

Couvre :
- Modèle ``CoutVehicule`` : validations ``clean`` (société de l'actif/
  conducteur, montant négatif).
- Selector ``ledger_vehicule(company, vehicule_id)`` : fusion chronologique
  de PleinCarburant, OrdreReparation, AssuranceVehicule, TSAV, Infraction,
  CoutVehicule — triée par date décroissante, avec catégorie + source.
- Endpoints API :
  - ``/couts/`` CRUD scopé société (multi-tenant), filtres
    ``?actif_flotte=`` / ``?categorie=`` ;
  - ``/vehicules/<id>/ledger/`` (lecture tout rôle) — historique fusionné.
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
    AssuranceVehicule,
    CoutVehicule,
    Infraction,
    OrdreReparation,
    PleinCarburant,
    Vehicule,
)
from apps.flotte.selectors import ledger_vehicule

User = get_user_model()

URL = "/api/django/flotte/couts/"


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


def make_actif(company, immat="CV-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return veh, ActifFlotte.objects.create(company=company, vehicule=veh)


# ── Modèle : validations ────────────────────────────────────────────────────────

class CoutVehiculeModelTests(TestCase):
    def setUp(self):
        self.co = make_company("cv-model", "Cv Model")
        self.veh, self.actif = make_actif(self.co, "CMOD")

    def test_creation_simple(self):
        cout = CoutVehicule.objects.create(
            company=self.co, actif_flotte=self.actif, categorie="peage",
            date=datetime.date(2026, 6, 1), montant=45, fournisseur="Jawaz")
        self.assertEqual(float(cout.montant), 45.0)

    def test_actif_autre_societe_rejete(self):
        autre = make_company("cv-model-b", "Cv Model B")
        _, actif_b = make_actif(autre, "B")
        cout = CoutVehicule(
            company=self.co, actif_flotte=actif_b,
            date=datetime.date(2026, 6, 1), montant=10)
        with self.assertRaises(ValidationError):
            cout.full_clean()

    def test_montant_negatif_rejete(self):
        cout = CoutVehicule(
            company=self.co, actif_flotte=self.actif,
            date=datetime.date(2026, 6, 1), montant=-5)
        with self.assertRaises(ValidationError):
            cout.full_clean()


# ── Selector : ledger_vehicule (fusion multi-source) ────────────────────────────

class LedgerVehiculeSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("cv-ledger", "Cv Ledger")
        self.veh, self.actif = make_actif(self.co, "LEDGER")

    def test_fusion_multi_source(self):
        PleinCarburant.objects.create(
            company=self.co, vehicule=self.veh,
            date_plein=datetime.date(2026, 5, 1), kilometrage=1000,
            quantite=40, prix_total=440)
        OrdreReparation.objects.create(
            company=self.co, actif_flotte=self.actif,
            date_ouverture=datetime.date(2026, 5, 5),
            cout_main_oeuvre=300, cout_pieces=200)
        AssuranceVehicule.objects.create(
            company=self.co, actif_flotte=self.actif, assureur="Wafa",
            numero_police="P1", date_debut=datetime.date(2026, 1, 1),
            date_echeance=datetime.date(2026, 12, 31), franchise=1500)
        Infraction.objects.create(
            company=self.co, actif_flotte=self.actif,
            date_infraction=datetime.date(2026, 5, 10),
            montant_amende=400)
        CoutVehicule.objects.create(
            company=self.co, actif_flotte=self.actif, categorie="peage",
            date=datetime.date(2026, 5, 15), montant=50)

        result = ledger_vehicule(self.co, self.veh.id)
        self.assertEqual(result['nb_lignes'], 5)
        sources = {ligne['source'] for ligne in result['lignes']}
        self.assertEqual(
            sources,
            {'carburant', 'reparation', 'assurance', 'infraction',
             'cout_divers'})

    def test_trie_par_date_decroissante(self):
        CoutVehicule.objects.create(
            company=self.co, actif_flotte=self.actif, categorie="peage",
            date=datetime.date(2026, 1, 1), montant=10)
        CoutVehicule.objects.create(
            company=self.co, actif_flotte=self.actif, categorie="parking",
            date=datetime.date(2026, 6, 1), montant=20)
        result = ledger_vehicule(self.co, self.veh.id)
        dates = [ligne['date'] for ligne in result['lignes']]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_scope_societe_vehicule_inexistant(self):
        result = ledger_vehicule(self.co, 999999)
        self.assertEqual(result['nb_lignes'], 0)
        self.assertEqual(result['lignes'], [])

    def test_saisie_peage_possible(self):
        """XFLT3 — un péage/parking/lavage se saisit via CoutVehicule (aucun
        autre modèle ne le capture)."""
        cout = CoutVehicule.objects.create(
            company=self.co, actif_flotte=self.actif, categorie="peage",
            date=datetime.date(2026, 6, 1), montant=45,
            fournisseur="Jawaz", reference_piece="JWZ-001")
        result = ledger_vehicule(self.co, self.veh.id)
        objet_ids = {
            ligne['objet_id'] for ligne in result['lignes']
            if ligne['source'] == 'cout_divers'
        }
        self.assertIn(cout.id, objet_ids)


# ── API : CRUD scopé + ledger action ────────────────────────────────────────────

class CoutVehiculeApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("cv-a", "Cv A")
        self.co_b = make_company("cv-b", "Cv B")
        self.admin_a = make_user(self.co_a, "cv-admin-a", "admin")
        self.user_a = make_user(self.co_a, "cv-user-a", "normal")
        self.veh, self.actif = make_actif(self.co_a, "API")

    def test_create_company_server_side(self):
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "categorie": "peage",
            "date": "2026-06-01",
            "montant": "45.00",
            "fournisseur": "Jawaz",
            "company": self.co_b.id,  # injection ignorée.
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        cout = CoutVehicule.objects.get()
        self.assertEqual(cout.company_id, self.co_a.id)

    def test_create_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL, {
            "actif_flotte": self.actif.id,
            "date": "2026-06-01", "montant": "10",
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_filtre_par_actif_et_categorie(self):
        CoutVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif, categorie="peage",
            date=datetime.date(2026, 6, 1), montant=45)
        CoutVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif, categorie="lavage",
            date=datetime.date(2026, 6, 2), montant=30)
        resp = auth(self.admin_a).get(f"{URL}?categorie=peage")
        self.assertEqual(len(rows(resp)), 1)

    def test_ledger_endpoint_read_any_role(self):
        CoutVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif, categorie="peage",
            date=datetime.date(2026, 6, 1), montant=45)
        url_ledger = f"/api/django/flotte/vehicules/{self.veh.id}/ledger/"
        resp = auth(self.user_a).get(url_ledger)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_lignes'], 1)

    def test_scope_societe_list(self):
        CoutVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif, categorie="peage",
            date=datetime.date(2026, 6, 1), montant=45)
        admin_b = make_user(self.co_b, "cv-admin-b", "admin")
        resp = auth(admin_b).get(URL)
        self.assertEqual(rows(resp), [])
