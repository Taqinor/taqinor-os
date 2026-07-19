"""PUB102 — Tests de la vigie d'EOL de la version Graph API.

Prouve : le calcul PUR des mois avant l'EOL (sortie + ~24 mois), l'alerte quand
une version proche de l'EOL est simulée, l'absence d'alerte loin de l'EOL, la
dédup, et l'absence de tout bump automatique (GRAPH_VERSION jamais modifiée).
"""
import datetime

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import api_version
from apps.adsengine.models import EngineAlert
from apps.adsengine.rules import SEVERITY_CRITICAL, SEVERITY_WARNING
from apps.adsengine.tasks import check_graph_version_eol


class MonthsUntilEolTests(TestCase):
    def test_eol_date_is_release_plus_lifetime(self):
        eol = api_version.graph_version_eol_date()
        # 2025-07 + 24 mois = 2027-07.
        self.assertEqual((eol.year, eol.month), (2027, 7))

    def test_months_positive_before_eol(self):
        # Un an avant l'EOL simulée.
        today = datetime.date(2026, 7, 1)
        self.assertEqual(api_version.months_until_graph_eol(today=today), 12)

    def test_months_negative_after_eol(self):
        today = datetime.date(2027, 10, 1)
        self.assertLess(api_version.months_until_graph_eol(today=today), 0)


class CheckGraphEolTests(TestCase):
    def setUp(self):
        # Une société active est nécessaire (l'alerte est posée sur la première).
        self.company = Company.objects.create(nom='Eol Co', slug='eol-co')

    def test_alert_when_near_eol(self):
        # ~2 mois avant l'EOL (2027-07) → sous le seuil (4 mois) → alerte warning.
        alert = check_graph_version_eol(today=datetime.date(2027, 5, 15))
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, SEVERITY_WARNING)
        self.assertEqual(alert.detail['kind'], 'graph_version_eol')
        self.assertIn(api_version.GRAPH_VERSION, alert.entity_key)

    def test_critical_when_past_eol(self):
        alert = check_graph_version_eol(today=datetime.date(2027, 9, 1))
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, SEVERITY_CRITICAL)

    def test_no_alert_far_from_eol(self):
        alert = check_graph_version_eol(today=datetime.date(2025, 8, 1))
        self.assertIsNone(alert)
        self.assertEqual(EngineAlert.objects.count(), 0)

    def test_dedup(self):
        check_graph_version_eol(today=datetime.date(2027, 5, 15))
        check_graph_version_eol(today=datetime.date(2027, 5, 20))
        self.assertEqual(EngineAlert.objects.filter(
            entity_key__startswith='graph_eol:').count(), 1)

    def test_never_auto_bumps_version(self):
        before = api_version.GRAPH_VERSION
        check_graph_version_eol(today=datetime.date(2027, 9, 1))
        self.assertEqual(api_version.GRAPH_VERSION, before)
