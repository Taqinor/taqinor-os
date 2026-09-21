"""Tests FLOTTE9 — Contrôle « permis valide / catégorie » à l'affectation.

Couvre :
- Service ``controle_permis`` (unité) : permis valide, manquant, expiré,
  catégorie inadaptée, catégorie multiple, véhicule sans exigence.
- API d'affectation : un conducteur au permis valide de la bonne catégorie
  passe (201) ; permis expiré / catégorie inadaptée / permis manquant → 400 ;
  ``force=True`` dégrade le rejet en soft-warn (201 + ``permis_avertissement``).
- Isolation multi-tenant préservée.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import Conducteur, Vehicule
from apps.flotte.services import controle_permis, normaliser_categorie_permis

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


def make_vehicule(company, immat="1234-A-00", categorie_requise=""):
    return Vehicule.objects.create(
        company=company,
        immatriculation=immat,
        energie="diesel",
        categorie_permis_requise=categorie_requise,
    )


def make_conducteur(company, nom="Conducteur Test", numero="P-1",
                    categorie="B", date_expiration=None):
    return Conducteur.objects.create(
        company=company,
        nom=nom,
        numero_permis=numero,
        categorie_permis=categorie,
        date_expiration=date_expiration,
    )


# ── Service (unité) ───────────────────────────────────────────────────────────

class ControlePermisServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("perm-svc", "Perm Svc")
        self.today = datetime.date.today()

    def test_normaliser_categorie(self):
        self.assertEqual(normaliser_categorie_permis(" ce "), "CE")
        self.assertEqual(normaliser_categorie_permis(""), "")
        self.assertEqual(normaliser_categorie_permis(None), "")

    def test_permis_valide_bonne_categorie(self):
        cond = make_conducteur(self.co, categorie="C",
                               date_expiration=self.today
                               + datetime.timedelta(days=365))
        veh = make_vehicule(self.co, "1111-A-11", categorie_requise="C")
        ok, code, _msg = controle_permis(cond, veh)
        self.assertTrue(ok)
        self.assertEqual(code, "")

    def test_vehicule_sans_exigence_passe(self):
        """Véhicule sans catégorie requise → tout permis valide passe."""
        cond = make_conducteur(self.co, categorie="B")
        veh = make_vehicule(self.co, "2222-A-22", categorie_requise="")
        ok, _code, _msg = controle_permis(cond, veh)
        self.assertTrue(ok)

    def test_permis_manquant(self):
        cond = make_conducteur(self.co, numero="", categorie="")
        veh = make_vehicule(self.co, "3333-A-33", categorie_requise="B")
        ok, code, _msg = controle_permis(cond, veh)
        self.assertFalse(ok)
        self.assertEqual(code, "permis_manquant")

    def test_permis_expire(self):
        cond = make_conducteur(
            self.co, categorie="C",
            date_expiration=self.today - datetime.timedelta(days=1))
        veh = make_vehicule(self.co, "4444-A-44", categorie_requise="C")
        ok, code, _msg = controle_permis(cond, veh)
        self.assertFalse(ok)
        self.assertEqual(code, "permis_expire")

    def test_permis_expire_aujourdhui_valide(self):
        """Permis expirant aujourd'hui même → encore valide (>= today)."""
        cond = make_conducteur(self.co, categorie="C",
                               date_expiration=self.today)
        veh = make_vehicule(self.co, "4445-A-44", categorie_requise="C")
        ok, _code, _msg = controle_permis(cond, veh)
        self.assertTrue(ok)

    def test_categorie_inadaptee(self):
        cond = make_conducteur(self.co, categorie="B")
        veh = make_vehicule(self.co, "5555-A-55", categorie_requise="CE")
        ok, code, _msg = controle_permis(cond, veh)
        self.assertFalse(ok)
        self.assertEqual(code, "categorie_inadaptee")

    def test_categorie_multiple_couvre(self):
        """Permis multi-catégories « B, CE » couvre la catégorie requise CE."""
        cond = make_conducteur(self.co, categorie="B, CE")
        veh = make_vehicule(self.co, "6666-A-66", categorie_requise="CE")
        ok, _code, _msg = controle_permis(cond, veh)
        self.assertTrue(ok)

    def test_categorie_insensible_casse_espaces(self):
        cond = make_conducteur(self.co, categorie=" ce ")
        veh = make_vehicule(self.co, "7777-A-77", categorie_requise="CE")
        ok, _code, _msg = controle_permis(cond, veh)
        self.assertTrue(ok)

    def test_permis_sans_expiration_passe(self):
        """date_expiration nulle → on ne bloque pas sur la validité."""
        cond = make_conducteur(self.co, categorie="C", date_expiration=None)
        veh = make_vehicule(self.co, "8888-A-88", categorie_requise="C")
        ok, _code, _msg = controle_permis(cond, veh)
        self.assertTrue(ok)


