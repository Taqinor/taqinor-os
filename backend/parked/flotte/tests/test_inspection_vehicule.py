"""Tests XFLT13 — Inspections périodiques paramétrables (check-lists DVIR).

Couvre :
- Service ``traiter_items_fail(inspection)`` :
  - item ``fail`` crée un ``SignalementVehicule`` lié ;
  - item ``bloquant`` du modèle → gravité ``critique`` ; sinon ``moyenne`` ;
  - item ``pass`` ne crée rien.
- Service ``taux_completion_inspections_par_conducteur`` : taux pass/total
  par conducteur.
- Endpoint ``POST /inspections/`` : company/auteur posés côté serveur, item
  fail génère automatiquement le signalement.
- Endpoint ``GET /inspections/taux-completion/``.
- Distinct de ``EtatDesLieux`` (FLOTTE11) — pas de doublon de modèle.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    Conducteur,
    InspectionVehicule,
    ModeleInspection,
    SignalementVehicule,
    Vehicule,
)
from apps.flotte.services import (
    taux_completion_inspections_par_conducteur,
    traiter_items_fail,
)

User = get_user_model()

URL = "/api/django/flotte/inspections/"
URL_TAUX = "/api/django/flotte/inspections/taux-completion/"


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


def make_actif(company, immat="INSP-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


def make_modele(company, nom="Pré-départ", items=None):
    if items is None:
        items = [
            {"libelle": "Freins", "photo_requise": False, "bloquant": True},
            {"libelle": "Feux", "photo_requise": False, "bloquant": False},
        ]
    return ModeleInspection.objects.create(
        company=company, nom=nom, items=items)


class TraiterItemsFailServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("insp-svc", "Insp Svc")
        self.actif = make_actif(self.co)
        self.modele = make_modele(self.co)

    def test_item_fail_cree_signalement_lie(self):
        inspection = InspectionVehicule.objects.create(
            company=self.co, actif_flotte=self.actif,
            modele_inspection=self.modele,
            resultats=[
                {"libelle": "Freins", "resultat": "fail"},
                {"libelle": "Feux", "resultat": "pass"},
            ])
        crees = traiter_items_fail(inspection)
        self.assertEqual(len(crees), 1)
        self.assertEqual(SignalementVehicule.objects.count(), 1)
        signalement = SignalementVehicule.objects.first()
        self.assertEqual(signalement.actif_flotte_id, self.actif.id)
        self.assertIn("Freins", signalement.description)

    def test_item_bloquant_gravite_critique(self):
        inspection = InspectionVehicule.objects.create(
            company=self.co, actif_flotte=self.actif,
            modele_inspection=self.modele,
            resultats=[{"libelle": "Freins", "resultat": "fail"}])
        traiter_items_fail(inspection)
        signalement = SignalementVehicule.objects.first()
        self.assertEqual(signalement.gravite, SignalementVehicule.Gravite.CRITIQUE)

    def test_item_non_bloquant_gravite_moyenne(self):
        inspection = InspectionVehicule.objects.create(
            company=self.co, actif_flotte=self.actif,
            modele_inspection=self.modele,
            resultats=[{"libelle": "Feux", "resultat": "fail"}])
        traiter_items_fail(inspection)
        signalement = SignalementVehicule.objects.first()
        self.assertEqual(signalement.gravite, SignalementVehicule.Gravite.MOYENNE)

    def test_tous_items_pass_aucun_signalement(self):
        inspection = InspectionVehicule.objects.create(
            company=self.co, actif_flotte=self.actif,
            modele_inspection=self.modele,
            resultats=[
                {"libelle": "Freins", "resultat": "pass"},
                {"libelle": "Feux", "resultat": "pass"},
            ])
        crees = traiter_items_fail(inspection)
        self.assertEqual(crees, [])
        self.assertEqual(SignalementVehicule.objects.count(), 0)


class TauxCompletionServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("insp-taux", "Insp Taux")
        self.actif = make_actif(self.co)
        self.modele = make_modele(self.co)
        self.cond = Conducteur.objects.create(company=self.co, nom="Ali")

    def test_taux_completion_par_conducteur(self):
        InspectionVehicule.objects.create(
            company=self.co, actif_flotte=self.actif,
            modele_inspection=self.modele, conducteur=self.cond,
            resultats=[
                {"libelle": "Freins", "resultat": "pass"},
                {"libelle": "Feux", "resultat": "fail"},
            ])
        resultats = taux_completion_inspections_par_conducteur(self.co)
        self.assertEqual(len(resultats), 1)
        entree = resultats[0]
        self.assertEqual(entree["conducteur_id"], self.cond.id)
        self.assertEqual(entree["nb_items"], 2)
        self.assertEqual(entree["nb_pass"], 1)
        self.assertEqual(entree["taux_completion"], 50.0)


class InspectionVehiculeApiTests(TestCase):
    def setUp(self):
        self.co = make_company("insp-api", "Insp Api")
        self.actif = make_actif(self.co)
        self.modele = make_modele(self.co)
        self.user = make_user(self.co, "insp-user")

    def test_creation_avec_fail_genere_signalement(self):
        resp = auth(self.user).post(URL, {
            "actif_flotte": self.actif.id,
            "modele_inspection": self.modele.id,
            "resultats": [
                {"libelle": "Freins", "resultat": "fail"},
                {"libelle": "Feux", "resultat": "pass"},
            ],
            "signature_nom": "Ali Test",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["nb_items_fail"], 1)
        self.assertEqual(SignalementVehicule.objects.filter(
            company=self.co).count(), 1)

    def test_taux_completion_endpoint(self):
        cond = Conducteur.objects.create(company=self.co, nom="Sami")
        InspectionVehicule.objects.create(
            company=self.co, actif_flotte=self.actif,
            modele_inspection=self.modele, conducteur=cond,
            resultats=[{"libelle": "Freins", "resultat": "pass"}])
        resp = auth(self.user).get(URL_TAUX)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["taux_completion"], 100.0)
