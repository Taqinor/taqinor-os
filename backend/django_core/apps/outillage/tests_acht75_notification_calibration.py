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

    def test_in_app_coupe_un_seul_email_par_echeance(self):
        """ASOC32 (C-ASOC-142) — in-app coupé, e-mail actif : un seul e-mail
        par échéance sur deux passages ; nouvelle échéance ⇒ un de plus."""
        from unittest import mock

        from apps.crm import horaires
        from apps.notifications.models import (
            MarqueurEmissionBalayage, NotificationPreference)
        # notify() juge les heures calmes sur l'horloge : mardi 10 h (ouvré).
        mardi = datetime.datetime(2026, 9, 1, 10, 0, tzinfo=horaires.CASABLANCA)
        ouvre = mock.patch('apps.notifications.services.timezone.now',
                           return_value=mardi)
        tech = User.objects.create_user(
            username='tech-asoc32', password='x', company=self.company,
            email='tech-asoc32@example.ma')
        NotificationPreference.objects.create(
            user=tech, company=self.company, event_type=EVT,
            in_app=False, email=True)
        self.proche.date_derniere_calibration = (
            self.jour + datetime.timedelta(days=7) - relativedelta(months=12))
        self.proche.save()
        self.proche.refresh_from_db()
        with mock.patch('apps.notifications.services._dispatch_email',
                        return_value=True) as envoi, ouvre, \
                self.captureOnCommitCallbacks(execute=True):
            for _passage in range(2):  # deux jours de suite
                tasks.notifier_calibration_proche(self.proche, [tech])
        self.assertEqual(envoi.call_count, 1)
        self.assertEqual(MarqueurEmissionBalayage.objects.filter(
            company=self.company, cle=f'outil:{self.proche.pk}:{tech.pk}').count(), 1)
        self.proche.date_derniere_calibration += relativedelta(months=1)
        self.proche.save()
        self.proche.refresh_from_db()
        with mock.patch('apps.notifications.services._dispatch_email',
                        return_value=True) as envoi, ouvre, \
                self.captureOnCommitCallbacks(execute=True):
            tasks.notifier_calibration_proche(self.proche, [tech])
        self.assertEqual(envoi.call_count, 1)
