# -*- coding: utf-8 -*-
"""CIQ141 — l'orchestrateur C&I lit le relevé de visite VALIDÉ (façade
``apps.visites.selectors.releve_ci_pour_lead``, jamais mockée) : vérifié par
la visite > déclaré > absent.

Catalogue de test et PVGIS figé : ceux des cas de référence CIQ122 (aucun
réseau). Le sélecteur visites et le lead sont réels (base de test).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq141_releve_visite"
"""
import datetime
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.crm.models import Lead
from apps.ventes import roof_load
from apps.ventes.domain import etude_ci
from apps.ventes.tests.test_ciq122_cas_reference import CATALOGUE_TEST, PVGIS
from apps.visites.models import VisiteTerrain
from authentication.models import Company

ZONE = {'id': 'z1', 'libelle': 'Atelier nord', 'longueur_m': 40, 'largeur_m': 18,
        'pente_deg': 8, 'orientation': 'sud', 'couverture': 'bac_acier',
        'structure': 'portique', 'surface_utile_m2': None,
        'charge_admissible_declaree_kg_m2': 25,
        'charge_admissible_piece': 'rapport bureau de contrôle n° 2026-118'}
CORPS = {'mode': 'commercial', 'tension': 'bt', 'phases': 'tri',
         'site': {'ville': 'Casablanca', 'lat': 33.57, 'lon': -7.59},
         'tarif': {'contrat': 'bt_patente'},
         'consommation': {'kwh_mensuels': [6000] * 12},
         'rythme': {'categorie_commerciale': 'bureau'},
         'taille_explicite_kwc': 40}


class ReleveVisiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.create(nom='CIQ141 Co', slug='ciq141-co')
        cls.lead = Lead.objects.create(company=cls.co, nom='Atelier', ville='Casablanca',
                                       type_installation='commercial')

    def _visite(self, statut=VisiteTerrain.Statut.VALIDEE, mesures=None):
        base = {
            'toiture_ci': {'zones_toiture': [ZONE]},
            'cheminement': {'trajets': [
                {'libelle': 'a', 'longueur_dc_m': 50, 'longueur_ac_m': None},
                {'libelle': 'b', 'longueur_dc_m': 35, 'longueur_ac_m': 40}]},
        }
        base.update(mesures or {})
        return VisiteTerrain.objects.create(company=self.co, lead=self.lead, gabarit='ci',
                                            statut=statut, mesures=base)

    def _etudier(self, corps=None, lead=None):
        with mock.patch.object(etude_ci, 'lire_catalogue_ci', return_value=CATALOGUE_TEST), \
                mock.patch.object(etude_ci, '_reglages_societe', return_value=None), \
                mock.patch.object(etude_ci, '_aujourdhui',
                                  return_value=datetime.date(2026, 10, 5)), \
                mock.patch.object(etude_ci, 'lire_production', return_value=(
                    PVGIS['productible_mensuel'], PVGIS['formes_saison'], PVGIS['source'])):
            return etude_ci.etudier_ci(self.co, dict(corps or CORPS),
                                       lead=self.lead if lead is None else lead)

    @staticmethod
    def _ligne(etude, role):
        return next((ligne for ligne in etude['composition']['lignes']
                     if ligne['role'] == role), None)

    def test_visite_validee_longueurs_sommees_et_metre_change(self):
        sans = self._etudier()
        self._visite()
        avec = self._etudier()
        dc = avec['entrees_resolues']['longueur_dc_m']
        self.assertEqual(dc['valeur'], 85)
        self.assertEqual(dc['provenance']['origine'], 'mesure_visite')
        self.assertEqual(avec['entrees_resolues']['longueur_ac_m']['valeur'], 40)
        self.assertIsNone(self._ligne(sans, 'cable_ac')['quantite'])
        self.assertEqual(self._ligne(avec, 'cable_ac')['quantite'], 40)
        self.assertNotIn('longueurs_non_relevees', [a['code'] for a in avec['alertes']])

    def test_visite_non_validee_entrees_inchangees_et_alerte(self):
        self._visite(statut=VisiteTerrain.Statut.TERMINEE)
        etude = self._etudier()
        self.assertNotIn('longueur_dc_m', etude['entrees_resolues'])
        self.assertIn('longueurs_non_relevees', [a['code'] for a in etude['alertes']])

    def test_charge_admissible_de_la_zone_et_sa_source(self):
        self._visite()
        with mock.patch.object(roof_load, 'verifier_charge_toiture',
                               wraps=roof_load.verifier_charge_toiture) as espion:
            etude = self._etudier()
        kwargs = espion.call_args.kwargs
        self.assertEqual(kwargs['charge_admissible_kg_m2'], 25)
        self.assertIn('rapport bureau de contrôle', kwargs['charge_admissible_source'])
        self.assertEqual(etude['entrees_resolues']['charge_admissible_kg_m2']['valeur'], 25)

    def test_mesure_non_relevee_alerte_sans_nombre(self):
        self._visite(mesures={'cheminement': {
            'trajets': [], '_non_releves': {'trajets': 'acces_refuse'}}})
        etude = self._etudier()
        self.assertNotIn('longueur_dc_m', etude['entrees_resolues'])
        alertes = [a for a in etude['alertes'] if a['code'] == 'mesure_non_verifiee']
        self.assertTrue(any('acces_refuse' in a['message'] for a in alertes))

    def test_devis_residentiel_aucun_appel_au_selecteur_visites(self):
        lead = Lead.objects.create(company=self.co, nom='Villa', ville='Casablanca',
                                   type_installation='residentiel',
                                   conso_mensuelle_kwh=Decimal('400'))
        with mock.patch('apps.visites.selectors.releve_ci_pour_lead') as espion:
            with self.assertNumQueries(0):
                self._etudier(corps={'mode': 'residentiel'}, lead=lead)
        espion.assert_not_called()
