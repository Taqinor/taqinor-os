"""Tests FLOTTE32 — Pool de véhicules & demandes.

Couvre :
- Modèle ``DemandeVehicule`` :
  - création simple + valeurs par défaut (statut=demandee) ;
  - validations ``clean`` (demandeur / décideur / véhicule d'une autre société,
    fin souhaitée < début).
- Service ``decider_demande_vehicule`` :
  - approbation (attribue un véhicule, pose décideur + date) ;
  - refus (aucune attribution conservée) ;
  - statut cible invalide / véhicule d'une autre société → ValueError.
- Selector ``demandes_vehicule_de_la_societe`` : scope société + filtres.
- Endpoints API ``/demandes-vehicule/`` :
  - création scopée société + demandeur posé serveur (jamais du body) ;
  - actions ``approuver`` / ``refuser`` (responsable/admin).
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import DemandeVehicule, Vehicule
from apps.flotte.selectors import demandes_vehicule_de_la_societe
from apps.flotte.services import decider_demande_vehicule

User = get_user_model()

URL = "/api/django/flotte/demandes-vehicule/"


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


D1 = datetime.date(2026, 6, 1)
D2 = datetime.date(2026, 6, 5)


class DemandeVehiculeModelTests(TestCase):
    def setUp(self):
        self.co = make_company("dem-model", "Dem Model")
        self.demandeur = make_user(self.co, "dem-u", "normal")

    def test_creation_defaults(self):
        d = DemandeVehicule.objects.create(
            company=self.co, demandeur=self.demandeur, besoin="Tournée",
            date_debut_souhaitee=D1, date_fin_souhaitee=D2)
        self.assertEqual(d.statut, DemandeVehicule.Statut.DEMANDEE)
        self.assertIsNone(d.vehicule_attribue_id)

    def test_demandeur_autre_societe_rejete(self):
        autre = make_company("dem-model-b", "B")
        u_b = make_user(autre, "u-b", "normal")
        d = DemandeVehicule(
            company=self.co, demandeur=u_b, besoin="x",
            date_debut_souhaitee=D1, date_fin_souhaitee=D2)
        with self.assertRaises(ValidationError):
            d.full_clean()

    def test_fin_avant_debut_rejetee(self):
        d = DemandeVehicule(
            company=self.co, demandeur=self.demandeur, besoin="x",
            date_debut_souhaitee=D2, date_fin_souhaitee=D1)
        with self.assertRaises(ValidationError):
            d.full_clean()


class DeciderDemandeServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("dem-svc", "Dem Svc")
        self.demandeur = make_user(self.co, "dem-svc-u", "normal")
        self.resp = make_user(self.co, "dem-svc-r", "admin")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="DEM-1", energie="diesel")
        self.demande = DemandeVehicule.objects.create(
            company=self.co, demandeur=self.demandeur, besoin="Tournée",
            date_debut_souhaitee=D1, date_fin_souhaitee=D2)

    def test_approbation(self):
        d = decider_demande_vehicule(
            self.demande, statut=DemandeVehicule.Statut.APPROUVEE,
            decide_par=self.resp, vehicule=self.veh, motif="OK")
        self.assertEqual(d.statut, DemandeVehicule.Statut.APPROUVEE)
        self.assertEqual(d.vehicule_attribue_id, self.veh.id)
        self.assertEqual(d.decide_par_id, self.resp.id)
        self.assertIsNotNone(d.date_decision)

    def test_refus_aucune_attribution(self):
        d = decider_demande_vehicule(
            self.demande, statut=DemandeVehicule.Statut.REFUSEE,
            decide_par=self.resp, vehicule=self.veh, motif="Indispo")
        self.assertEqual(d.statut, DemandeVehicule.Statut.REFUSEE)
        self.assertIsNone(d.vehicule_attribue_id)

    def test_statut_invalide(self):
        with self.assertRaises(ValueError):
            decider_demande_vehicule(
                self.demande, statut=DemandeVehicule.Statut.DEMANDEE,
                decide_par=self.resp)

    def test_vehicule_autre_societe(self):
        autre = make_company("dem-svc-b", "B")
        veh_b = Vehicule.objects.create(
            company=autre, immatriculation="B", energie="diesel")
        with self.assertRaises(ValueError):
            decider_demande_vehicule(
                self.demande, statut=DemandeVehicule.Statut.APPROUVEE,
                decide_par=self.resp, vehicule=veh_b)


class DemandeVehiculeSelectorTests(TestCase):
    def test_scope_et_filtres(self):
        co = make_company("dem-sel", "Sel")
        autre = make_company("dem-sel-b", "Sel B")
        u = make_user(co, "dem-sel-u", "normal")
        u_b = make_user(autre, "dem-sel-u-b", "normal")
        DemandeVehicule.objects.create(
            company=co, demandeur=u, besoin="x",
            date_debut_souhaitee=D1, date_fin_souhaitee=D2)
        DemandeVehicule.objects.create(
            company=autre, demandeur=u_b, besoin="y",
            date_debut_souhaitee=D1, date_fin_souhaitee=D2)
        self.assertEqual(demandes_vehicule_de_la_societe(co).count(), 1)
        self.assertEqual(
            demandes_vehicule_de_la_societe(
                co, statut="demandee").count(), 1)


class DemandeVehiculeApiTests(TestCase):
    def setUp(self):
        self.co = make_company("dem-api", "Dem Api")
        self.admin = make_user(self.co, "dem-admin", "admin")
        self.user = make_user(self.co, "dem-user", "normal")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="DEM-API", energie="diesel")

    def test_create_demandeur_pose_serveur(self):
        api = auth(self.user)
        resp = api.post(URL, {
            "besoin": "Déplacement client",
            "date_debut_souhaitee": "2026-06-01",
            "date_fin_souhaitee": "2026-06-05",
            "demandeur": self.admin.id,  # tentative d'usurpation ignorée.
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        d = DemandeVehicule.objects.get(id=resp.data["id"])
        self.assertEqual(d.company_id, self.co.id)
        self.assertEqual(d.demandeur_id, self.user.id)

    def test_action_approuver(self):
        d = DemandeVehicule.objects.create(
            company=self.co, demandeur=self.user, besoin="x",
            date_debut_souhaitee=D1, date_fin_souhaitee=D2)
        api = auth(self.admin)
        resp = api.post(
            URL + f"{d.id}/approuver/",
            {"vehicule_attribue": self.veh.id, "motif_decision": "OK"},
            format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        d.refresh_from_db()
        self.assertEqual(d.statut, DemandeVehicule.Statut.APPROUVEE)
        self.assertEqual(d.vehicule_attribue_id, self.veh.id)
        self.assertEqual(d.decide_par_id, self.admin.id)

    def test_action_refuser(self):
        d = DemandeVehicule.objects.create(
            company=self.co, demandeur=self.user, besoin="x",
            date_debut_souhaitee=D1, date_fin_souhaitee=D2)
        api = auth(self.admin)
        resp = api.post(
            URL + f"{d.id}/refuser/", {"motif_decision": "Indispo"},
            format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        d.refresh_from_db()
        self.assertEqual(d.statut, DemandeVehicule.Statut.REFUSEE)
