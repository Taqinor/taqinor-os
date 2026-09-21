"""Tests XFLT8 — TVA carburant : récupérable vs non déductible.

Couvre :
- Service ``classifier_tva_recuperable(vehicule)`` :
  - utilitaire → récupérable ; tourisme → non déductible ;
  - type_fiscal vide (inconnu) → récupérable (comportement historique).
- Selector ``synthese_tva_carburant(company, periode)`` :
  - synthèse mensuelle juste (récupérable / non déductible séparés).
- Endpoints API :
  - création d'un plein classe automatiquement selon le type_fiscal du
    véhicule (sauf override explicite) ;
  - ``GET /pleins/synthese-tva/`` (lecture tout rôle).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import PleinCarburant, Vehicule
from apps.flotte.selectors import synthese_tva_carburant
from apps.flotte.services import classifier_tva_recuperable

User = get_user_model()

URL_PLEINS = "/api/django/flotte/pleins/"
URL_SYNTHESE = "/api/django/flotte/pleins/synthese-tva/"


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


class ClassifierTvaRecuperableServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("tva-svc", "Tva Svc")

    def test_utilitaire_recuperable(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="U1", energie="diesel",
            type_fiscal=Vehicule.TypeFiscal.UTILITAIRE)
        self.assertTrue(classifier_tva_recuperable(veh))

    def test_tourisme_non_deductible(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="T1", energie="diesel",
            type_fiscal=Vehicule.TypeFiscal.TOURISME)
        self.assertFalse(classifier_tva_recuperable(veh))

    def test_type_fiscal_inconnu_recuperable_par_defaut(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="INC", energie="diesel")
        self.assertTrue(classifier_tva_recuperable(veh))


class SyntheseTvaCarburantSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("tva-sel", "Tva Sel")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="TSEL", energie="diesel")

    def test_synthese_mensuelle_juste(self):
        PleinCarburant.objects.create(
            company=self.co, vehicule=self.veh,
            date_plein=datetime.date(2026, 6, 5), kilometrage=100,
            quantite=40, prix_total=440, tva_recuperable=True,
            montant_tva=88)
        PleinCarburant.objects.create(
            company=self.co, vehicule=self.veh,
            date_plein=datetime.date(2026, 6, 20), kilometrage=200,
            quantite=30, prix_total=330, tva_recuperable=False,
            montant_tva=66)
        result = synthese_tva_carburant(self.co, periode=(None, None))
        bloc = next(b for b in result['par_mois'] if b['mois'] == '2026-06')
        self.assertEqual(bloc['tva_recuperable'], 88.0)
        self.assertEqual(bloc['tva_non_deductible'], 66.0)
        self.assertEqual(result['total_recuperable'], 88.0)
        self.assertEqual(result['total_non_deductible'], 66.0)

    def test_periode_bornee(self):
        PleinCarburant.objects.create(
            company=self.co, vehicule=self.veh,
            date_plein=datetime.date(2026, 1, 5), kilometrage=100,
            quantite=40, prix_total=440, montant_tva=88)
        PleinCarburant.objects.create(
            company=self.co, vehicule=self.veh,
            date_plein=datetime.date(2026, 6, 5), kilometrage=200,
            quantite=40, prix_total=440, montant_tva=88)
        result = synthese_tva_carburant(
            self.co,
            periode=(datetime.date(2026, 5, 1), datetime.date(2026, 12, 31)))
        mois = [b['mois'] for b in result['par_mois']]
        self.assertEqual(mois, ['2026-06'])


class TvaCarburantApiTests(TestCase):
    def setUp(self):
        self.co = make_company("tva-api", "Tva Api")
        self.admin = make_user(self.co, "tva-admin", "admin")
        self.user_normal = make_user(self.co, "tva-user", "normal")
        self.veh_tourisme = Vehicule.objects.create(
            company=self.co, immatriculation="TAPI", energie="diesel",
            type_fiscal=Vehicule.TypeFiscal.TOURISME)

    def test_creation_classifie_automatiquement(self):
        resp = auth(self.admin).post(URL_PLEINS, {
            "vehicule": self.veh_tourisme.id, "date_plein": "2026-06-01",
            "kilometrage": 500, "quantite": "40", "prix_total": "440",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data['tva_recuperable'])

    def test_override_explicite_respecte(self):
        resp = auth(self.admin).post(URL_PLEINS, {
            "vehicule": self.veh_tourisme.id, "date_plein": "2026-06-01",
            "kilometrage": 500, "quantite": "40", "prix_total": "440",
            "tva_recuperable": True,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['tva_recuperable'])

    def test_synthese_tva_read_any_role(self):
        PleinCarburant.objects.create(
            company=self.co, vehicule=self.veh_tourisme,
            date_plein=datetime.date(2026, 6, 1), kilometrage=100,
            quantite=40, prix_total=440, tva_recuperable=False,
            montant_tva=88)
        resp = auth(self.user_normal).get(URL_SYNTHESE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total_non_deductible'], 88.0)
