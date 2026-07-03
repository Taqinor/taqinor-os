"""Tests XFLT21 — Journal d'audit flotte.

Couvre :
- Service ``journaliser_diff_vehicule`` : un changement de statut trace une
  entrée ``ActiviteFlotte`` horodatée (ancien→nouveau) ; pas de changement =
  pas d'entrée.
- Service ``journaliser_diff_affectation`` : changement de conducteur/date_fin
  trace une entrée.
- Endpoint ``PATCH /vehicules/<id>/`` : modification directe du statut/km
  trace une entrée visible sur la fiche véhicule.
- Endpoint ``PATCH /affectations/<id>/`` : changement de conducteur trace
  une entrée.
- Endpoint ``GET /vehicules/<id>/activites/`` : historique non modifiable,
  visible du plus récent au plus ancien.
- Immuabilité : ``ActiviteFlotteSerializer`` n'expose aucun champ writable.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ActiviteFlotte, AffectationConducteur, Conducteur, Vehicule
from apps.flotte.services import (
    journaliser_diff_affectation,
    journaliser_diff_vehicule,
)

User = get_user_model()

URL_VEHICULES = "/api/django/flotte/vehicules/"
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


class JournaliserDiffVehiculeServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("act-svc", "Act Svc")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="ACT-1", energie="diesel",
            statut=Vehicule.Statut.ACTIF)

    def test_changement_statut_trace_entree(self):
        avant = {'statut': 'actif', 'kilometrage': 0, 'type_fiscal': '',
                 'modele_ref_id': None}
        apres = {
            'company': self.co, 'instance': self.veh,
            'statut': 'maintenance', 'kilometrage': 0, 'type_fiscal': '',
            'modele_ref_id': None,
        }
        crees = journaliser_diff_vehicule(avant, apres)
        self.assertEqual(len(crees), 1)
        entree = ActiviteFlotte.objects.first()
        self.assertEqual(entree.champ, 'statut')
        self.assertEqual(entree.ancienne_valeur, 'actif')
        self.assertEqual(entree.nouvelle_valeur, 'maintenance')

    def test_sans_changement_aucune_entree(self):
        avant = {'statut': 'actif', 'kilometrage': 0, 'type_fiscal': '',
                 'modele_ref_id': None}
        apres = {
            'company': self.co, 'instance': self.veh,
            'statut': 'actif', 'kilometrage': 0, 'type_fiscal': '',
            'modele_ref_id': None,
        }
        crees = journaliser_diff_vehicule(avant, apres)
        self.assertEqual(crees, [])
        self.assertEqual(ActiviteFlotte.objects.count(), 0)


class JournaliserDiffAffectationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("act-aff-svc", "Act Aff Svc")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="ACT-2", energie="diesel")
        self.cond1 = Conducteur.objects.create(company=self.co, nom="A")
        self.cond2 = Conducteur.objects.create(company=self.co, nom="B")
        self.affectation = AffectationConducteur.objects.create(
            company=self.co, conducteur=self.cond1, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1))

    def test_changement_conducteur_trace_entree(self):
        avant = {'conducteur_id': self.cond1.id, 'date_fin': None, 'actif': True}
        apres = {
            'company': self.co, 'vehicule': self.veh,
            'instance': self.affectation,
            'conducteur_id': self.cond2.id, 'date_fin': None, 'actif': True,
        }
        crees = journaliser_diff_affectation(avant, apres)
        self.assertEqual(len(crees), 1)
        entree = ActiviteFlotte.objects.first()
        self.assertEqual(entree.type_objet, ActiviteFlotte.TypeObjet.AFFECTATION)
        self.assertEqual(entree.vehicule_id, self.veh.id)


class VehiculeActivitesApiTests(TestCase):
    def setUp(self):
        self.co = make_company("act-api", "Act Api")
        self.user = make_user(self.co, "act-user")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="ACT-3", energie="diesel",
            statut=Vehicule.Statut.ACTIF)

    def test_patch_statut_trace_activite(self):
        resp = auth(self.user).patch(f"{URL_VEHICULES}{self.veh.id}/", {
            "statut": "maintenance",
        }, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)

        resp = auth(self.user).get(f"{URL_VEHICULES}{self.veh.id}/activites/")
        self.assertEqual(resp.status_code, 200)
        champs = [a['champ'] for a in resp.data]
        self.assertIn('statut', champs)

    def test_patch_sans_changement_aucune_activite(self):
        resp = auth(self.user).patch(f"{URL_VEHICULES}{self.veh.id}/", {
            "statut": "actif",
        }, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = auth(self.user).get(f"{URL_VEHICULES}{self.veh.id}/activites/")
        self.assertEqual(resp.data, [])

    def test_activites_tries_plus_recent_dabord(self):
        auth(self.user).patch(f"{URL_VEHICULES}{self.veh.id}/", {
            "statut": "maintenance",
        }, format="json")
        auth(self.user).patch(f"{URL_VEHICULES}{self.veh.id}/", {
            "statut": "actif",
        }, format="json")
        resp = auth(self.user).get(f"{URL_VEHICULES}{self.veh.id}/activites/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 2)
        # La plus récente en premier.
        self.assertEqual(resp.data[0]['nouvelle_valeur'], 'actif')


class AffectationActiviteApiTests(TestCase):
    def setUp(self):
        self.co = make_company("act-aff-api", "Act Aff Api")
        self.user = make_user(self.co, "act-aff-user")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="ACT-4", energie="diesel")
        self.cond1 = Conducteur.objects.create(company=self.co, nom="X")
        self.cond2 = Conducteur.objects.create(company=self.co, nom="Y")
        self.affectation = AffectationConducteur.objects.create(
            company=self.co, conducteur=self.cond1, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1))

    def test_patch_conducteur_trace_activite_sur_vehicule(self):
        resp = auth(self.user).patch(
            f"{URL_AFFECTATIONS}{self.affectation.id}/",
            {"conducteur": self.cond2.id}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)

        resp = auth(self.user).get(f"{URL_VEHICULES}{self.veh.id}/activites/")
        self.assertEqual(resp.status_code, 200)
        champs = [a['champ'] for a in resp.data]
        self.assertIn('conducteur_id', champs)


class ActiviteFlotteImmuableTests(TestCase):
    def test_serializer_tout_read_only(self):
        from apps.flotte.serializers import ActiviteFlotteSerializer
        serializer = ActiviteFlotteSerializer()
        for field_name in serializer.fields:
            self.assertTrue(
                serializer.fields[field_name].read_only,
                f"{field_name} devrait être read_only (immuabilité XFLT21)")
