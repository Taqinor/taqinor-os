"""Tests XFLT5 — Signalement d'anomalie véhicule par le conducteur.

Couvre :
- Modèle ``SignalementVehicule`` : validations ``clean`` (société de
  l'actif/conducteur/auteur).
- Endpoints API ``/signalements/`` :
  - création avec photo, tout rôle (company + auteur posés serveur) ;
  - filtres ``?statut=`` / ``?actif_flotte=`` ;
  - isolation tenant (scope société) ;
  - action ``convertir-en-or/`` (1 clic, responsable/admin) → OrdreReparation
    pré-rempli et lié ; refus si déjà converti.
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
    OrdreReparation,
    SignalementVehicule,
    Vehicule,
)

User = get_user_model()

URL = "/api/django/flotte/signalements/"


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


def make_actif(company, immat="SIG-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


class SignalementVehiculeModelTests(TestCase):
    def setUp(self):
        self.co = make_company("sig-model", "Sig Model")
        self.actif = make_actif(self.co, "SMOD")

    def test_actif_autre_societe_rejete(self):
        autre = make_company("sig-model-b", "Sig Model B")
        actif_b = make_actif(autre, "B")
        sig = SignalementVehicule(
            company=self.co, actif_flotte=actif_b, description="Fuite")
        with self.assertRaises(ValidationError):
            sig.full_clean()


class SignalementVehiculeApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("sig-a", "Sig A")
        self.co_b = make_company("sig-b", "Sig B")
        self.admin_a = make_user(self.co_a, "sig-admin-a", "admin")
        self.user_a = make_user(self.co_a, "sig-user-a", "normal")
        self.actif = make_actif(self.co_a, "API")

    def test_create_avec_photo_tout_role(self):
        photo = SimpleUploadedFile(
            "anomalie.jpg", b"fake-image-bytes", content_type="image/jpeg")
        resp = auth(self.user_a).post(URL, {
            "actif_flotte": self.actif.id,
            "description": "Bruit moteur suspect",
            "gravite": "critique",
            "photo": photo,
            "company": self.co_b.id,  # injection ignorée.
        }, format="multipart")
        self.assertEqual(resp.status_code, 201, resp.data)
        sig = SignalementVehicule.objects.get()
        self.assertEqual(sig.company_id, self.co_a.id)
        self.assertEqual(sig.auteur_id, self.user_a.id)
        self.assertTrue(sig.photo)

    def test_scope_societe(self):
        SignalementVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            description="Test", auteur=self.user_a)
        admin_b = make_user(self.co_b, "sig-admin-b", "admin")
        resp = auth(admin_b).get(URL)
        self.assertEqual(rows(resp), [])

    def test_filtre_statut_et_actif(self):
        SignalementVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif, description="A",
            statut="ouvert", auteur=self.user_a)
        SignalementVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif, description="B",
            statut="resolu", auteur=self.user_a)
        resp = auth(self.admin_a).get(f"{URL}?statut=ouvert")
        self.assertEqual(len(rows(resp)), 1)

    def test_convertir_en_or_1_clic(self):
        sig = SignalementVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            description="Fuite hydraulique", auteur=self.user_a)
        resp = auth(self.admin_a).post(f"{URL}{sig.id}/convertir-en-or/")
        self.assertEqual(resp.status_code, 200, resp.data)
        sig.refresh_from_db()
        self.assertIsNotNone(sig.ordre_reparation_id)
        ordre = OrdreReparation.objects.get(id=sig.ordre_reparation_id)
        self.assertEqual(ordre.actif_flotte_id, self.actif.id)
        self.assertEqual(ordre.description, "Fuite hydraulique")
        self.assertEqual(ordre.date_ouverture, datetime.date.today())

    def test_convertir_en_or_forbidden_normal_role(self):
        sig = SignalementVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            description="Test", auteur=self.user_a)
        resp = auth(self.user_a).post(f"{URL}{sig.id}/convertir-en-or/")
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_convertir_en_or_deja_converti_refuse(self):
        sig = SignalementVehicule.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            description="Test", auteur=self.user_a)
        auth(self.admin_a).post(f"{URL}{sig.id}/convertir-en-or/")
        resp = auth(self.admin_a).post(f"{URL}{sig.id}/convertir-en-or/")
        self.assertEqual(resp.status_code, 400, resp.data)
