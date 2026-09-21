"""Tests NTAGR14 — Coût d'irrigation agrégé dans le coût de campagne.

Couvre : ``cout_total_campagne`` inclut l'irrigation payante (réseau/gasoil)
de la fenêtre de campagne, l'irrigation solaire reste à coût variable nul
(exclue de la somme, comptée séparément en volume), et un relevé hors
fenêtre de campagne n'est pas compté."""
from decimal import Decimal

from django.test import TestCase

from apps.agriculture.models import CampagneCulturale, Exploitation, Parcelle, PointIrrigation
from apps.agriculture.selectors import (
    cout_irrigation_campagne, cout_total_campagne,
    volume_irrigation_solaire_campagne,
)

from .helpers import make_company


class CoutIrrigationCampagneTests(TestCase):
    def setUp(self):
        self.co = make_company('agr-ci-a', 'Ferme Coût Irrigation')
        exploitation = Exploitation.objects.create(company=self.co, nom='Domaine')
        self.parcelle = Parcelle.objects.create(
            company=self.co, exploitation=exploitation, nom='Parcelle 1')
        self.campagne = CampagneCulturale.objects.create(
            company=self.co, parcelle=self.parcelle, culture='Blé',
            date_semis='2026-01-01', date_recolte_prevue='2026-06-30')

    def test_cout_total_campagne_includes_paid_irrigation(self):
        point = PointIrrigation.objects.create(
            company=self.co, parcelle=self.parcelle, type_source='reseau')
        point.releves.create(
            company=self.co, date='2026-03-01', volume_m3=Decimal('10'),
            cout_energie_mad=Decimal('80.00'))
        self.campagne.etapes.create(
            company=self.co, type_etape='semis', date='2026-01-05',
            cout_mad=Decimal('50.00'))

        self.assertEqual(
            cout_irrigation_campagne(self.campagne), Decimal('80.00'))
        self.assertEqual(
            cout_total_campagne(self.campagne), Decimal('130.00'))

    def test_solar_irrigation_excluded_from_paid_cost_but_volume_tracked(self):
        point = PointIrrigation.objects.create(
            company=self.co, parcelle=self.parcelle,
            type_source='pompage_solaire', installation_id=1)
        point.releves.create(
            company=self.co, date='2026-03-01', volume_m3=Decimal('25'))

        self.assertEqual(cout_irrigation_campagne(self.campagne), Decimal('0'))
        self.assertEqual(cout_total_campagne(self.campagne), Decimal('0'))
        self.assertEqual(
            volume_irrigation_solaire_campagne(self.campagne), Decimal('25'))

    def test_releve_outside_campagne_window_not_counted(self):
        point = PointIrrigation.objects.create(
            company=self.co, parcelle=self.parcelle, type_source='reseau')
        # Hors fenêtre (avant le semis) — ne doit pas être compté.
        point.releves.create(
            company=self.co, date='2025-12-01', volume_m3=Decimal('5'),
            cout_energie_mad=Decimal('30.00'))

        self.assertEqual(cout_irrigation_campagne(self.campagne), Decimal('0'))

    def test_releve_without_cost_ignored_not_zero_conflictual(self):
        point = PointIrrigation.objects.create(
            company=self.co, parcelle=self.parcelle, type_source='reseau')
        point.releves.create(
            company=self.co, date='2026-03-01', volume_m3=Decimal('5'))
        other = PointIrrigation.objects.create(
            company=self.co, parcelle=self.parcelle, type_source='reseau')
        other.releves.create(
            company=self.co, date='2026-03-02', volume_m3=Decimal('3'),
            cout_energie_mad=Decimal('20.00'))

        self.assertEqual(cout_irrigation_campagne(self.campagne), Decimal('20.00'))
