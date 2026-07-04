"""Tests XFLT12 — Catalogue de modèles véhicule.

Couvre :
- Service ``prefill_depuis_modele(vehicule_data, modele)`` :
  - champs vides pré-remplis depuis le modèle ;
  - une saisie existante n'est JAMAIS écrasée ;
  - ``modele=None`` ne change rien.
- Endpoint ``POST /vehicules/`` avec ``modele_ref`` : pré-remplit
  energie/puissance_fiscale/valeur côté serveur.
- Selector ``anomalies_pleins`` : un plein dont la quantité (litres) dépasse
  la ``capacite_reservoir_l`` du modèle catalogue du véhicule remonte en
  anomalie ``plein_superieur_reservoir`` ; sous la capacité → rien ; un
  véhicule sans ``modele_ref`` n'est jamais évalué (aucune régression).
- CRUD ``/modeles-vehicule/`` scopé société.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ModeleVehicule, PleinCarburant, Vehicule
from apps.flotte.selectors import anomalies_pleins
from apps.flotte.services import prefill_depuis_modele

User = get_user_model()

URL_VEHICULES = "/api/django/flotte/vehicules/"
URL_MODELES = "/api/django/flotte/modeles-vehicule/"


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


def make_modele(
        company, marque="Renault", modele="Kangoo", energie="diesel",
        puissance_fiscale=6, valeur_catalogue=180000, capacite_reservoir_l=55):
    return ModeleVehicule.objects.create(
        company=company, marque=marque, modele=modele, energie=energie,
        puissance_fiscale=puissance_fiscale,
        valeur_catalogue=valeur_catalogue,
        capacite_reservoir_l=capacite_reservoir_l)


class PrefillDepuisModeleServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("mv-svc", "MV Svc")
        self.modele = make_modele(self.co)

    def test_prefill_champs_vides(self):
        data = {}
        prefill_depuis_modele(data, self.modele)
        self.assertEqual(data["energie"], "diesel")
        self.assertEqual(data["puissance_fiscale"], 6)
        self.assertEqual(data["valeur"], 180000)

    def test_ne_jamais_ecraser_saisie_existante(self):
        data = {"energie": "essence", "puissance_fiscale": 9}
        prefill_depuis_modele(data, self.modele)
        self.assertEqual(data["energie"], "essence")
        self.assertEqual(data["puissance_fiscale"], 9)
        # Champ absent du dict initial → pré-rempli.
        self.assertEqual(data["valeur"], 180000)

    def test_modele_none_ne_change_rien(self):
        data = {"energie": "essence"}
        resultat = prefill_depuis_modele(data, None)
        self.assertEqual(resultat, {"energie": "essence"})


class VehiculeCreationAvecModeleApiTests(TestCase):
    def setUp(self):
        self.co = make_company("mv-api", "MV Api")
        self.user = make_user(self.co, "mv-user")
        self.modele = make_modele(self.co)

    def test_creation_avec_modele_ref_prefill(self):
        resp = auth(self.user).post(URL_VEHICULES, {
            "immatriculation": "MV-1",
            "modele_ref": self.modele.id,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["energie"], "diesel")
        self.assertEqual(resp.data["puissance_fiscale"], 6)
        self.assertEqual(float(resp.data["valeur"]), 180000.0)
        self.assertEqual(resp.data["modele_ref"], self.modele.id)

    def test_creation_avec_modele_ref_et_saisie_explicite_non_ecrasee(self):
        resp = auth(self.user).post(URL_VEHICULES, {
            "immatriculation": "MV-2",
            "modele_ref": self.modele.id,
            "energie": "essence",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["energie"], "essence")


class AnomaliePleinReservoirTests(TestCase):
    def setUp(self):
        self.co = make_company("mv-anom", "MV Anom")
        self.modele = make_modele(self.co, capacite_reservoir_l=55)

    def test_plein_superieur_reservoir_remonte_anomalie(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="MV-A1", energie="diesel",
            modele_ref=self.modele)
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh,
            date_plein=datetime.date.today(), kilometrage=1000,
            quantite=70, unite="litre", prix_total=700)
        resultat = anomalies_pleins(self.co)
        types = [a["type"] for a in resultat["anomalies"]]
        self.assertIn("plein_superieur_reservoir", types)

    def test_plein_sous_capacite_aucune_anomalie(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="MV-A2", energie="diesel",
            modele_ref=self.modele)
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh,
            date_plein=datetime.date.today(), kilometrage=1000,
            quantite=40, unite="litre", prix_total=400)
        resultat = anomalies_pleins(self.co)
        types = [a["type"] for a in resultat["anomalies"]]
        self.assertNotIn("plein_superieur_reservoir", types)

    def test_vehicule_sans_modele_ref_jamais_evalue(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="MV-A3", energie="diesel")
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh,
            date_plein=datetime.date.today(), kilometrage=1000,
            quantite=200, unite="litre", prix_total=2000)
        resultat = anomalies_pleins(self.co)
        types = [a["type"] for a in resultat["anomalies"]]
        self.assertNotIn("plein_superieur_reservoir", types)


class ModeleVehiculeCrudApiTests(TestCase):
    def setUp(self):
        self.co = make_company("mv-crud", "MV Crud")
        self.user = make_user(self.co, "mv-crud-user")

    def test_creation_et_liste_scopees_societe(self):
        resp = auth(self.user).post(URL_MODELES, {
            "marque": "Peugeot", "modele": "Partner", "energie": "diesel",
            "capacite_reservoir_l": 60,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)

        autre_co = make_company("mv-crud-2", "MV Crud 2")
        ModeleVehicule.objects.create(
            company=autre_co, marque="Autre", modele="Modele")

        resp = auth(self.user).get(URL_MODELES)
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        rows = data["results"] if isinstance(data, dict) and "results" in data \
            else data
        marques = [row["marque"] for row in rows]
        self.assertIn("Peugeot", marques)
        self.assertNotIn("Autre", marques)
