"""Tests ZCTR11 — Enrichissement fiscal du catalogue de modèles véhicule.

Couvre :
- ``ModeleVehicule.valeur_residuelle`` / ``pct_charges_non_deductibles``
  (validation 0-100, modèle + serializer).
- ``Vehicule.carte_mobilite`` affichée + ``Vehicule.valeur_residuelle`` /
  ``pct_charges_non_deductibles`` pré-remplis à la sélection du modèle (via
  ``services.prefill_depuis_modele``, existant, étendu) SANS écraser une
  saisie.
- Le TCO (FLOTTE31, ``tco_vehicule``) lit ``pct_charges_non_deductibles`` et
  calcule la part non déductible (indicative, hors régression pour les
  véhicules sans pourcentage renseigné).
- La synthèse TVA carburant (XFLT8, ``synthese_tva_carburant``) expose
  ``par_vehicule`` avec la part de carburant non déductible.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ModeleVehicule, PleinCarburant, Vehicule
from apps.flotte.selectors import synthese_tva_carburant, tco_vehicule
from apps.flotte.services import prefill_depuis_modele

User = get_user_model()

URL_VEHICULES = '/api/django/flotte/vehicules/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_modele(company, **kwargs):
    defaults = dict(
        marque='Renault', modele='Kangoo', energie='diesel',
        valeur_residuelle=50000, pct_charges_non_deductibles=25)
    defaults.update(kwargs)
    return ModeleVehicule.objects.create(company=company, **defaults)


class ModeleVehiculeValidationTests(TestCase):
    def setUp(self):
        self.co = make_company('zctr11-model', 'ZCTR11 Model')

    def test_pct_valide_ok(self):
        modele = ModeleVehicule(
            company=self.co, marque='M', modele='X',
            pct_charges_non_deductibles=50)
        modele.full_clean()  # ne lève pas.

    def test_pct_hors_bornes_rejete(self):
        modele = ModeleVehicule(
            company=self.co, marque='M', modele='X',
            pct_charges_non_deductibles=150)
        with self.assertRaises(ValidationError):
            modele.full_clean()

    def test_pct_negatif_rejete(self):
        modele = ModeleVehicule(
            company=self.co, marque='M', modele='X',
            pct_charges_non_deductibles=-1)
        with self.assertRaises(ValidationError):
            modele.full_clean()

    def test_pct_vide_ok(self):
        modele = ModeleVehicule(company=self.co, marque='M', modele='X')
        modele.full_clean()


class VehiculePctValidationTests(TestCase):
    def setUp(self):
        self.co = make_company('zctr11-veh', 'ZCTR11 Veh')

    def test_pct_hors_bornes_rejete(self):
        veh = Vehicule(
            company=self.co, immatriculation='V1', energie='diesel',
            pct_charges_non_deductibles=101)
        with self.assertRaises(ValidationError):
            veh.full_clean()


class PrefillEnrichissementFiscalTests(TestCase):
    def setUp(self):
        self.co = make_company('zctr11-prefill', 'ZCTR11 Prefill')
        self.modele = make_modele(self.co)

    def test_prefill_valeur_residuelle_et_pct(self):
        data = {}
        prefill_depuis_modele(data, self.modele)
        self.assertEqual(data['valeur_residuelle'], 50000)
        self.assertEqual(data['pct_charges_non_deductibles'], 25)

    def test_prefill_ne_jamais_ecraser_saisie(self):
        data = {'pct_charges_non_deductibles': 10}
        prefill_depuis_modele(data, self.modele)
        self.assertEqual(data['pct_charges_non_deductibles'], 10)
        # Le champ absent, lui, est pré-rempli.
        self.assertEqual(data['valeur_residuelle'], 50000)


class VehiculeCreationDepuisModeleApiTests(TestCase):
    def setUp(self):
        self.co = make_company('zctr11-api', 'ZCTR11 Api')
        self.user = make_user(self.co, 'zctr11-user')
        self.modele = make_modele(self.co)

    def test_creation_prefill_valeur_residuelle_et_pct(self):
        resp = auth(self.user).post(URL_VEHICULES, {
            'immatriculation': 'ZCTR11-1',
            'modele_ref': self.modele.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(float(resp.data['valeur_residuelle']), 50000.0)
        self.assertEqual(
            float(resp.data['pct_charges_non_deductibles']), 25.0)

    def test_carte_mobilite_affichee(self):
        resp = auth(self.user).post(URL_VEHICULES, {
            'immatriculation': 'ZCTR11-2',
            'carte_mobilite': 'CM-00123',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['carte_mobilite'], 'CM-00123')

    def test_pct_hors_bornes_rejete_par_api(self):
        resp = auth(self.user).post(URL_VEHICULES, {
            'immatriculation': 'ZCTR11-3',
            'pct_charges_non_deductibles': 150,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


class TcoPartNonDeductibleTests(TestCase):
    def setUp(self):
        self.co = make_company('zctr11-tco', 'ZCTR11 Tco')

    def test_tco_signale_part_non_deductible(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation='TCO-1', energie='diesel',
            pct_charges_non_deductibles=20)
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh, date_plein=datetime.date.today(),
            kilometrage=1000, quantite=50, prix_total=1000)
        result = tco_vehicule(self.co, veh.id)
        self.assertEqual(result['pct_charges_non_deductibles'], 20.0)
        self.assertEqual(
            result['part_charges_non_deductibles'],
            round(result['cout_total'] * 0.20, 2))

    def test_tco_sans_pct_renseigne_aucune_regression(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation='TCO-2', energie='diesel')
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh, date_plein=datetime.date.today(),
            kilometrage=1000, quantite=50, prix_total=1000)
        result = tco_vehicule(self.co, veh.id)
        self.assertIsNone(result['pct_charges_non_deductibles'])
        self.assertIsNone(result['part_charges_non_deductibles'])
        # Le cout_total reste identique au comportement historique.
        self.assertEqual(result['cout_total'], 1000.0)


class SyntheseTvaParVehiculeTests(TestCase):
    def setUp(self):
        self.co = make_company('zctr11-tva', 'ZCTR11 Tva')

    def test_synthese_tva_par_vehicule_signale_pct(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation='TVA-1', energie='diesel',
            pct_charges_non_deductibles=30)
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh, date_plein=datetime.date(2026, 6, 1),
            kilometrage=1000, quantite=50, prix_total=1000, montant_tva=200)
        result = synthese_tva_carburant(
            self.co, periode=(datetime.date(2026, 6, 1),
                              datetime.date(2026, 6, 30)))
        par_veh = {r['vehicule_id']: r for r in result['par_vehicule']}
        self.assertIn(veh.id, par_veh)
        self.assertEqual(par_veh[veh.id]['pct_charges_non_deductibles'], 30.0)
        self.assertEqual(
            par_veh[veh.id]['montant_carburant_non_deductible'], 300.0)

    def test_vehicule_sans_pct_absent_du_rapport(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation='TVA-2', energie='diesel')
        PleinCarburant.objects.create(
            company=self.co, vehicule=veh, date_plein=datetime.date(2026, 6, 1),
            kilometrage=1000, quantite=50, prix_total=1000, montant_tva=200)
        result = synthese_tva_carburant(
            self.co, periode=(datetime.date(2026, 6, 1),
                              datetime.date(2026, 6, 30)))
        par_veh_ids = {r['vehicule_id'] for r in result['par_vehicule']}
        self.assertNotIn(veh.id, par_veh_ids)
