"""Tests XFLT15 — Analyse de remplacement (fin de vie économique).

Couvre :
- Modèle ``ParametreRemplacementFlotte.pour`` : défauts si non paramétré,
  valeurs stockées sinon.
- Selector ``analyse_remplacement(company, today)`` :
  - véhicule dépassant 2 règles (âge + km) → ``a_remplacer=True`` avec les
    règles déclenchées listées ;
  - véhicule dépassant seulement 1 règle → ``a_remplacer=False`` ;
  - véhicule vendu/réformé exclu ;
  - seuils éditables par société ;
  - budget estimé = valeur catalogue du modèle de référence.
- Endpoint ``GET /rapports/remplacement/`` (lecture tout rôle).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ModeleVehicule,
    OrdreReparation,
    ParametreRemplacementFlotte,
    Vehicule,
)
from apps.flotte.selectors import analyse_remplacement

User = get_user_model()

URL = "/api/django/flotte/rapports/remplacement/"


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


class ParametreRemplacementModelTests(TestCase):
    def setUp(self):
        self.co = make_company("rmp-model", "Rmp Model")

    def test_defauts_si_non_parametre(self):
        param = ParametreRemplacementFlotte.pour(self.co)
        self.assertEqual(param.age_max_ans, 8)
        self.assertEqual(param.km_max, 200000)

    def test_valeurs_stockees(self):
        ParametreRemplacementFlotte.objects.create(
            company=self.co, age_max_ans=5, km_max=100000)
        param = ParametreRemplacementFlotte.pour(self.co)
        self.assertEqual(param.age_max_ans, 5)
        self.assertEqual(param.km_max, 100000)


class AnalyseRemplacementSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("rmp-svc", "Rmp Svc")
        self.today = datetime.date(2026, 7, 3)

    def test_deux_regles_declenchees_flag_a_remplacer(self):
        # Âge > 8 ans (via date_acquisition, pas de carte grise) ET km > 200000.
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="RMP-1", energie="diesel",
            kilometrage=250000, valeur=100000,
            date_acquisition=self.today - datetime.timedelta(days=365 * 10))
        resultat = analyse_remplacement(self.co, today=self.today)
        ligne = next(
            v for v in resultat["vehicules"] if v["vehicule_id"] == veh.id)
        self.assertIn("age", ligne["regles_declenchees"])
        self.assertIn("kilometrage", ligne["regles_declenchees"])
        self.assertTrue(ligne["a_remplacer"])
        self.assertIn(veh.id, [v["vehicule_id"] for v in resultat["a_remplacer"]])

    def test_une_seule_regle_pas_de_flag(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="RMP-2", energie="diesel",
            kilometrage=250000, valeur=100000,
            date_acquisition=self.today - datetime.timedelta(days=365 * 2))
        resultat = analyse_remplacement(self.co, today=self.today)
        ligne = next(
            v for v in resultat["vehicules"] if v["vehicule_id"] == veh.id)
        self.assertEqual(ligne["regles_declenchees"], ["kilometrage"])
        self.assertFalse(ligne["a_remplacer"])

    def test_vehicule_vendu_exclu(self):
        Vehicule.objects.create(
            company=self.co, immatriculation="RMP-3", energie="diesel",
            kilometrage=300000, statut=Vehicule.Statut.VENDU,
            date_acquisition=self.today - datetime.timedelta(days=365 * 12))
        resultat = analyse_remplacement(self.co, today=self.today)
        immats = [v["immatriculation"] for v in resultat["vehicules"]]
        self.assertNotIn("RMP-3", immats)

    def test_seuils_editables(self):
        ParametreRemplacementFlotte.objects.create(
            company=self.co, age_max_ans=1, km_max=1000)
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="RMP-4", energie="diesel",
            kilometrage=5000,
            date_acquisition=self.today - datetime.timedelta(days=365 * 3))
        resultat = analyse_remplacement(self.co, today=self.today)
        ligne = next(
            v for v in resultat["vehicules"] if v["vehicule_id"] == veh.id)
        self.assertIn("age", ligne["regles_declenchees"])
        self.assertIn("kilometrage", ligne["regles_declenchees"])

    def test_budget_estime_depuis_modele_catalogue(self):
        modele = ModeleVehicule.objects.create(
            company=self.co, marque="Dacia", modele="Duster",
            valeur_catalogue=220000)
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="RMP-5", energie="diesel",
            kilometrage=250000, valeur=50000, modele_ref=modele,
            date_acquisition=self.today - datetime.timedelta(days=365 * 10))
        resultat = analyse_remplacement(self.co, today=self.today)
        ligne = next(
            v for v in resultat["vehicules"] if v["vehicule_id"] == veh.id)
        self.assertEqual(ligne["budget_remplacement_estime"], 220000.0)
        self.assertGreater(resultat["budget_annuel_estime"], 0)

    def test_ratio_cout_reparation_declenche_regle(self):
        from apps.flotte.models import ActifFlotte

        veh = Vehicule.objects.create(
            company=self.co, immatriculation="RMP-6", energie="diesel",
            kilometrage=1000, valeur=10000,
            date_acquisition=self.today - datetime.timedelta(days=30))
        actif = ActifFlotte.objects.create(company=self.co, vehicule=veh)
        OrdreReparation.objects.create(
            company=self.co, actif_flotte=actif,
            date_ouverture=self.today - datetime.timedelta(days=10),
            cout_main_oeuvre=5000, cout_pieces=0)
        resultat = analyse_remplacement(self.co, today=self.today)
        ligne = next(
            v for v in resultat["vehicules"] if v["vehicule_id"] == veh.id)
        self.assertIn("cout_reparation", ligne["regles_declenchees"])


class RapportRemplacementApiTests(TestCase):
    def setUp(self):
        self.co = make_company("rmp-api", "Rmp Api")
        self.user = make_user(self.co, "rmp-user")

    def test_endpoint_lecture(self):
        resp = auth(self.user).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("seuils", resp.data)
        self.assertIn("vehicules", resp.data)
        self.assertIn("a_remplacer", resp.data)
