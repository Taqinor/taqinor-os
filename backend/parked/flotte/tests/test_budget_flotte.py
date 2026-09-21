"""Tests XFLT18 — Budget flotte annuel vs réalisé.

Couvre :
- Selector ``variance_budget_flotte(company, annee)`` :
  - réalisé agrégé par catégorie budgétaire depuis le ledger (XFLT3) ;
  - catégories hors périmètre budget (amende/péage/parking/lavage)
    reclassées sous 'autre' ;
  - ``pct`` et ``niveau`` (rouge > 100 %, orange > 85 %, ok sinon) ;
  - budget non saisi → ``pct=None``, ``niveau=None``.
- Service ``verifier_depassements_budget`` : notifie une fois (idempotent —
  second appel = aucune notification supplémentaire, flag posé).
- Endpoint ``GET /rapports/budget/?annee=`` (lecture tout rôle).
- CRUD ``/budgets/`` scopé société, ``notifie_depassement`` jamais du body.
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    BudgetFlotte,
    CoutVehicule,
    PleinCarburant,
    Vehicule,
)
from apps.flotte.selectors import variance_budget_flotte
from apps.flotte.services import verifier_depassements_budget

User = get_user_model()

URL_RAPPORT = "/api/django/flotte/rapports/budget/"
URL_BUDGETS = "/api/django/flotte/budgets/"


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


class VarianceBudgetSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("bud-svc", "Bud Svc")

    def test_realise_agrege_par_categorie(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="BUD-1", energie="diesel")
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh,
            date_plein=datetime.date(2026, 3, 1), kilometrage=1000,
            quantite=40, unite="litre", prix_total=500)
        BudgetFlotte.objects.create(
            company=self.co, annee=2026,
            categorie=BudgetFlotte.Categorie.CARBURANT, montant_budgete=1000)
        resultat = variance_budget_flotte(self.co, 2026)
        carburant = next(
            c for c in resultat["categories"] if c["categorie"] == "carburant")
        self.assertEqual(carburant["realise"], 500.0)
        self.assertEqual(carburant["budgete"], 1000.0)
        self.assertEqual(carburant["pct"], 50.0)
        self.assertEqual(carburant["niveau"], "ok")

    def test_categories_hors_perimetre_reclassees_autre(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="BUD-2", energie="diesel")
        actif = ActifFlotte.objects.create(company=self.co, vehicule=veh)
        CoutVehicule.objects.create(
            company=self.co, actif_flotte=actif, categorie="peage",
            date=datetime.date(2026, 2, 1), montant=100)
        resultat = variance_budget_flotte(self.co, 2026)
        autre = next(
            c for c in resultat["categories"] if c["categorie"] == "autre")
        self.assertEqual(autre["realise"], 100.0)

    def test_depassement_niveau_rouge(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="BUD-3", energie="diesel")
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh,
            date_plein=datetime.date(2026, 3, 1), kilometrage=1000,
            quantite=40, unite="litre", prix_total=1500)
        BudgetFlotte.objects.create(
            company=self.co, annee=2026,
            categorie=BudgetFlotte.Categorie.CARBURANT, montant_budgete=1000)
        resultat = variance_budget_flotte(self.co, 2026)
        carburant = next(
            c for c in resultat["categories"] if c["categorie"] == "carburant")
        self.assertEqual(carburant["niveau"], "rouge")

    def test_orange_entre_85_et_100(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="BUD-4", energie="diesel")
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh,
            date_plein=datetime.date(2026, 3, 1), kilometrage=1000,
            quantite=40, unite="litre", prix_total=900)
        BudgetFlotte.objects.create(
            company=self.co, annee=2026,
            categorie=BudgetFlotte.Categorie.CARBURANT, montant_budgete=1000)
        resultat = variance_budget_flotte(self.co, 2026)
        carburant = next(
            c for c in resultat["categories"] if c["categorie"] == "carburant")
        self.assertEqual(carburant["niveau"], "orange")

    def test_budget_non_saisi_pct_none(self):
        resultat = variance_budget_flotte(self.co, 2026)
        carburant = next(
            c for c in resultat["categories"] if c["categorie"] == "carburant")
        self.assertIsNone(carburant["pct"])
        self.assertIsNone(carburant["niveau"])


class VerifierDepassementsServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("bud-notif", "Bud Notif")
        make_user(self.co, "bud-admin", role="admin")

    @mock.patch("apps.notifications.services.notify_many")
    def test_notifie_une_fois_idempotent(self, mock_notify):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="BUD-N1", energie="diesel")
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh,
            date_plein=datetime.date(2026, 3, 1), kilometrage=1000,
            quantite=40, unite="litre", prix_total=2000)
        BudgetFlotte.objects.create(
            company=self.co, annee=2026,
            categorie=BudgetFlotte.Categorie.CARBURANT, montant_budgete=1000)

        notifiees_1 = verifier_depassements_budget(self.co, 2026)
        self.assertEqual(notifiees_1, ["carburant"])
        self.assertEqual(mock_notify.call_count, 1)

        notifiees_2 = verifier_depassements_budget(self.co, 2026)
        self.assertEqual(notifiees_2, [])
        self.assertEqual(mock_notify.call_count, 1)

        budget = BudgetFlotte.objects.get(
            company=self.co, annee=2026, categorie="carburant")
        self.assertTrue(budget.notifie_depassement)


class RapportBudgetApiTests(TestCase):
    def setUp(self):
        self.co = make_company("bud-api", "Bud Api")
        self.user = make_user(self.co, "bud-user")

    def test_endpoint_lecture(self):
        resp = auth(self.user).get(URL_RAPPORT, {"annee": 2026})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["annee"], 2026)
        self.assertIn("categories", resp.data)


class BudgetFlotteCrudApiTests(TestCase):
    def setUp(self):
        self.co = make_company("bud-crud", "Bud Crud")
        self.user = make_user(self.co, "bud-crud-user")

    def test_notifie_depassement_non_acceptee_du_body(self):
        resp = auth(self.user).post(URL_BUDGETS, {
            "annee": 2026, "categorie": "carburant", "montant_budgete": 5000,
            "notifie_depassement": True,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data["notifie_depassement"])

    def test_montant_negatif_rejete(self):
        resp = auth(self.user).post(URL_BUDGETS, {
            "annee": 2026, "categorie": "entretien", "montant_budgete": -100,
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_filtre_annee(self):
        BudgetFlotte.objects.create(
            company=self.co, annee=2025, categorie="carburant",
            montant_budgete=1000)
        BudgetFlotte.objects.create(
            company=self.co, annee=2026, categorie="carburant",
            montant_budgete=2000)
        resp = auth(self.user).get(URL_BUDGETS, {"annee": 2026})
        self.assertEqual(resp.status_code, 200)
        rows = resp.data["results"] if isinstance(resp.data, dict) \
            and "results" in resp.data else resp.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["annee"], 2026)
