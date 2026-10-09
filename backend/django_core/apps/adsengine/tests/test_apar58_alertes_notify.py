"""APAR58 — les alertes du moteur de publicité passent par ``notify_many`` :
type ``adsengine_alert`` accepté, report hors fenêtre."""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.adsengine import alerts
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType


class AlertesViaNotifyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR58 Co', slug='apar58')
        U = get_user_model()
        U.objects.create_user(
            username='a58_admin', password='x', company=self.company,
            role_legacy='admin')
        U.objects.create_user(
            username='a58_resp', password='x', company=self.company,
            role_legacy='responsable')

    def test_type_enregistre(self):
        self.assertIn('adsengine_alert', EventType.values)

    def test_alerte_creee_pour_chaque_destinataire(self):
        alerts.create_alert(
            self.company, alert_type='guardrail', message='Garde-fou')
        rows = Notification.objects.filter(event_type='adsengine_alert')
        self.assertEqual(
            sorted(r.recipient.username for r in rows),
            ['a58_admin', 'a58_resp'])

    def test_passe_par_notify_many(self):
        with mock.patch('apps.notifications.services.notify_many') as nm:
            alerts.create_alert(
                self.company, alert_type='guardrail', message='X')
        self.assertTrue(nm.called)
        self.assertEqual(nm.call_args[0][1], 'adsengine_alert')

    @override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True)
    def test_hors_fenetre_reporte(self):
        ouverture = datetime.datetime(
            2030, 1, 7, 8, 30, tzinfo=datetime.timezone.utc)
        fermee = mock.Mock(ouverte=False, prochaine_ouverture=ouverture)
        with mock.patch(
                'apps.notifications.selectors.fenetre_notifications',
                return_value=fermee):
            alerts.create_alert(
                self.company, alert_type='guardrail', message='Nuit')
        rows = list(Notification.objects.filter(event_type='adsengine_alert'))
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row.programmee_pour, ouverture)
