"""Tests FLOTTE20 — BaremeVignette + calcul de la vignette / TSAV.

Couvre :
- Modèle ``BaremeVignette`` :
  - validations ``clean`` (CV min > CV max, montant négatif) ;
  - ``couvre_cv`` (appartenance à la tranche) ;
  - unicité ``(company, energie, cv_min, cv_max, annee)``.
- Selector ``calcul_tsav(vehicule, annee=...)`` :
  - choisit la bonne tranche par énergie + CV ;
  - électrique exonéré → montant 0 + ``exonere`` ;
  - aucune tranche → ``montant`` None + note ;
  - CV inconnu → ``montant`` None + note ;
  - paramètre ``annee`` (datée prioritaire, retombe sur générique) threadé.
- Endpoints API :
  - ``/baremes-vignette/`` CRUD scopé société (multi-tenant), role gate,
    filtres ``?energie=`` / ``?annee=`` / ``?actif=`` ;
  - ``/vehicules/{id}/tsav/?annee=`` (lecture tout rôle).
- Commande ``seed_baremes_vignette`` (idempotente, additive).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.management.commands.seed_baremes_vignette import (
    seed_baremes_vignette_for_company,
)
from apps.flotte.models import BaremeVignette, Vehicule
from apps.flotte.selectors import calcul_tsav

User = get_user_model()

URL = "/api/django/flotte/baremes-vignette/"


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


def make_vehicule(company, immat="BV-1", energie="essence", cv=8):
    return Vehicule.objects.create(
        company=company, immatriculation=immat, energie=energie,
        puissance_fiscale=cv)


def make_bareme(company, energie, cv_min, cv_max, montant, annee=0):
    return BaremeVignette.objects.create(
        company=company, energie=energie, cv_min=cv_min, cv_max=cv_max,
        montant=Decimal(str(montant)), annee=annee)


# ── Modèle : validations + couvre_cv + unicité ─────────────────────────────────

class BaremeVignetteModelTests(TestCase):
    def setUp(self):
        self.co = make_company("barvig-model", "Barvig Model")

    def test_creation_simple(self):
        b = make_bareme(self.co, "essence", 8, 10, 650)
        self.assertEqual(b.energie, "essence")
        self.assertEqual(float(b.montant), 650.0)

    def test_cv_min_superieur_max_rejete(self):
        b = BaremeVignette(
            company=self.co, energie="essence", cv_min=12, cv_max=8,
            montant=100)
        with self.assertRaises(ValidationError):
            b.full_clean()

    def test_montant_negatif_rejete(self):
        b = BaremeVignette(
            company=self.co, energie="essence", cv_min=0, cv_max=7,
            montant=-1)
        with self.assertRaises(ValidationError):
            b.full_clean()

    def test_couvre_cv(self):
        b = make_bareme(self.co, "essence", 8, 10, 650)
        self.assertTrue(b.couvre_cv(8))
        self.assertTrue(b.couvre_cv(10))
        self.assertFalse(b.couvre_cv(7))
        self.assertFalse(b.couvre_cv(11))
        self.assertFalse(b.couvre_cv(None))

    def test_unicite_tranche(self):
        make_bareme(self.co, "essence", 8, 10, 650, annee=2026)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_bareme(self.co, "essence", 8, 10, 700, annee=2026)


# ── Selector : calcul_tsav ─────────────────────────────────────────────────────

class CalculTsavTests(TestCase):
    def setUp(self):
        self.co = make_company("barvig-sel", "Barvig Sel")
        # Grille essence générique.
        make_bareme(self.co, "essence", 0, 7, 350)
        make_bareme(self.co, "essence", 8, 10, 650)
        make_bareme(self.co, "essence", 11, 14, 3000)
        make_bareme(self.co, "essence", 15, 9999, 8000)
        # Grille diesel générique.
        make_bareme(self.co, "diesel", 8, 10, 1500)
        # Électrique exonéré.
        make_bareme(self.co, "electrique", 0, 9999, 0)

    def test_picks_bracket_by_energie_et_cv(self):
        veh = make_vehicule(self.co, "ESS-9", "essence", cv=9)
        result = calcul_tsav(veh)
        self.assertEqual(result["montant"], Decimal("650.00"))
        self.assertFalse(result["exonere"])

    def test_picks_high_open_bracket(self):
        veh = make_vehicule(self.co, "ESS-20", "essence", cv=20)
        self.assertEqual(calcul_tsav(veh)["montant"], Decimal("8000.00"))

    def test_diesel_distinct_de_essence(self):
        veh = make_vehicule(self.co, "DIE-9", "diesel", cv=9)
        self.assertEqual(calcul_tsav(veh)["montant"], Decimal("1500.00"))

    def test_electrique_exonere(self):
        veh = make_vehicule(self.co, "ELE-5", "electrique", cv=5)
        result = calcul_tsav(veh)
        self.assertEqual(result["montant"], Decimal("0.00"))
        self.assertTrue(result["exonere"])

    def test_aucune_tranche_retourne_none(self):
        # Hybride : aucune ligne dans le barème de cette société.
        veh = make_vehicule(self.co, "HYB-9", "hybride", cv=9)
        result = calcul_tsav(veh)
        self.assertIsNone(result["montant"])
        self.assertIn("Aucune tranche", result["note"])

    def test_cv_inconnu_retourne_none(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="NOCV", energie="essence",
            puissance_fiscale=None)
        result = calcul_tsav(veh)
        self.assertIsNone(result["montant"])
        self.assertIn("inconnue", result["note"])

    def test_ligne_inactive_ignoree(self):
        # Désactive la tranche 8-10 essence → plus de match pour 9 CV.
        BaremeVignette.objects.filter(
            company=self.co, energie="essence", cv_min=8, cv_max=10
        ).update(actif=False)
        veh = make_vehicule(self.co, "ESS-INACT", "essence", cv=9)
        self.assertIsNone(calcul_tsav(veh)["montant"])

    def test_annee_datee_prioritaire_puis_generique(self):
        # Ligne datée 2026 pour 9 CV essence = 999 ; générique = 650.
        make_bareme(self.co, "essence", 8, 10, 999, annee=2026)
        veh = make_vehicule(self.co, "ESS-AN", "essence", cv=9)
        # annee=2026 → datée.
        self.assertEqual(
            calcul_tsav(veh, annee=2026)["montant"], Decimal("999.00"))
        # annee=2025 (pas de ligne datée) → retombe sur générique.
        self.assertEqual(
            calcul_tsav(veh, annee=2025)["montant"], Decimal("650.00"))

    def test_sans_annee_prend_la_plus_recente(self):
        make_bareme(self.co, "essence", 8, 10, 999, annee=2026)
        veh = make_vehicule(self.co, "ESS-RECENT", "essence", cv=9)
        # Sans annee : la plus récente (2026) l'emporte sur le générique (0).
        self.assertEqual(calcul_tsav(veh)["montant"], Decimal("999.00"))

    def test_scope_societe(self):
        autre = make_company("barvig-sel-b", "Barvig Sel B")
        veh = make_vehicule(autre, "ESS-B", "essence", cv=9)
        # Aucun barème pour `autre` → None malgré la grille de `self.co`.
        self.assertIsNone(calcul_tsav(veh)["montant"])


# ── API : CRUD scopé + role gate + filtres ────────────────────────────────────

class BaremeVignetteApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("barvig-a", "Barvig A")
        self.co_b = make_company("barvig-b", "Barvig B")
        self.admin_a = make_user(self.co_a, "bv-admin-a", "admin")
        self.user_a = make_user(self.co_a, "bv-user-a", "normal")

    def test_create_company_server_side(self):
        resp = auth(self.admin_a).post(URL, {
            "energie": "essence",
            "cv_min": 8,
            "cv_max": 10,
            "montant": "650.00",
            "annee": 2026,
            "company": self.co_b.id,  # injection ignorée.
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        b = BaremeVignette.objects.get()
        self.assertEqual(b.company_id, self.co_a.id)

    def test_create_forbidden_for_normal_role(self):
        resp = auth(self.user_a).post(URL, {
            "energie": "diesel", "cv_min": 0, "cv_max": 7, "montant": "700",
        }, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(BaremeVignette.objects.count(), 0)

    def test_cv_min_superieur_max_refuse(self):
        resp = auth(self.admin_a).post(URL, {
            "energie": "essence", "cv_min": 12, "cv_max": 8, "montant": "100",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_montant_negatif_refuse(self):
        resp = auth(self.admin_a).post(URL, {
            "energie": "essence", "cv_min": 0, "cv_max": 7, "montant": "-1",
        }, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_list_scoped_and_read_any_role(self):
        make_bareme(self.co_a, "essence", 8, 10, 650)
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
        admin_b = make_user(self.co_b, "bv-admin-b", "admin")
        self.assertEqual(rows(auth(admin_b).get(URL)), [])

    def test_filtre_par_energie_annee_actif(self):
        make_bareme(self.co_a, "essence", 8, 10, 650, annee=2026)
        make_bareme(self.co_a, "diesel", 8, 10, 1500, annee=2026)
        b_inact = make_bareme(self.co_a, "essence", 0, 7, 350, annee=2025)
        b_inact.actif = False
        b_inact.save(update_fields=["actif"])

        self.assertEqual(
            len(rows(auth(self.admin_a).get(f"{URL}?energie=essence"))), 2)
        self.assertEqual(
            len(rows(auth(self.admin_a).get(f"{URL}?annee=2026"))), 2)
        self.assertEqual(
            len(rows(auth(self.admin_a).get(f"{URL}?actif=false"))), 1)


# ── API : action vehicules/{id}/tsav/ ─────────────────────────────────────────

class VehiculeTsavActionTests(TestCase):
    def setUp(self):
        self.co = make_company("barvig-tsav", "Barvig Tsav")
        self.admin = make_user(self.co, "tsav-admin", "admin")
        self.user = make_user(self.co, "tsav-user", "normal")
        make_bareme(self.co, "essence", 8, 10, 650)
        make_bareme(self.co, "essence", 8, 10, 999, annee=2026)
        self.veh = make_vehicule(self.co, "TSAV-9", "essence", cv=9)

    def _url(self, suffix=""):
        return f"/api/django/flotte/vehicules/{self.veh.id}/tsav/{suffix}"

    def test_tsav_read_any_role(self):
        resp = auth(self.user).get(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        # Sans annee → la plus récente (2026).
        self.assertEqual(Decimal(str(resp.data["montant"])), Decimal("999.00"))

    def test_tsav_annee_param_threade(self):
        resp = auth(self.admin).get(self._url("?annee=2025"))
        self.assertEqual(resp.status_code, 200, resp.data)
        # 2025 (pas de ligne datée) → générique 650.
        self.assertEqual(Decimal(str(resp.data["montant"])), Decimal("650.00"))

    def test_tsav_annee_invalide_retombe(self):
        resp = auth(self.admin).get(self._url("?annee=abc"))
        self.assertEqual(resp.status_code, 200, resp.data)
        # annee invalide → None → comportement "sans annee" → 999.
        self.assertEqual(Decimal(str(resp.data["montant"])), Decimal("999.00"))


# ── Commande de seed : idempotente + additive ─────────────────────────────────

class SeedBaremesVignetteTests(TestCase):
    def setUp(self):
        self.co = make_company("barvig-seed", "Barvig Seed")

    def test_seed_cree_la_grille_puis_idempotent(self):
        created = seed_baremes_vignette_for_company(self.co)
        self.assertGreater(created, 0)
        total = BaremeVignette.objects.filter(company=self.co).count()
        # Un second passage ne crée rien.
        again = seed_baremes_vignette_for_company(self.co)
        self.assertEqual(again, 0)
        self.assertEqual(
            BaremeVignette.objects.filter(company=self.co).count(), total)

    def test_seed_electrique_exonere(self):
        seed_baremes_vignette_for_company(self.co)
        veh = make_vehicule(self.co, "SEED-ELE", "electrique", cv=4)
        self.assertEqual(calcul_tsav(veh)["montant"], Decimal("0.00"))

    def test_seed_n_ecrase_pas_un_montant_edite(self):
        seed_baremes_vignette_for_company(self.co)
        ligne = BaremeVignette.objects.get(
            company=self.co, energie="essence", cv_min=8, cv_max=10, annee=0)
        ligne.montant = Decimal("777")
        ligne.save(update_fields=["montant"])
        # Re-seed laisse le montant édité intact.
        seed_baremes_vignette_for_company(self.co)
        ligne.refresh_from_db()
        self.assertEqual(ligne.montant, Decimal("777.00"))
