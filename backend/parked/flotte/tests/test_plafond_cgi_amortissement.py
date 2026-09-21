"""Tests XFLT9 — Plafond CGI d'amortissement des véhicules de tourisme.

Couvre :
- Modèle ``ParametreAmortissementCGI`` : plafond par défaut (400 000 DH),
  ``plafond_pour(company)``.
- Selector ``part_non_deductible_amortissement(company, vehicule_id)`` :
  - véhicule tourisme à 600 000 DH TTC → part non déductible = amortissement
    × (600k−400k)/600k ;
  - véhicule utilitaire → 0 (exonéré du plafond) ;
  - plafond éditable par société (override) ;
  - véhicule sous le plafond → 0 ;
  - véhicule sans immobilisation liée → 0.
- Endpoint API ``GET /vehicules/<id>/amortissement/`` expose
  ``part_non_deductible``.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta.models import Immobilisation
from apps.compta.services import generer_plan_amortissement
from apps.flotte.models import ParametreAmortissementCGI, Vehicule
from apps.flotte.selectors import part_non_deductible_amortissement

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


def make_vehicule_avec_immo(company, immat, type_fiscal, cout,
                            duree_annees=5):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel",
        type_fiscal=type_fiscal)
    immo = Immobilisation.objects.create(
        company=company, libelle=f"Véhicule {immat}", categorie="vehicule",
        cout=Decimal(str(cout)), date_acquisition=datetime.date(2024, 1, 1))
    generer_plan_amortissement(immo, duree_annees=duree_annees)
    veh.immobilisation = immo
    veh.save(update_fields=["immobilisation"])
    return veh


class ParametreAmortissementCGIModelTests(TestCase):
    def setUp(self):
        self.co = make_company("cgi-model", "Cgi Model")

    def test_plafond_par_defaut(self):
        self.assertEqual(
            ParametreAmortissementCGI.plafond_pour(self.co), 400000.0)

    def test_plafond_editable(self):
        ParametreAmortissementCGI.objects.create(
            company=self.co, plafond_ttc=Decimal("500000.00"))
        self.assertEqual(
            ParametreAmortissementCGI.plafond_pour(self.co), 500000.0)


class PartNonDeductibleAmortissementSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("cgi-sel", "Cgi Sel")

    def test_tourisme_au_dessus_plafond(self):
        veh = make_vehicule_avec_immo(
            self.co, "CGI600", Vehicule.TypeFiscal.TOURISME, 600000)
        result = part_non_deductible_amortissement(self.co, veh.id)
        self.assertTrue(result['assujetti'])
        cumul = result['cumul_amortissements']
        attendu = round(cumul * (600000 - 400000) / 600000, 2)
        self.assertEqual(result['part_non_deductible'], attendu)
        self.assertGreater(result['part_non_deductible'], 0)

    def test_utilitaire_exonere(self):
        veh = make_vehicule_avec_immo(
            self.co, "CGIUTIL", Vehicule.TypeFiscal.UTILITAIRE, 600000)
        result = part_non_deductible_amortissement(self.co, veh.id)
        self.assertFalse(result['assujetti'])
        self.assertEqual(result['part_non_deductible'], 0.0)

    def test_tourisme_sous_plafond(self):
        veh = make_vehicule_avec_immo(
            self.co, "CGI300", Vehicule.TypeFiscal.TOURISME, 300000)
        result = part_non_deductible_amortissement(self.co, veh.id)
        self.assertEqual(result['part_non_deductible'], 0.0)

    def test_plafond_editable_change_le_calcul(self):
        veh = make_vehicule_avec_immo(
            self.co, "CGI600B", Vehicule.TypeFiscal.TOURISME, 600000)
        ParametreAmortissementCGI.objects.create(
            company=self.co, plafond_ttc=Decimal("500000.00"))
        result = part_non_deductible_amortissement(self.co, veh.id)
        cumul = result['cumul_amortissements']
        attendu = round(cumul * (600000 - 500000) / 600000, 2)
        self.assertEqual(result['part_non_deductible'], attendu)

    def test_sans_immobilisation_zero(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="NOIMMO", energie="diesel",
            type_fiscal=Vehicule.TypeFiscal.TOURISME)
        result = part_non_deductible_amortissement(self.co, veh.id)
        self.assertEqual(result['part_non_deductible'], 0.0)
        self.assertFalse(result['assujetti'])


class AmortissementApiXflt9Tests(TestCase):
    def setUp(self):
        self.co = make_company("cgi-api", "Cgi Api")
        self.admin = make_user(self.co, "cgi-admin", "admin")

    def test_amortissement_endpoint_expose_part_non_deductible(self):
        veh = make_vehicule_avec_immo(
            self.co, "CGIAPI", Vehicule.TypeFiscal.TOURISME, 600000)
        resp = auth(self.admin).get(
            f"/api/django/flotte/vehicules/{veh.id}/amortissement/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('part_non_deductible', resp.data)
        self.assertGreater(resp.data['part_non_deductible'], 0)
