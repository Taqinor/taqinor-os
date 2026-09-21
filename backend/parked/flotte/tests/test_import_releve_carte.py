"""Tests XFLT6 — Import relevé carte carburant / Jawaz (CSV) + rapprochement.

Couvre :
- Service ``importer_releve_carte(carte, contenu_csv)`` :
  - lignes avec litres → PleinCarburant ; sans litres → CoutVehicule (péage,
    tag Jawaz) ;
  - import idempotent (ré-import = 0 création, tout en doublon) ;
  - carte sans véhicule attribué → non rapprochées, rien créé ;
  - lignes invalides (date/montant) → erreurs, pas de crash.
- Endpoint API ``POST /cartes/<id>/importer-releve/`` :
  - import CSV via fichier (multipart), rapport JSON, écriture
    responsable/admin.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    CarteCarburant,
    CoutVehicule,
    PleinCarburant,
    Vehicule,
)
from apps.flotte.services import importer_releve_carte

User = get_user_model()


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


CSV_MIXTE = (
    "date,montant,litres,station\n"
    "2026-06-01,440,40,Afriquia Casa\n"
    "2026-06-02,45,,Peage Jawaz A1\n"
)


class ImporterReleveCarteServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("imp-svc", "Imp Svc")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="IMP1", energie="diesel")
        ActifFlotte.objects.create(company=self.co, vehicule=self.veh)
        self.carte = CarteCarburant.objects.create(
            company=self.co, vehicule=self.veh, numero="CARD-1")

    def test_lignes_avec_et_sans_litres(self):
        rapport = importer_releve_carte(self.carte, CSV_MIXTE)
        self.assertEqual(rapport['crees'], 2)
        self.assertEqual(PleinCarburant.objects.count(), 1)
        self.assertEqual(CoutVehicule.objects.count(), 1)
        cout = CoutVehicule.objects.get()
        self.assertEqual(cout.categorie, 'peage')
        self.assertEqual(cout.reference_piece, 'Jawaz')

    def test_reimport_idempotent(self):
        r1 = importer_releve_carte(self.carte, CSV_MIXTE)
        r2 = importer_releve_carte(self.carte, CSV_MIXTE)
        self.assertEqual(r1['crees'], 2)
        self.assertEqual(r2['crees'], 0)
        self.assertEqual(r2['doublons'], 2)
        self.assertEqual(PleinCarburant.objects.count(), 1)
        self.assertEqual(CoutVehicule.objects.count(), 1)

    def test_carte_sans_vehicule_non_rapprochee(self):
        carte_orpheline = CarteCarburant.objects.create(
            company=self.co, numero="CARD-ORPHAN")
        rapport = importer_releve_carte(carte_orpheline, CSV_MIXTE)
        self.assertEqual(rapport['crees'], 0)
        self.assertEqual(rapport['non_rapprochees'], 2)

    def test_ligne_invalide_signale_erreur(self):
        csv_invalide = "date,montant,litres,station\n,abc,,X\n"
        rapport = importer_releve_carte(self.carte, csv_invalide)
        self.assertEqual(len(rapport['erreurs']), 1)
        self.assertEqual(rapport['crees'], 0)

    def test_plein_cree_avec_bons_champs(self):
        importer_releve_carte(self.carte, CSV_MIXTE)
        plein = PleinCarburant.objects.get()
        self.assertEqual(plein.vehicule_id, self.veh.id)
        self.assertEqual(plein.date_plein, datetime.date(2026, 6, 1))
        self.assertEqual(float(plein.prix_total), 440.0)
        self.assertEqual(float(plein.quantite), 40.0)


class ImporterReleveApiTests(TestCase):
    def setUp(self):
        self.co = make_company("imp-api", "Imp Api")
        self.admin = make_user(self.co, "imp-admin", "admin")
        self.user_normal = make_user(self.co, "imp-user", "normal")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="IMPAPI", energie="diesel")
        ActifFlotte.objects.create(company=self.co, vehicule=self.veh)
        self.carte = CarteCarburant.objects.create(
            company=self.co, vehicule=self.veh, numero="CARD-API")

    def test_import_multipart_ok(self):
        fichier = SimpleUploadedFile(
            "releve.csv", CSV_MIXTE.encode('utf-8'), content_type="text/csv")
        resp = auth(self.admin).post(
            f"/api/django/flotte/cartes/{self.carte.id}/importer-releve/",
            {"fichier": fichier}, format="multipart")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['crees'], 2)

    def test_import_forbidden_normal_role(self):
        fichier = SimpleUploadedFile(
            "releve.csv", CSV_MIXTE.encode('utf-8'), content_type="text/csv")
        resp = auth(self.user_normal).post(
            f"/api/django/flotte/cartes/{self.carte.id}/importer-releve/",
            {"fichier": fichier}, format="multipart")
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_import_sans_fichier_400(self):
        resp = auth(self.admin).post(
            f"/api/django/flotte/cartes/{self.carte.id}/importer-releve/",
            {}, format="multipart")
        self.assertEqual(resp.status_code, 400, resp.data)
