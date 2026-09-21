"""Tests XFLT16 — Cession / sortie de parc.

Couvre :
- Service ``ceder_vehicule`` :
  - exige le statut ``a_vendre`` (ValueError sinon) ;
  - véhicule NON immobilisé → calcul local (prix_cession - valeur) ;
  - véhicule immobilisé (``compta.Immobilisation``) → délégué à
    ``apps.compta.services`` (jamais recalculé en doublon), statut passe à
    ``vendu``, historique conservé.
- Endpoint ``POST /vehicules/<id>/ceder/`` : 400 sans date/prix, calcule le
  gain/perte, retourne le véhicule mis à jour.
- Selector ``tableau_bord_flotte`` : ``total_actifs`` exclut vendu/réformé.
- Selector ``alertes_echeances_reglementaires`` : un véhicule vendu
  n'apparaît plus dans les alertes.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta.models import Immobilisation
from apps.flotte.models import ActifFlotte, AssuranceVehicule, Vehicule
from apps.flotte.selectors import (
    alertes_echeances_reglementaires,
    tableau_bord_flotte,
)
from apps.flotte.services import ceder_vehicule

User = get_user_model()

URL_TPL = "/api/django/flotte/vehicules/{}/ceder/"


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


def make_vehicule_a_vendre(company, immat="CES-1", valeur=80000,
                           immobilisation=None):
    return Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel",
        valeur=valeur, statut=Vehicule.Statut.A_VENDRE,
        immobilisation=immobilisation)


class CederVehiculeServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("ces-svc", "Ces Svc")

    def test_exige_statut_a_vendre(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="CES-A1", energie="diesel",
            statut=Vehicule.Statut.ACTIF)
        with self.assertRaises(ValueError):
            ceder_vehicule(
                veh, date_cession=datetime.date(2026, 6, 1),
                prix_cession=50000)

    def test_calcul_local_sans_immobilisation(self):
        veh = make_vehicule_a_vendre(self.co, valeur=80000)
        resultat = ceder_vehicule(
            veh, date_cession=datetime.date(2026, 6, 1),
            prix_cession=70000, acheteur="Client X")
        self.assertEqual(resultat['source'], 'local')
        self.assertEqual(resultat['resultat_cession'], -10000.0)
        veh.refresh_from_db()
        self.assertEqual(veh.statut, Vehicule.Statut.VENDU)
        self.assertEqual(veh.acheteur, "Client X")
        self.assertEqual(veh.date_cession, datetime.date(2026, 6, 1))

    def test_delegue_a_compta_si_immobilise(self):
        immo = Immobilisation.objects.create(
            company=self.co, libelle="Camionnette CES",
            categorie=Immobilisation.Categorie.VEHICULE, cout=100000,
            date_acquisition=datetime.date(2023, 1, 1))
        veh = make_vehicule_a_vendre(
            self.co, valeur=80000, immobilisation=immo)
        resultat = ceder_vehicule(
            veh, date_cession=datetime.date(2026, 6, 1), prix_cession=60000)
        self.assertEqual(resultat['source'], 'compta')
        # Sans plan d'amortissement, cumul=0 → VNC=cout=100000 → résultat=-40000.
        self.assertEqual(resultat['resultat_cession'], -40000.0)
        immo.refresh_from_db()
        self.assertFalse(immo.actif)

    def test_historique_conserve_apres_vente(self):
        veh = make_vehicule_a_vendre(self.co, immat="CES-H1")
        actif = ActifFlotte.objects.create(company=self.co, vehicule=veh)
        AssuranceVehicule.objects.create(
            company=self.co, actif_flotte=actif, assureur="Wafa",
            numero_police="P-1", date_debut=datetime.date(2025, 1, 1),
            date_echeance=datetime.date(2027, 1, 1))
        ceder_vehicule(
            veh, date_cession=datetime.date(2026, 6, 1), prix_cession=70000)
        self.assertEqual(
            AssuranceVehicule.objects.filter(actif_flotte=actif).count(), 1)


class CessionApiTests(TestCase):
    def setUp(self):
        self.co = make_company("ces-api", "Ces Api")
        self.user = make_user(self.co, "ces-user")

    def test_ceder_endpoint_requiert_date_et_prix(self):
        veh = make_vehicule_a_vendre(self.co)
        resp = auth(self.user).post(
            URL_TPL.format(veh.id), {}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_ceder_endpoint_calcule_gain_perte(self):
        veh = make_vehicule_a_vendre(self.co, valeur=50000)
        resp = auth(self.user).post(URL_TPL.format(veh.id), {
            "date_cession": "2026-06-01",
            "prix_cession": "60000",
            "acheteur": "Client Y",
        }, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["resultat_cession"], 10000.0)
        self.assertEqual(resp.data["statut"], Vehicule.Statut.VENDU)

    def test_ceder_refuse_statut_invalide(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="CES-A2", energie="diesel",
            statut=Vehicule.Statut.ACTIF)
        resp = auth(self.user).post(URL_TPL.format(veh.id), {
            "date_cession": "2026-06-01", "prix_cession": "60000",
        }, format="json")
        self.assertEqual(resp.status_code, 400)


class DashboardEtAlertesExclusionTests(TestCase):
    def setUp(self):
        self.co = make_company("ces-dash", "Ces Dash")

    def test_dashboard_total_actifs_exclut_vendu(self):
        Vehicule.objects.create(
            company=self.co, immatriculation="CES-D1", energie="diesel",
            statut=Vehicule.Statut.ACTIF)
        Vehicule.objects.create(
            company=self.co, immatriculation="CES-D2", energie="diesel",
            statut=Vehicule.Statut.VENDU)
        dashboard = tableau_bord_flotte(self.co)
        self.assertEqual(dashboard['vehicules']['total'], 2)
        self.assertEqual(dashboard['vehicules']['total_actifs'], 1)

    def test_alertes_excluent_vehicule_vendu(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="CES-D3", energie="diesel",
            statut=Vehicule.Statut.VENDU)
        actif = ActifFlotte.objects.create(company=self.co, vehicule=veh)
        today = datetime.date(2026, 7, 3)
        AssuranceVehicule.objects.create(
            company=self.co, actif_flotte=actif, assureur="Wafa",
            numero_police="P-2", date_debut=today,
            date_echeance=today + datetime.timedelta(days=5))
        alertes = alertes_echeances_reglementaires(self.co, today=today)
        actif_ids = [a['actif_flotte_id'] for a in alertes['alertes']]
        self.assertNotIn(actif.id, actif_ids)
