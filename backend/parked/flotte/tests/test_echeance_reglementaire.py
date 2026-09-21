"""Tests FLOTTE19 — EcheanceReglementaire (échéances réglementaires).

Couvre :
- Modèle ``EcheanceReglementaire`` :
  - validations ``clean`` (société de l'actif, échéance < dernier
    renouvellement, coût négatif) ;
  - ``statut_calcule(today)`` (a_jour / a_renouveler / expire), date injectable.
- Selectors :
  - ``echeances_reglementaires_status(company, today=...)`` — compteurs
    due/upcoming/overdue, scope société, date injectable ;
  - ``echeances_reglementaires_expirantes(company, within, today=...)``.
- Endpoints API ``/echeances-reglementaires/`` :
  - CRUD scopé société (multi-tenant : company posée serveur, jamais du body) ;
  - lecture tout rôle, écriture responsable/admin (role gate) ;
  - filtres ``?type=`` / ``?statut=`` / ``?actif_flotte=`` ;
  - action ``expirantes/?within=N`` (lecture).
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ActifFlotte, EcheanceReglementaire, Vehicule
from apps.flotte.selectors import (
    echeances_reglementaires_expirantes,
    echeances_reglementaires_status,
)

User = get_user_model()

URL = "/api/django/flotte/echeances-reglementaires/"
URL_EXPIRANTES = (
    "/api/django/flotte/echeances-reglementaires/expirantes/"
)


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


def make_actif(company, immat="ER-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


# ── Modèle : validations + statut calculé ──────────────────────────────────────

class EcheanceReglementaireModelTests(TestCase):
    def setUp(self):
        self.co = make_company("echreg-model", "Echreg Model")
        self.actif = make_actif(self.co, "EMOD")

    def test_creation_simple(self):
        ech = EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_echeance="visite_technique",
            date_echeance=datetime.date(2026, 12, 1),
            organisme="Centre VT Casa", cout=300)
        self.assertEqual(ech.statut, EcheanceReglementaire.Statut.A_JOUR)
        self.assertEqual(float(ech.cout), 300.0)

    def test_actif_autre_societe_rejete(self):
        autre = make_company("echreg-model-b", "Echreg Model B")
        actif_b = make_actif(autre, "B")
        ech = EcheanceReglementaire(
            company=self.co, actif_flotte=actif_b,
            date_echeance=datetime.date(2026, 12, 1))
        with self.assertRaises(ValidationError):
            ech.full_clean()

    def test_echeance_avant_renouvellement_rejete(self):
        ech = EcheanceReglementaire(
            company=self.co, actif_flotte=self.actif,
            date_echeance=datetime.date(2026, 1, 1),
            date_dernier_renouvellement=datetime.date(2026, 6, 1))
        with self.assertRaises(ValidationError):
            ech.full_clean()

    def test_cout_negatif_rejete(self):
        ech = EcheanceReglementaire(
            company=self.co, actif_flotte=self.actif,
            date_echeance=datetime.date(2026, 12, 1), cout=-5)
        with self.assertRaises(ValidationError):
            ech.full_clean()

    def test_statut_calcule_expire(self):
        today = datetime.date(2026, 6, 15)
        ech = EcheanceReglementaire(
            company=self.co, actif_flotte=self.actif,
            date_echeance=datetime.date(2026, 6, 1), alerte_jours=30)
        self.assertEqual(
            ech.statut_calcule(today=today),
            EcheanceReglementaire.Statut.EXPIRE)

    def test_statut_calcule_a_renouveler(self):
        today = datetime.date(2026, 6, 15)
        # échéance dans 20 j, marge 30 j → à renouveler.
        ech = EcheanceReglementaire(
            company=self.co, actif_flotte=self.actif,
            date_echeance=datetime.date(2026, 7, 5), alerte_jours=30)
        self.assertEqual(
            ech.statut_calcule(today=today),
            EcheanceReglementaire.Statut.A_RENOUVELER)

    def test_statut_calcule_a_jour(self):
        today = datetime.date(2026, 6, 15)
        # échéance dans 100 j, marge 30 j → à jour.
        ech = EcheanceReglementaire(
            company=self.co, actif_flotte=self.actif,
            date_echeance=datetime.date(2026, 9, 23), alerte_jours=30)
        self.assertEqual(
            ech.statut_calcule(today=today),
            EcheanceReglementaire.Statut.A_JOUR)


# ── Selectors : status + expirantes (date injectable) ──────────────────────────

class EcheanceReglementaireSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("echreg-sel", "Echreg Sel")
        self.actif = make_actif(self.co, "ESEL")
        self.today = datetime.date(2026, 6, 15)

        # Expirée (overdue).
        self.exp = EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif, type_echeance="assurance",
            date_echeance=datetime.date(2026, 6, 1), alerte_jours=30)
        # Imminente (upcoming) — dans 10 j.
        self.upc = EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_echeance="visite_technique",
            date_echeance=datetime.date(2026, 6, 25), alerte_jours=30)
        # À jour — dans 200 j.
        self.ok = EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif, type_echeance="vignette",
            date_echeance=datetime.date(2027, 1, 1), alerte_jours=30)

    def test_status_compteurs_date_injectable(self):
        result = echeances_reglementaires_status(self.co, today=self.today)
        self.assertEqual(result["nb_total"], 3)
        self.assertEqual(result["nb_overdue"], 1)
        self.assertEqual(result["nb_upcoming"], 1)
        self.assertEqual(result["nb_ok"], 1)
        # tri : expirée d'abord.
        self.assertEqual(
            result["echeances"][0]["statut_calcule"],
            EcheanceReglementaire.Statut.EXPIRE)

    def test_status_respecte_today_passe(self):
        # Un mois plus tôt, l'expirée n'est pas encore due.
        early = datetime.date(2026, 5, 1)
        result = echeances_reglementaires_status(self.co, today=early)
        self.assertEqual(result["nb_overdue"], 0)

    def test_status_scope_societe(self):
        autre = make_company("echreg-sel-b", "Echreg Sel B")
        actif_b = make_actif(autre, "B")
        EcheanceReglementaire.objects.create(
            company=autre, actif_flotte=actif_b,
            date_echeance=datetime.date(2026, 6, 1))
        result = echeances_reglementaires_status(autre, today=self.today)
        self.assertEqual(result["nb_total"], 1)

    def test_expirantes_within(self):
        # within=15 j → expirée + imminente (10 j), pas la "à jour".
        qs = echeances_reglementaires_expirantes(
            self.co, within=15, today=self.today)
        ids = {e.id for e in qs}
        self.assertEqual(ids, {self.exp.id, self.upc.id})


# ── API : CRUD scopé + role gate + filtres + action expirantes ────────────────

class EcheanceReglementaireApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("echreg-a", "Echreg A")
        self.co_b = make_company("echreg-b", "Echreg B")
        self.admin_a = make_user(self.co_a, "er-admin-a", "admin")
        self.user_a = make_user(self.co_a, "er-user-a", "normal")
        self.actif = make_actif(self.co_a, "API")

    def test_create_company_server_side(self):
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": self.actif.id,
            "type_echeance": "assurance",
            "date_echeance": "2026-12-01",
            "organisme": "Wafa Assurance",
            "cout": "1200.00",
            "company": self.co_b.id,  # injection ignorée.
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        ech = EcheanceReglementaire.objects.get()
        self.assertEqual(ech.company_id, self.co_a.id)
        self.assertIn("statut_calcule", resp.data)

    def test_create_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL, {
            "actif_flotte": self.actif.id,
            "type_echeance": "vignette",
            "date_echeance": "2026-12-01",
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(EcheanceReglementaire.objects.count(), 0)

    def test_actif_autre_societe_refuse(self):
        actif_b = make_actif(self.co_b, "B")
        resp = auth(self.admin_a).post(URL, {
            "actif_flotte": actif_b.id,
            "type_echeance": "assurance",
            "date_echeance": "2026-12-01",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_list_scoped_and_read_any_role(self):
        EcheanceReglementaire.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            type_echeance="assurance",
            date_echeance=datetime.date(2026, 12, 1))
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
        admin_b = make_user(self.co_b, "er-admin-b", "admin")
        self.assertEqual(rows(auth(admin_b).get(URL)), [])

    def test_filtre_par_type_et_statut(self):
        EcheanceReglementaire.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            type_echeance="assurance", statut="expire",
            date_echeance=datetime.date(2026, 1, 1))
        EcheanceReglementaire.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            type_echeance="vignette", statut="a_jour",
            date_echeance=datetime.date(2027, 1, 1))
        resp = auth(self.admin_a).get(f"{URL}?type=assurance")
        self.assertEqual(len(rows(resp)), 1)
        resp = auth(self.admin_a).get(f"{URL}?statut=expire")
        self.assertEqual(len(rows(resp)), 1)

    def test_filtre_par_actif_flotte(self):
        actif2 = make_actif(self.co_a, "API-2")
        EcheanceReglementaire.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            date_echeance=datetime.date(2026, 12, 1))
        EcheanceReglementaire.objects.create(
            company=self.co_a, actif_flotte=actif2,
            date_echeance=datetime.date(2026, 12, 1))
        resp = auth(self.admin_a).get(f"{URL}?actif_flotte={self.actif.id}")
        self.assertEqual(len(rows(resp)), 1)

    def test_expirantes_action_read_any_role(self):
        # Une expirée et une lointaine.
        EcheanceReglementaire.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            type_echeance="assurance",
            date_echeance=datetime.date(2000, 1, 1))
        EcheanceReglementaire.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            type_echeance="vignette",
            date_echeance=datetime.date(2099, 1, 1))
        resp = auth(self.user_a).get(f"{URL_EXPIRANTES}?within=30")
        self.assertEqual(resp.status_code, 200, resp.data)
        # Seule l'expirée tombe dans la fenêtre (within ne capte pas 2099).
        self.assertEqual(len(rows(resp)), 1)

    def test_expirantes_within_invalide_retombe_30(self):
        EcheanceReglementaire.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            date_echeance=datetime.date(2000, 1, 1))
        resp = auth(self.admin_a).get(f"{URL_EXPIRANTES}?within=abc")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
