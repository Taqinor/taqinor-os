"""Tests XFLT20 — Registre de remise clés / carte / badge / tag Jawaz.

Couvre :
- Selector ``detenteurs_courants(company, actif_flotte_id)`` : détenteur
  courant par type (dernière ligne sans retour), rien si restitué.
- Selector ``accessoires_non_rendus(company, conducteur_id)`` : liste les
  accessoires détenus non rendus, tous actifs confondus.
- Service ``avertissement_accessoires_non_rendus`` : message si clé non
  rendue, ``None`` sinon.
- Endpoint ``GET /actifs/<id>/detenteurs-courants/`` : expose le détenteur
  courant par accessoire sur la fiche véhicule.
- Endpoint ``PATCH /affectations/<id>/`` (date_fin) : warning non bloquant
  ``accessoires_avertissement`` si clé non rendue.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    AffectationConducteur,
    Conducteur,
    RemiseAccessoire,
    Vehicule,
)
from apps.flotte.selectors import accessoires_non_rendus, detenteurs_courants
from apps.flotte.services import avertissement_accessoires_non_rendus

User = get_user_model()

URL_AFFECTATIONS = "/api/django/flotte/affectations/"


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


def make_actif(company, immat="REM-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh), veh


class DetenteursCourantsSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("rem-svc", "Rem Svc")
        self.actif, self.veh = make_actif(self.co)
        self.cond = Conducteur.objects.create(company=self.co, nom="Hicham")

    def test_detenteur_courant_sans_retour(self):
        RemiseAccessoire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_accessoire=RemiseAccessoire.Type.CLE, conducteur=self.cond,
            date_remise=datetime.date(2026, 6, 1))
        detenteurs = detenteurs_courants(self.co, self.actif.id)
        self.assertEqual(len(detenteurs), 1)
        self.assertEqual(detenteurs[0]['conducteur_id'], self.cond.id)
        self.assertEqual(detenteurs[0]['type'], 'cle')

    def test_accessoire_restitue_non_liste(self):
        RemiseAccessoire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_accessoire=RemiseAccessoire.Type.CLE, conducteur=self.cond,
            date_remise=datetime.date(2026, 6, 1),
            date_retour=datetime.date(2026, 6, 5))
        detenteurs = detenteurs_courants(self.co, self.actif.id)
        self.assertEqual(detenteurs, [])

    def test_derniere_remise_prevaut(self):
        autre_cond = Conducteur.objects.create(company=self.co, nom="Nabil")
        RemiseAccessoire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_accessoire=RemiseAccessoire.Type.CLE, conducteur=self.cond,
            date_remise=datetime.date(2026, 6, 1),
            date_retour=datetime.date(2026, 6, 5))
        RemiseAccessoire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_accessoire=RemiseAccessoire.Type.CLE, conducteur=autre_cond,
            date_remise=datetime.date(2026, 6, 6))
        detenteurs = detenteurs_courants(self.co, self.actif.id)
        self.assertEqual(len(detenteurs), 1)
        self.assertEqual(detenteurs[0]['conducteur_id'], autre_cond.id)


class AccessoiresNonRendusServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("rem-warn", "Rem Warn")
        self.actif, self.veh = make_actif(self.co)
        self.cond = Conducteur.objects.create(company=self.co, nom="Yassir")

    def test_avertissement_si_cle_non_rendue(self):
        RemiseAccessoire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_accessoire=RemiseAccessoire.Type.CLE, conducteur=self.cond,
            date_remise=datetime.date(2026, 6, 1))
        affectation = AffectationConducteur.objects.create(
            company=self.co, conducteur=self.cond, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1),
            date_fin=datetime.date(2026, 6, 10))
        message = avertissement_accessoires_non_rendus(affectation)
        self.assertIsNotNone(message)
        self.assertIn("Clé", message)

    def test_aucun_avertissement_si_tout_rendu(self):
        RemiseAccessoire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_accessoire=RemiseAccessoire.Type.CLE, conducteur=self.cond,
            date_remise=datetime.date(2026, 6, 1),
            date_retour=datetime.date(2026, 6, 5))
        affectation = AffectationConducteur.objects.create(
            company=self.co, conducteur=self.cond, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1),
            date_fin=datetime.date(2026, 6, 10))
        self.assertIsNone(avertissement_accessoires_non_rendus(affectation))

    def test_accessoires_non_rendus_selector(self):
        RemiseAccessoire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_accessoire=RemiseAccessoire.Type.TAG_JAWAZ,
            conducteur=self.cond, date_remise=datetime.date(2026, 6, 1))
        resultat = accessoires_non_rendus(self.co, self.cond.id)
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[0]['type'], 'tag_jawaz')


class DetenteursCourantsApiTests(TestCase):
    def setUp(self):
        self.co = make_company("rem-api", "Rem Api")
        self.user = make_user(self.co, "rem-user")
        self.actif, self.veh = make_actif(self.co, immat="REM-A1")
        self.cond = Conducteur.objects.create(company=self.co, nom="Othmane")

    def test_endpoint_detenteurs_courants(self):
        RemiseAccessoire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_accessoire=RemiseAccessoire.Type.BADGE, conducteur=self.cond,
            date_remise=datetime.date(2026, 6, 1))
        resp = auth(self.user).get(
            f"/api/django/flotte/actifs/{self.actif.id}/detenteurs-courants/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['type'], 'badge')


class AffectationAccessoiresWarningApiTests(TestCase):
    def setUp(self):
        self.co = make_company("rem-aff", "Rem Aff")
        self.user = make_user(self.co, "rem-aff-user")
        self.actif, self.veh = make_actif(self.co, immat="REM-A2")
        self.cond = Conducteur.objects.create(company=self.co, nom="Zakaria")
        self.affectation = AffectationConducteur.objects.create(
            company=self.co, conducteur=self.cond, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1))

    def test_fin_affectation_cle_non_rendue_warning(self):
        RemiseAccessoire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_accessoire=RemiseAccessoire.Type.CLE, conducteur=self.cond,
            date_remise=datetime.date(2026, 1, 1))
        resp = auth(self.user).patch(
            f"{URL_AFFECTATIONS}{self.affectation.id}/",
            {"date_fin": "2026-06-10"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(resp.data["accessoires_avertissement"])

    def test_fin_affectation_sans_accessoire_pas_de_warning(self):
        resp = auth(self.user).patch(
            f"{URL_AFFECTATIONS}{self.affectation.id}/",
            {"date_fin": "2026-06-10"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data["accessoires_avertissement"])
