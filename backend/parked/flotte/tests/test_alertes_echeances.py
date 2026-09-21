"""Tests FLOTTE24 — Moteur d'alertes d'échéances réglementaires (J-30/15/7/échu).

Couvre :
- Helper ``_bucket_pour_jours`` : seau correct par jours restants (échu / j7 /
  j15 / j30 / hors fenêtre).
- Selector ``alertes_echeances_reglementaires(company, today=...)`` :
  - un item à J-5 tombe dans le seau ``j7`` ; un à J-25 dans ``j30`` ; un déjà
    passé dans ``echu`` ; un hors fenêtre (> 30 j) est EXCLU ;
  - agrégation de PLUSIEURS modèles sources (échéance réglementaire, assurance,
    visite technique, carte grise, entretien daté) ;
  - isolation multi-société (la société B ne voit rien de A) ;
  - date INJECTABLE (``today``) ;
  - tri du plus urgent au moins urgent (échu d'abord, par date croissante).
- Endpoint API ``GET /echeances-reglementaires/alertes-echeances/`` :
  - scope société + lecture tout rôle.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    AssuranceVehicule,
    CarteGriseVehicule,
    EcheanceEntretien,
    EcheanceReglementaire,
    PlanEntretien,
    Vehicule,
    VisiteTechnique,
)
from apps.flotte.selectors import (
    _bucket_pour_jours,
    alertes_echeances_reglementaires,
)

User = get_user_model()

URL_ALERTES = (
    "/api/django/flotte/echeances-reglementaires/alertes-echeances/"
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


def make_actif(company, immat="AL-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


# ── Helper de seau ──────────────────────────────────────────────────────────────

class BucketHelperTests(TestCase):
    def test_echu_si_passe(self):
        self.assertEqual(_bucket_pour_jours(-1), "echu")
        self.assertEqual(_bucket_pour_jours(-100), "echu")

    def test_j7(self):
        self.assertEqual(_bucket_pour_jours(0), "j7")
        self.assertEqual(_bucket_pour_jours(5), "j7")
        self.assertEqual(_bucket_pour_jours(7), "j7")

    def test_j15(self):
        self.assertEqual(_bucket_pour_jours(8), "j15")
        self.assertEqual(_bucket_pour_jours(15), "j15")

    def test_j30(self):
        self.assertEqual(_bucket_pour_jours(16), "j30")
        self.assertEqual(_bucket_pour_jours(25), "j30")
        self.assertEqual(_bucket_pour_jours(30), "j30")

    def test_hors_fenetre(self):
        self.assertIsNone(_bucket_pour_jours(31))
        self.assertIsNone(_bucket_pour_jours(365))
        self.assertIsNone(_bucket_pour_jours(None))


# ── Selector : buckets + fenêtre + tri (date injectable) ────────────────────────

class AlertesBucketsTests(TestCase):
    def setUp(self):
        self.co = make_company("alertes-bk", "Alertes BK")
        self.actif = make_actif(self.co, "ABK")
        self.today = datetime.date(2026, 6, 15)

    def test_j5_tombe_dans_j7(self):
        EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_echeance="assurance",
            date_echeance=self.today + datetime.timedelta(days=5))
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        self.assertEqual(result["nb_total"], 1)
        self.assertEqual(result["nb_j7"], 1)
        self.assertEqual(result["alertes"][0]["bucket"], "j7")
        self.assertEqual(result["alertes"][0]["jours_restants"], 5)

    def test_j25_tombe_dans_j30(self):
        EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_echeance="vignette",
            date_echeance=self.today + datetime.timedelta(days=25))
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        self.assertEqual(result["nb_j30"], 1)
        self.assertEqual(result["alertes"][0]["bucket"], "j30")

    def test_passe_tombe_dans_echu(self):
        EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_echeance="visite_technique",
            date_echeance=self.today - datetime.timedelta(days=3))
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        self.assertEqual(result["nb_echu"], 1)
        self.assertEqual(result["alertes"][0]["bucket"], "echu")
        self.assertEqual(result["buckets"]["echu"][0]["jours_restants"], -3)

    def test_hors_fenetre_exclu(self):
        # À 31 jours → au-delà de l'horizon de 30 j : exclu.
        EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_echeance="autre",
            date_echeance=self.today + datetime.timedelta(days=31))
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        self.assertEqual(result["nb_total"], 0)

    def test_tri_echu_dabord_puis_par_date(self):
        # Échu (-3 j), J-25, J-5 → l'échu remonte en tête, puis par date.
        EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif, type_echeance="vignette",
            date_echeance=self.today + datetime.timedelta(days=25))
        EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif, type_echeance="assurance",
            date_echeance=self.today - datetime.timedelta(days=3))
        EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_echeance="visite_technique",
            date_echeance=self.today + datetime.timedelta(days=5))
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        buckets = [a["bucket"] for a in result["alertes"]]
        self.assertEqual(buckets, ["echu", "j7", "j30"])


# ── Selector : agrégation multi-modèles ────────────────────────────────────────

class AlertesAgregationTests(TestCase):
    def setUp(self):
        self.co = make_company("alertes-agg", "Alertes AGG")
        self.actif = make_actif(self.co, "AGG")
        self.today = datetime.date(2026, 6, 15)
        within = datetime.timedelta(days=10)  # tous imminents.

        self.ech = EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif, type_echeance="taxe_essieu",
            date_echeance=self.today + within)
        self.assur = AssuranceVehicule.objects.create(
            company=self.co, actif_flotte=self.actif, assureur="Wafa",
            numero_police="P-1", date_echeance=self.today + within)
        self.vt = VisiteTechnique.objects.create(
            company=self.co, actif_flotte=self.actif, centre="VT Casa",
            date_visite=self.today - datetime.timedelta(days=350),
            date_prochaine=self.today + within)
        self.cg = CarteGriseVehicule.objects.create(
            company=self.co, actif_flotte=self.actif,
            numero_carte_grise="CG-1",
            autorisation_date_validite=self.today + within)
        # Échéance d'entretien OUVERTE datée (FLOTTE16).
        plan = PlanEntretien.objects.create(
            company=self.co, actif_flotte=self.actif, type_entretien="vidange",
            intervalle_jours=180)
        self.ee = EcheanceEntretien.objects.create(
            company=self.co, plan=plan, actif_flotte=self.actif,
            type_entretien="vidange", due_le=self.today + within,
            statut=EcheanceEntretien.Statut.A_FAIRE)

    def test_les_cinq_sources_agregees(self):
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        sources = {a["source"] for a in result["alertes"]}
        self.assertEqual(sources, {
            "echeance_reglementaire", "assurance", "visite_technique",
            "carte_grise", "entretien"})
        self.assertEqual(result["nb_total"], 5)

    def test_entretien_clos_exclu(self):
        # Une échéance d'entretien FAITE ne doit pas alerter.
        self.ee.statut = EcheanceEntretien.Statut.FAIT
        self.ee.save()
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        sources = [a["source"] for a in result["alertes"]]
        self.assertNotIn("entretien", sources)
        self.assertEqual(result["nb_total"], 4)

    def test_scope_societe(self):
        autre = make_company("alertes-agg-b", "Alertes AGG B")
        actif_b = make_actif(autre, "B")
        EcheanceReglementaire.objects.create(
            company=autre, actif_flotte=actif_b,
            date_echeance=self.today + datetime.timedelta(days=5))
        result = alertes_echeances_reglementaires(autre, today=self.today)
        self.assertEqual(result["nb_total"], 1)

    def test_date_injectable(self):
        # Bien plus tôt : tout est hors fenêtre (échéances à > 30 j).
        early = self.today - datetime.timedelta(days=60)
        result = alertes_echeances_reglementaires(self.co, today=early)
        self.assertEqual(result["nb_total"], 0)


# ── API : scope + lecture tout rôle ────────────────────────────────────────────

class AlertesApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("alertes-a", "Alertes A")
        self.co_b = make_company("alertes-b", "Alertes B")
        self.user_a = make_user(self.co_a, "al-user-a", "normal")
        self.actif = make_actif(self.co_a, "API")

    def test_alertes_lecture_tout_role_scope(self):
        EcheanceReglementaire.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            type_echeance="assurance",
            date_echeance=datetime.date(2000, 1, 1))  # échu, toujours dans fenêtre.
        resp = auth(self.user_a).get(URL_ALERTES)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["nb_total"], 1)
        self.assertEqual(resp.data["nb_echu"], 1)
        self.assertIn("buckets", resp.data)

        admin_b = make_user(self.co_b, "al-admin-b", "admin")
        resp_b = auth(admin_b).get(URL_ALERTES)
        self.assertEqual(resp_b.status_code, 200, resp_b.data)
        self.assertEqual(resp_b.data["nb_total"], 0)
