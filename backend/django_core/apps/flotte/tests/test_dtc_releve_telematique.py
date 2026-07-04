"""Tests XFLT25 — Codes défaut moteur (DTC) sur les relevés télématiques.

Couvre :
- Champ additif ``ReleveTelematique.codes_defaut`` (JSON, défaut liste vide).
- Service ``criticite_dtc`` :
  - référentiel générique OBD-II par défaut (P0xxx -> critique) ;
  - référentiel société ÉDITABLE (``ReferentielFlotte`` domaine
    ``code_dtc``) prioritaire sur le défaut ;
  - code inconnu -> 'faible' (permissif).
- Service ``traiter_codes_defaut`` :
  - DTC critique -> un ``SignalementVehicule`` gravité critique créé ;
  - DTC bénin -> rien ;
  - IDEMPOTENT : un second passage sur le même relevé ne duplique pas le
    signalement ouvert pour le même code+véhicule.
- Endpoint ``POST /flotte/releves-telematiques/`` : la création avec un DTC
  critique déclenche le signalement automatiquement (perform_create).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    ReferentielFlotte,
    ReleveTelematique,
    SignalementVehicule,
    Vehicule,
)
from apps.flotte.services import criticite_dtc, traiter_codes_defaut

User = get_user_model()

URL = "/api/django/flotte/releves-telematiques/"

H = datetime.datetime(2026, 6, 1, 8, 0, 0)


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


def make_actif(company, immat="DTC-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


class CriticiteDtcTests(TestCase):
    def setUp(self):
        self.co = make_company("dtc-crit", "DTC Crit")

    def test_defaut_p0_critique(self):
        self.assertEqual(criticite_dtc(self.co, "P0301"), "critique")

    def test_defaut_u0_faible(self):
        self.assertEqual(criticite_dtc(self.co, "U0100"), "faible")

    def test_code_inconnu_faible(self):
        self.assertEqual(criticite_dtc(self.co, "ZZZ999"), "faible")

    def test_referentiel_societe_prioritaire(self):
        # La société surclasse P0 en 'faible' pour son propre parc.
        ReferentielFlotte.objects.create(
            company=self.co, domaine=ReferentielFlotte.Domaine.CODE_DTC,
            code="P0", libelle="faible")
        self.assertEqual(criticite_dtc(self.co, "P0301"), "faible")

    def test_referentiel_societe_ignore_pour_autre_societe(self):
        autre = make_company("dtc-crit-b", "DTC Crit B")
        ReferentielFlotte.objects.create(
            company=autre, domaine=ReferentielFlotte.Domaine.CODE_DTC,
            code="P0", libelle="faible")
        # Toujours le défaut générique pour self.co.
        self.assertEqual(criticite_dtc(self.co, "P0301"), "critique")


class TraiterCodesDefautTests(TestCase):
    def setUp(self):
        self.co = make_company("dtc-svc", "DTC Svc")
        self.actif = make_actif(self.co, "DSVC")

    def test_dtc_critique_cree_signalement(self):
        releve = ReleveTelematique.objects.create(
            company=self.co, actif_flotte=self.actif, horodatage=H,
            codes_defaut=["P0301"])
        crees = traiter_codes_defaut(releve)
        self.assertEqual(len(crees), 1)
        self.assertEqual(crees[0].gravite, SignalementVehicule.Gravite.CRITIQUE)
        self.assertIn("P0301", crees[0].description)

    def test_dtc_benin_rien(self):
        releve = ReleveTelematique.objects.create(
            company=self.co, actif_flotte=self.actif, horodatage=H,
            codes_defaut=["U0100"])
        self.assertEqual(traiter_codes_defaut(releve), [])
        self.assertEqual(SignalementVehicule.objects.count(), 0)

    def test_idempotent_pas_de_doublon(self):
        releve = ReleveTelematique.objects.create(
            company=self.co, actif_flotte=self.actif, horodatage=H,
            codes_defaut=["P0301"])
        premiers = traiter_codes_defaut(releve)
        self.assertEqual(len(premiers), 1)
        # Second passage sur le MÊME relevé (ou un nouveau relevé, même code
        # sur le même véhicule) : aucun nouveau signalement (idempotent).
        seconds = traiter_codes_defaut(releve)
        self.assertEqual(seconds, [])
        self.assertEqual(SignalementVehicule.objects.count(), 1)

    def test_sans_codes_rien(self):
        releve = ReleveTelematique.objects.create(
            company=self.co, actif_flotte=self.actif, horodatage=H)
        self.assertEqual(traiter_codes_defaut(releve), [])


class DtcEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company("dtc-api", "DTC Api")
        self.admin = make_user(self.co, "dtc-admin")
        self.actif = make_actif(self.co, "DAPI")

    def test_creation_avec_dtc_critique_cree_signalement(self):
        resp = auth(self.admin).post(URL, {
            "actif_flotte": self.actif.id,
            "horodatage": "2026-06-01T08:00:00Z",
            "codes_defaut": ["P0420"],
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(SignalementVehicule.objects.filter(
            company=self.co, actif_flotte=self.actif,
            gravite=SignalementVehicule.Gravite.CRITIQUE).count(), 1)

    def test_creation_sans_dtc_aucun_signalement(self):
        resp = auth(self.admin).post(URL, {
            "actif_flotte": self.actif.id,
            "horodatage": "2026-06-01T08:00:00Z",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(SignalementVehicule.objects.count(), 0)
