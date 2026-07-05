"""Tests XFLT26 — ICE/IF fournisseurs flotte (préparation e-facturation DGI).

Couvre :
- Champs additifs ``Garage.ice``/``identifiant_fiscal`` :
  - ICE valide (15 chiffres) accepté ;
  - ICE invalide (mauvaise longueur / non numérique) rejeté (message FR),
    modèle ET serializer.
- ``CoutVehicule.fournisseur_id_ref`` (lien optionnel vers ``stock.Fournisseur``) :
  - fournisseur de la MÊME société accepté, résolu en lecture
    (``fournisseur_label``) via le sélecteur cross-app ;
  - fournisseur d'une AUTRE société rejeté.
- Avertissement (non bloquant) sur coût élevé sans référence de facture :
  - coût > 5 000 MAD sans ``reference_piece`` -> ``reference_avertissement``
    non nul ;
  - coût <= 5 000 MAD ou avec référence -> ``reference_avertissement`` nul.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ActifFlotte, CoutVehicule, Garage, Vehicule
from apps.stock.models import Fournisseur

User = get_user_model()

GARAGE_URL = "/api/django/flotte/garages/"
COUT_URL = "/api/django/flotte/couts/"


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


def make_actif(company, immat="ICE-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


# ── Modèle Garage : ICE ─────────────────────────────────────────────────────────

class GarageIceModelTests(TestCase):
    def setUp(self):
        self.co = make_company("ice-model", "ICE Model")

    def test_ice_valide_accepte(self):
        garage = Garage(
            company=self.co, nom="Garage A", ice="001234567000012")
        garage.full_clean()  # ne lève pas.

    def test_ice_longueur_invalide_rejete(self):
        garage = Garage(company=self.co, nom="Garage B", ice="12345")
        with self.assertRaises(ValidationError):
            garage.full_clean()

    def test_ice_non_numerique_rejete(self):
        garage = Garage(
            company=self.co, nom="Garage C", ice="ABCDEFGHIJKLMNO")
        with self.assertRaises(ValidationError):
            garage.full_clean()

    def test_ice_vide_accepte(self):
        garage = Garage(company=self.co, nom="Garage D", ice="")
        garage.full_clean()  # optionnel, ne lève pas.


# ── Endpoint Garage : ICE ────────────────────────────────────────────────────────

class GarageIceApiTests(TestCase):
    def setUp(self):
        self.co = make_company("ice-api", "ICE Api")
        self.admin = make_user(self.co, "ice-admin")

    def test_creation_ice_valide(self):
        resp = auth(self.admin).post(GARAGE_URL, {
            "nom": "Garage E", "ice": "001234567000012",
            "identifiant_fiscal": "12345678",
        })
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_creation_ice_invalide_400(self):
        resp = auth(self.admin).post(GARAGE_URL, {
            "nom": "Garage F", "ice": "123",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("ice", resp.data)


# ── CoutVehicule : lien fournisseur référentiel + avertissement référence ──────

class CoutVehiculeFournisseurRefTests(TestCase):
    def setUp(self):
        self.co = make_company("ice-cout", "ICE Cout")
        self.actif = make_actif(self.co)
        self.fournisseur = Fournisseur.objects.create(
            company=self.co, nom="Fournisseur Flotte SARL")

    def test_fournisseur_meme_societe_accepte(self):
        cout = CoutVehicule(
            company=self.co, actif_flotte=self.actif,
            categorie=CoutVehicule.Categorie.ENTRETIEN,
            date=datetime.date(2026, 6, 1), montant=1000,
            fournisseur_id_ref=self.fournisseur.id)
        cout.full_clean()  # ne lève pas.

    def test_fournisseur_autre_societe_rejete(self):
        autre = make_company("ice-cout-b", "ICE Cout B")
        fournisseur_autre = Fournisseur.objects.create(
            company=autre, nom="Autre Fournisseur")
        cout = CoutVehicule(
            company=self.co, actif_flotte=self.actif,
            categorie=CoutVehicule.Categorie.ENTRETIEN,
            date=datetime.date(2026, 6, 1), montant=1000,
            fournisseur_id_ref=fournisseur_autre.id)
        with self.assertRaises(ValidationError):
            cout.full_clean()


class CoutVehiculeAvertissementApiTests(TestCase):
    def setUp(self):
        self.co = make_company("ice-warn", "ICE Warn")
        self.admin = make_user(self.co, "ice-warn-admin")
        self.actif = make_actif(self.co, "WARN-1")

    def test_cout_eleve_sans_reference_avertissement(self):
        resp = auth(self.admin).post(COUT_URL, {
            "actif_flotte": self.actif.id, "categorie": "entretien",
            "date": "2026-06-01", "montant": "12000",
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNotNone(resp.data["reference_avertissement"])
        self.assertIn("MAD", resp.data["reference_avertissement"])

    def test_cout_eleve_avec_reference_pas_avertissement(self):
        resp = auth(self.admin).post(COUT_URL, {
            "actif_flotte": self.actif.id, "categorie": "entretien",
            "date": "2026-06-01", "montant": "12000",
            "reference_piece": "FAC-2026-001",
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data["reference_avertissement"])

    def test_cout_bas_sans_reference_pas_avertissement(self):
        resp = auth(self.admin).post(COUT_URL, {
            "actif_flotte": self.actif.id, "categorie": "peage",
            "date": "2026-06-01", "montant": "50",
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data["reference_avertissement"])

    def test_fournisseur_ref_resolu_en_lecture(self):
        fournisseur = Fournisseur.objects.create(
            company=self.co, nom="Garage Central")
        resp = auth(self.admin).post(COUT_URL, {
            "actif_flotte": self.actif.id, "categorie": "entretien",
            "date": "2026-06-01", "montant": "500",
            "fournisseur_id_ref": fournisseur.id,
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["fournisseur_label"], "Garage Central")

    def test_fournisseur_ref_autre_societe_400(self):
        autre = make_company("ice-warn-b", "ICE Warn B")
        fournisseur_autre = Fournisseur.objects.create(
            company=autre, nom="Fournisseur Externe")
        resp = auth(self.admin).post(COUT_URL, {
            "actif_flotte": self.actif.id, "categorie": "entretien",
            "date": "2026-06-01", "montant": "500",
            "fournisseur_id_ref": fournisseur_autre.id,
        })
        self.assertEqual(resp.status_code, 400)
