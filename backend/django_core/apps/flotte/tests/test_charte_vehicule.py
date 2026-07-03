"""Tests XFLT17 — Charte véhicule + signatures sur l'état des lieux.

Couvre :
- Service ``signer_etat_des_lieux`` : nom saisi + horodatage serveur, refuse
  une double signature du même rôle, rôle invalide rejeté.
- Endpoint ``POST /etats-des-lieux/<id>/signer/`` : 400 sans role/nom, signe.
- Service ``charte_courante`` : version la plus récente, ``None`` si aucune.
- Service ``accuse_charte_manquant`` : True si le conducteur n'a pas accusé
  la version courante, False si accusé ou si aucune charte publiée.
- Endpoint ``POST /chartes-vehicule/`` : version auto-incrémentée côté
  serveur (jamais du body).
- Endpoint ``POST /accuses-charte/`` : version posée côté serveur = version
  courante.
- Endpoint ``POST /affectations/`` : warning ``charte_avertissement`` non
  bloquant si le conducteur n'a pas accusé la charte courante.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    AccuseCharte,
    CharteVehicule,
    Conducteur,
    EtatDesLieux,
    Vehicule,
)
from apps.flotte.services import (
    accuse_charte_manquant,
    charte_courante,
    signer_etat_des_lieux,
)

User = get_user_model()

URL_AFFECTATIONS = "/api/django/flotte/affectations/"
URL_CHARTES = "/api/django/flotte/chartes-vehicule/"
URL_ACCUSES = "/api/django/flotte/accuses-charte/"


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


def make_charte(company, version=1):
    fichier = SimpleUploadedFile(
        "charte.pdf", b"contenu", content_type="application/pdf")
    return CharteVehicule.objects.create(
        company=company, version=version, document=fichier)


class SignerEtatDesLieuxServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("charte-svc", "Charte Svc")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="CHT-1", energie="diesel")
        self.etat = EtatDesLieux.objects.create(
            company=self.co, vehicule=self.veh,
            date_constat=datetime.datetime(2026, 6, 1, 8, 0))

    def test_signe_nom_et_horodatage(self):
        etat = signer_etat_des_lieux(
            self.etat, role='conducteur', nom='Ahmed Test')
        self.assertEqual(etat.signature_conducteur, 'Ahmed Test')
        self.assertIsNotNone(etat.signature_conducteur_horodatage)

    def test_refuse_double_signature_meme_role(self):
        signer_etat_des_lieux(self.etat, role='conducteur', nom='Ahmed')
        with self.assertRaises(ValueError):
            signer_etat_des_lieux(self.etat, role='conducteur', nom='Autre')

    def test_role_invalide_rejete(self):
        with self.assertRaises(ValueError):
            signer_etat_des_lieux(self.etat, role='inconnu', nom='Ahmed')


class SignerEtatDesLieuxApiTests(TestCase):
    def setUp(self):
        self.co = make_company("charte-api", "Charte Api")
        self.user = make_user(self.co, "charte-user")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="CHT-2", energie="diesel")
        self.etat = EtatDesLieux.objects.create(
            company=self.co, vehicule=self.veh,
            date_constat=datetime.datetime(2026, 6, 1, 8, 0))

    def test_signer_requiert_role_et_nom(self):
        resp = auth(self.user).post(
            f"/api/django/flotte/etats-des-lieux/{self.etat.id}/signer/",
            {}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_signer_appose_signature(self):
        resp = auth(self.user).post(
            f"/api/django/flotte/etats-des-lieux/{self.etat.id}/signer/",
            {"role": "responsable", "nom": "Sami Resp"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["signature_responsable"], "Sami Resp")
        self.assertIsNotNone(resp.data["signature_responsable_horodatage"])


class CharteCouranteServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("charte-cour", "Charte Cour")

    def test_aucune_charte_retourne_none(self):
        self.assertIsNone(charte_courante(self.co))

    def test_version_la_plus_recente(self):
        make_charte(self.co, version=1)
        make_charte(self.co, version=2)
        charte = charte_courante(self.co)
        self.assertEqual(charte.version, 2)


class AccuseCharteManquantServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("charte-acc", "Charte Acc")
        self.cond = Conducteur.objects.create(company=self.co, nom="Karim")

    def test_aucune_charte_publiee_jamais_de_warning(self):
        self.assertFalse(accuse_charte_manquant(self.cond))

    def test_conducteur_sans_accuse_warning(self):
        make_charte(self.co, version=1)
        self.assertTrue(accuse_charte_manquant(self.cond))

    def test_conducteur_avec_accuse_pas_de_warning(self):
        charte = make_charte(self.co, version=1)
        AccuseCharte.objects.create(
            company=self.co, conducteur=self.cond, version=charte.version)
        self.assertFalse(accuse_charte_manquant(self.cond))


class CharteVehiculeApiTests(TestCase):
    def setUp(self):
        self.co = make_company("charte-crud", "Charte Crud")
        self.user = make_user(self.co, "charte-crud-user")

    def test_version_auto_incrementee_serveur(self):
        fichier1 = SimpleUploadedFile(
            "v1.pdf", b"v1", content_type="application/pdf")
        resp = auth(self.user).post(
            URL_CHARTES, {"document": fichier1}, format="multipart")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["version"], 1)

        fichier2 = SimpleUploadedFile(
            "v2.pdf", b"v2", content_type="application/pdf")
        resp = auth(self.user).post(
            URL_CHARTES, {"document": fichier2, "version": 99},
            format="multipart")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["version"], 2)


class AccuseCharteApiTests(TestCase):
    def setUp(self):
        self.co = make_company("accuse-api", "Accuse Api")
        self.user = make_user(self.co, "accuse-user")
        self.cond = Conducteur.objects.create(company=self.co, nom="Nadia")
        self.charte = make_charte(self.co, version=1)

    def test_accuse_version_courante_serveur(self):
        resp = auth(self.user).post(URL_ACCUSES, {
            "conducteur": self.cond.id,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["version"], 1)

    def test_accuse_sans_charte_publiee_refuse(self):
        autre_co = make_company("accuse-sans", "Accuse Sans")
        autre_user = make_user(autre_co, "accuse-sans-user")
        autre_cond = Conducteur.objects.create(company=autre_co, nom="X")
        resp = auth(autre_user).post(URL_ACCUSES, {
            "conducteur": autre_cond.id,
        }, format="json")
        self.assertEqual(resp.status_code, 400)


class AffectationCharteWarningApiTests(TestCase):
    def setUp(self):
        self.co = make_company("aff-charte", "Aff Charte")
        self.user = make_user(self.co, "aff-charte-user")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="CHT-3", energie="diesel")
        self.cond = Conducteur.objects.create(company=self.co, nom="Yassine")

    def test_warning_charte_non_accusee(self):
        make_charte(self.co, version=1)
        resp = auth(self.user).post(URL_AFFECTATIONS, {
            "conducteur": self.cond.id,
            "vehicule": self.veh.id,
            "date_debut": "2026-06-01",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNotNone(resp.data["charte_avertissement"])
        self.assertIn("v1", resp.data["charte_avertissement"])

    def test_aucun_warning_si_charte_accusee(self):
        charte = make_charte(self.co, version=1)
        AccuseCharte.objects.create(
            company=self.co, conducteur=self.cond, version=charte.version)
        resp = auth(self.user).post(URL_AFFECTATIONS, {
            "conducteur": self.cond.id,
            "vehicule": self.veh.id,
            "date_debut": "2026-06-01",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data["charte_avertissement"])

    def test_aucun_warning_si_aucune_charte_publiee(self):
        resp = auth(self.user).post(URL_AFFECTATIONS, {
            "conducteur": self.cond.id,
            "vehicule": self.veh.id,
            "date_debut": "2026-06-01",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data["charte_avertissement"])
