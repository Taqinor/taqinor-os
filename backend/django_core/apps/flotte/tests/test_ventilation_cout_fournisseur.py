"""Tests XFLT30 — Ventilation d'une facture fournisseur sur plusieurs véhicules.

Couvre :
- Service ``ventiler_cout_fournisseur`` :
  - ventilation de 12 000 MAD sur 3 véhicules -> 3 coûts sommant EXACTEMENT
    12 000, même référence de pièce (Done= de la spec) ;
  - montant NON divisible par le nombre d'actifs (arrondi centime) -> la
    somme des lignes créées reste EXACTEMENT égale au total (reliquat sur la
    dernière ligne) ;
  - ``repartitions`` explicite qui NE somme PAS au total -> ``ValueError`` ;
  - ``repartitions`` explicite cohérente -> montants respectés tels quels ;
  - actif d'une autre société (id invalide) -> ignoré silencieusement, le
    reste de la ventilation aboutit.
- Endpoint ``POST /flotte/couts/ventiler/`` : réparation égale, erreurs 400
  (actifs manquants, montant/date absents, répartition incohérente).
"""
import datetime
import decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ActifFlotte, CoutVehicule, Vehicule
from apps.flotte.services import ventiler_cout_fournisseur

User = get_user_model()

URL = "/api/django/flotte/couts/ventiler/"


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


def make_actif(company, immat):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


class VentilerCoutFournisseurServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("ventil-svc", "Ventil Svc")
        self.a1 = make_actif(self.co, "VENT-1")
        self.a2 = make_actif(self.co, "VENT-2")
        self.a3 = make_actif(self.co, "VENT-3")

    def test_12000_sur_3_vehicules_somme_exacte(self):
        crees = ventiler_cout_fournisseur(
            self.co, montant_total="12000.00",
            actif_flotte_ids=[self.a1.id, self.a2.id, self.a3.id],
            date=datetime.date(2026, 6, 1),
            reference_piece="FAC-2026-042")
        self.assertEqual(len(crees), 3)
        total = sum((c.montant for c in crees), decimal.Decimal("0"))
        self.assertEqual(total, decimal.Decimal("12000.00"))
        self.assertTrue(all(
            c.reference_piece == "FAC-2026-042" for c in crees))
        self.assertEqual(CoutVehicule.objects.filter(company=self.co).count(), 3)

    def test_montant_non_divisible_somme_reste_exacte(self):
        # 10000 / 3 = 3333.333... -> arrondi centime + reliquat sur la
        # dernière ligne, la somme doit rester EXACTEMENT 10000.00.
        crees = ventiler_cout_fournisseur(
            self.co, montant_total="10000.00",
            actif_flotte_ids=[self.a1.id, self.a2.id, self.a3.id],
            date=datetime.date(2026, 6, 1),
            reference_piece="FAC-2026-043")
        total = sum((c.montant for c in crees), decimal.Decimal("0"))
        self.assertEqual(total, decimal.Decimal("10000.00"))

    def test_repartitions_explicites_respectees(self):
        crees = ventiler_cout_fournisseur(
            self.co, montant_total="12000",
            actif_flotte_ids=[self.a1.id, self.a2.id, self.a3.id],
            date=datetime.date(2026, 6, 1),
            reference_piece="FAC-2026-044",
            repartitions={self.a1.id: "5000", self.a2.id: "4000",
                          self.a3.id: "3000"})
        montants = {c.actif_flotte_id: c.montant for c in crees}
        self.assertEqual(montants[self.a1.id], decimal.Decimal("5000.00"))
        self.assertEqual(montants[self.a2.id], decimal.Decimal("4000.00"))
        self.assertEqual(montants[self.a3.id], decimal.Decimal("3000.00"))

    def test_repartitions_incoherentes_leve(self):
        with self.assertRaises(ValueError):
            ventiler_cout_fournisseur(
                self.co, montant_total="12000",
                actif_flotte_ids=[self.a1.id, self.a2.id],
                date=datetime.date(2026, 6, 1),
                repartitions={self.a1.id: "5000", self.a2.id: "4000"})

    def test_actif_autre_societe_ignore(self):
        autre = make_company("ventil-svc-b", "Ventil Svc B")
        actif_autre = make_actif(autre, "VENT-B1")
        crees = ventiler_cout_fournisseur(
            self.co, montant_total="6000",
            actif_flotte_ids=[self.a1.id, actif_autre.id],
            date=datetime.date(2026, 6, 1),
            reference_piece="FAC-2026-045")
        # Un seul actif valide (self.a1) : toute la somme lui revient.
        self.assertEqual(len(crees), 1)
        self.assertEqual(crees[0].montant, decimal.Decimal("6000.00"))


class VentilerCoutFournisseurApiTests(TestCase):
    def setUp(self):
        self.co = make_company("ventil-api", "Ventil Api")
        self.admin = make_user(self.co, "ventil-admin")
        self.a1 = make_actif(self.co, "VAPI-1")
        self.a2 = make_actif(self.co, "VAPI-2")
        self.a3 = make_actif(self.co, "VAPI-3")

    def test_ventilation_egale_201(self):
        resp = auth(self.admin).post(URL, {
            "montant_total": "12000.00",
            "actif_flotte_ids": [self.a1.id, self.a2.id, self.a3.id],
            "date": "2026-06-01",
            "reference_piece": "FAC-API-1",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data), 3)
        total = sum(decimal.Decimal(str(row["montant"])) for row in resp.data)
        self.assertEqual(total, decimal.Decimal("12000.00"))

    def test_actif_flotte_ids_manquant_400(self):
        resp = auth(self.admin).post(URL, {
            "montant_total": "1000", "date": "2026-06-01",
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_montant_manquant_400(self):
        resp = auth(self.admin).post(URL, {
            "actif_flotte_ids": [self.a1.id], "date": "2026-06-01",
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_repartition_incoherente_400(self):
        resp = auth(self.admin).post(URL, {
            "montant_total": "12000",
            "actif_flotte_ids": [self.a1.id, self.a2.id],
            "date": "2026-06-01",
            "repartitions": {str(self.a1.id): "5000", str(self.a2.id): "4000"},
        }, format="json")
        self.assertEqual(resp.status_code, 400)
