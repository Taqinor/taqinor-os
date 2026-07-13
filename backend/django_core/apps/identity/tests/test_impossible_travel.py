"""NTSEC12 — Tests détection « impossible travel ».

Garanties : sans base géo le module est INERTE (no-op) ; deux connexions
géographiquement incompatibles en peu de temps lèvent une ``SECURITY_ALERT`` ;
jamais bloquant ; une vitesse plausible ne lève rien.
"""
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from authentication.models import UserSession
from testkit.factories import CompanyFactory, UserFactory

from apps.identity import anomaly

# Casablanca et Tokyo — ~11 000 km : impossibles à 1 h d'intervalle.
CASA = (33.57, -7.59)
TOKYO = (35.68, 139.69)


class ImpossibleTravelTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company, username='trav')

    def _prior_session(self, ip, minutes_ago):
        s = UserSession.objects.create(
            company=self.company, user=self.user, jti='j', ip_address=ip,
            revoked=False)
        UserSession.objects.filter(pk=s.pk).update(
            last_seen_at=timezone.now() - timedelta(minutes=minutes_ago))
        return s

    def test_no_geo_db_is_noop(self):
        # _geolocate renvoie None (pas de base) → aucune alerte, aucun crash.
        self._prior_session('1.1.1.1', 30)
        with mock.patch.object(anomaly, '_geolocate', return_value=None):
            self.assertIsNone(
                anomaly.detect_impossible_travel(self.user, '2.2.2.2'))

    def test_impossible_travel_raises_alert(self):
        self._prior_session('1.1.1.1', 60)
        before = AuditLog.objects.filter(
            action=AuditLog.Action.SECURITY_ALERT).count()

        def fake_geo(ip):
            return TOKYO if ip == '2.2.2.2' else CASA

        with mock.patch.object(anomaly, '_geolocate', side_effect=fake_geo):
            res = anomaly.detect_impossible_travel(self.user, '2.2.2.2')
        self.assertIsNotNone(res)
        self.assertGreater(res['speed_kmh'], anomaly.SPEED_THRESHOLD_KMH)
        after = AuditLog.objects.filter(
            action=AuditLog.Action.SECURITY_ALERT).count()
        self.assertEqual(after, before + 1)

    def test_plausible_travel_no_alert(self):
        # Même ville, 1 h plus tard : vitesse faible → aucune alerte.
        self._prior_session('1.1.1.1', 60)

        def fake_geo(ip):
            return (CASA[0] + 0.01, CASA[1] + 0.01) if ip == '2.2.2.2' else CASA

        with mock.patch.object(anomaly, '_geolocate', side_effect=fake_geo):
            self.assertIsNone(
                anomaly.detect_impossible_travel(self.user, '2.2.2.2'))

    def test_no_prior_session_noop(self):
        with mock.patch.object(anomaly, '_geolocate', return_value=CASA):
            self.assertIsNone(
                anomaly.detect_impossible_travel(self.user, '2.2.2.2'))
