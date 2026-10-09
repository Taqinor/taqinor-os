"""ACHT75 (C-ACHT-071) — l'échéance de calibration crée réellement une
Notification `outillage_calibration_proche` : au `calibrer` (échéance à 30
jours ou moins) et par la tâche quotidienne `outillage.calibrations_a_echeance`
(sociétés ACTIVES seulement, aucun doublon au 2e passage).

Rejoue COUT-6 : `EventType contient ? False`, `Notifications créées 0`.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.outillage.tests_acht75_notification_calibration"
"""
import datetime

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType
from apps.outillage import tasks
from apps.outillage.models import Outillage

User = get_user_model()
EVT = 'outillage_calibration_proche'


class NotificationCalibrationTests(TestCase):
    def setUp(self):
        self.jour = datetime.date.today()
        self.company = Company.objects.create(nom='ACHT75', slug='acht75-co')
        self.suspendue = Company.objects.create(
            nom='ACHT75 S', slug='acht75-susp')
        Company.objects.filter(pk=self.suspendue.pk).update(actif=False)
        self.admin = User.objects.create_user(
            username='admin-acht75', password='x', company=self.company,
            role_legacy='admin')
        self.admin_susp = User.objects.create_user(
            username='admin-acht75-s', password='x', company=self.suspendue,
            role_legacy='admin')
        self.proche = self._outil(self.company, 'Proche', 20)
        self.loin = self._outil(self.company, 'Loin', 60)
        self.suspendu = self._outil(self.suspendue, 'Suspendu', 20)

    def _outil(self, company, nom, jours):
        """Outil dont la prochaine calibration tombe dans `jours` jours."""
        echeance = self.jour + datetime.timedelta(days=jours)
        derniere = echeance - relativedelta(months=12)
        return Outillage.objects.create(
            company=company, nom=nom, intervalle_calibration_mois=12,
            date_derniere_calibration=derniere)

    def _nb(self, company):
        return Notification.objects.filter(
            company=company, event_type=EVT).count()

    def test_event_type_declare(self):
        self.assertIn(EVT, EventType.values)

    def test_calibrer_notifie(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        neuf = Outillage.objects.create(
            company=self.company, nom='Neuf', intervalle_calibration_mois=12)
        # Calibration à J − 11 mois : prochaine échéance à ~ 25 jours.
        date = self.jour - relativedelta(months=11) + datetime.timedelta(
            days=-5)
        r = api.post(f'/api/django/outillage/outils/{neuf.id}/calibrer/',
                     {'date_calibration': str(date)}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._nb(self.company), 1)

    def test_tache_quotidienne_sans_doublon_ni_suspendue(self):
        res = tasks.calibrations_a_echeance()
        self.assertEqual(res['outils'], 1)           # Proche seulement
        self.assertEqual(self._nb(self.company), 1)
        self.assertEqual(self._nb(self.suspendue), 0)
        tasks.calibrations_a_echeance()
        self.assertEqual(self._nb(self.company), 1)  # aucun doublon
