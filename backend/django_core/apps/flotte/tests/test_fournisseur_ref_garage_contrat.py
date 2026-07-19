"""Tests WIR90 — liens optionnels vers stock.Fournisseur (Garage, ContratVehicule).

Même pattern que ``CoutVehicule.fournisseur_id_ref`` : id NUMÉRIQUE référencé
(jamais un FK cross-app dur), repli sur la saisie libre, validation « même
société » côté modèle (``clean``) ET serializer, résolution en lecture
(``fournisseur_label``) via le sélecteur cross-app ``apps.stock``.

Couvre pour CHAQUE modèle :
- fournisseur de la MÊME société accepté (modèle + endpoint) et résolu en
  ``fournisseur_label`` ;
- fournisseur d'une AUTRE société rejeté (modèle full_clean + endpoint 400) ;
- absence de lien (repli saisie libre) toujours acceptée.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ContratVehicule, Garage, Vehicule
from apps.stock.models import Fournisseur

User = get_user_model()

GARAGE_URL = "/api/django/flotte/garages/"
CONTRAT_URL = "/api/django/flotte/contrats-vehicule/"


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


# ── Garage.fournisseur_id_ref ────────────────────────────────────────────────

class GarageFournisseurRefTests(TestCase):
    def setUp(self):
        self.co = make_company("wir90-garage", "WIR90 Garage")
        self.admin = make_user(self.co, "wir90-garage-admin")
        self.fournisseur = Fournisseur.objects.create(
            company=self.co, nom="Garage Fournisseur SARL")

    def test_sans_lien_repli_saisie_libre(self):
        garage = Garage(company=self.co, nom="Garage ponctuel")
        garage.full_clean()  # ne lève pas — fournisseur_id_ref optionnel.

    def test_fournisseur_meme_societe_accepte(self):
        garage = Garage(
            company=self.co, nom="Garage lié",
            fournisseur_id_ref=self.fournisseur.id)
        garage.full_clean()  # ne lève pas.

    def test_fournisseur_autre_societe_rejete(self):
        autre = make_company("wir90-garage-b", "WIR90 Garage B")
        fournisseur_autre = Fournisseur.objects.create(
            company=autre, nom="Autre Fournisseur")
        garage = Garage(
            company=self.co, nom="Garage mal lié",
            fournisseur_id_ref=fournisseur_autre.id)
        with self.assertRaises(ValidationError):
            garage.full_clean()

    def test_endpoint_fournisseur_resolu_en_lecture(self):
        resp = auth(self.admin).post(GARAGE_URL, {
            "nom": "Garage API", "fournisseur_id_ref": self.fournisseur.id,
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["fournisseur_label"], "Garage Fournisseur SARL")

    def test_endpoint_fournisseur_autre_societe_400(self):
        autre = make_company("wir90-garage-c", "WIR90 Garage C")
        fournisseur_autre = Fournisseur.objects.create(
            company=autre, nom="Fournisseur Externe")
        resp = auth(self.admin).post(GARAGE_URL, {
            "nom": "Garage API 2", "fournisseur_id_ref": fournisseur_autre.id,
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("fournisseur_id_ref", resp.data)


# ── ContratVehicule.fournisseur_id_ref ───────────────────────────────────────

class ContratVehiculeFournisseurRefTests(TestCase):
    def setUp(self):
        self.co = make_company("wir90-contrat", "WIR90 Contrat")
        self.admin = make_user(self.co, "wir90-contrat-admin")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="WIR90-1", energie="diesel")
        self.fournisseur = Fournisseur.objects.create(
            company=self.co, nom="Bailleur Leasing SARL")

    def test_sans_lien_repli_saisie_libre(self):
        ctr = ContratVehicule(
            company=self.co, vehicule=self.veh, type_contrat="leasing",
            fournisseur="Wafasalaf", date_debut=datetime.date(2026, 1, 1))
        ctr.full_clean()  # ne lève pas.

    def test_fournisseur_meme_societe_accepte(self):
        ctr = ContratVehicule(
            company=self.co, vehicule=self.veh, type_contrat="leasing",
            date_debut=datetime.date(2026, 1, 1),
            fournisseur_id_ref=self.fournisseur.id)
        ctr.full_clean()  # ne lève pas.

    def test_fournisseur_autre_societe_rejete(self):
        autre = make_company("wir90-contrat-b", "WIR90 Contrat B")
        fournisseur_autre = Fournisseur.objects.create(
            company=autre, nom="Autre Bailleur")
        ctr = ContratVehicule(
            company=self.co, vehicule=self.veh, type_contrat="leasing",
            date_debut=datetime.date(2026, 1, 1),
            fournisseur_id_ref=fournisseur_autre.id)
        with self.assertRaises(ValidationError):
            ctr.full_clean()

    def test_endpoint_fournisseur_resolu_en_lecture(self):
        resp = auth(self.admin).post(CONTRAT_URL, {
            "vehicule": self.veh.id, "type_contrat": "leasing",
            "date_debut": "2026-01-01",
            "fournisseur_id_ref": self.fournisseur.id,
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["fournisseur_label"], "Bailleur Leasing SARL")

    def test_endpoint_fournisseur_autre_societe_400(self):
        autre = make_company("wir90-contrat-c", "WIR90 Contrat C")
        fournisseur_autre = Fournisseur.objects.create(
            company=autre, nom="Bailleur Externe")
        resp = auth(self.admin).post(CONTRAT_URL, {
            "vehicule": self.veh.id, "type_contrat": "leasing",
            "date_debut": "2026-01-01",
            "fournisseur_id_ref": fournisseur_autre.id,
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("fournisseur_id_ref", resp.data)