# ── API ───────────────────────────────────────────────────────────────────────

class ControlePermisApiTests(TestCase):
    def setUp(self):
        self.co = make_company("perm-api", "Perm API")
        self.admin = make_user(self.co, "perm-admin", "admin")
        self.today = datetime.date.today().isoformat()

    def _post(self, conducteur, vehicule, **extra):
        body = {
            "conducteur": conducteur.id,
            "vehicule": vehicule.id,
            "date_debut": self.today,
        }
        body.update(extra)
        return auth(self.admin).post(URL, body, format="json")

    def test_affectation_permis_valide_ok(self):
        cond = make_conducteur(self.co, categorie="C")
        veh = make_vehicule(self.co, "1234-A-01", categorie_requise="C")
        resp = self._post(cond, veh)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data["permis_avertissement"])

    def test_affectation_vehicule_sans_exigence_ok(self):
        cond = make_conducteur(self.co, categorie="B")
        veh = make_vehicule(self.co, "1234-A-02", categorie_requise="")
        resp = self._post(cond, veh)
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_affectation_permis_expire_rejetee(self):
        cond = make_conducteur(
            self.co, categorie="C",
            date_expiration=datetime.date.today()
            - datetime.timedelta(days=1))
        veh = make_vehicule(self.co, "1234-A-03", categorie_requise="C")
        resp = self._post(cond, veh)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("conducteur", resp.data)

    def test_affectation_categorie_inadaptee_rejetee(self):
        cond = make_conducteur(self.co, categorie="B")
        veh = make_vehicule(self.co, "1234-A-04", categorie_requise="CE")
        resp = self._post(cond, veh)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("conducteur", resp.data)

    def test_affectation_permis_manquant_rejetee(self):
        cond = make_conducteur(self.co, numero="", categorie="")
        veh = make_vehicule(self.co, "1234-A-05", categorie_requise="B")
        resp = self._post(cond, veh)
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_force_degrade_en_soft_warn(self):
        """force=True : l'affectation non-conforme est créée + avertissement."""
        cond = make_conducteur(self.co, categorie="B")
        veh = make_vehicule(self.co, "1234-A-06", categorie_requise="CE")
        resp = self._post(cond, veh, force=True)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNotNone(resp.data["permis_avertissement"])
        self.assertIn("catégorie", resp.data["permis_avertissement"].lower())

    def test_force_permis_expire_soft_warn(self):
        cond = make_conducteur(
            self.co, categorie="C",
            date_expiration=datetime.date.today()
            - datetime.timedelta(days=5))
        veh = make_vehicule(self.co, "1234-A-07", categorie_requise="C")
        resp = self._post(cond, veh, force=True)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNotNone(resp.data["permis_avertissement"])

    def test_force_inutile_quand_conforme(self):
        """force=True sur une affectation conforme → pas d'avertissement."""
        cond = make_conducteur(self.co, categorie="C")
        veh = make_vehicule(self.co, "1234-A-08", categorie_requise="C")
        resp = self._post(cond, veh, force=True)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data["permis_avertissement"])
