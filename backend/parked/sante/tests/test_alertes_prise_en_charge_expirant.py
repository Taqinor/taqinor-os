"""NTSAN31 — Alertes prise en charge expirant : une ``PriseEnCharge`` qui
expire dans 7 jours génère une notification unique (pas de doublon si la
tâche tourne plusieurs fois).
"""
import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.notifications.models import Notification
from apps.sante.models import Convention, Patient, PriseEnCharge
from apps.sante.tasks import alertes_prise_en_charge_expirant

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, **extra):
    return User.objects.create_user(
        username=username, password='x', company=company, **extra)


class AlertesPriseEnChargeExpirantTests(TestCase):
    def setUp(self):
        self.company = make_company('sante-pec-alert-co', 'Clinique Alerte PEC')
        self.admin = make_user(
            self.company, 'sante-pec-alert-admin', role_legacy='admin')
        self.patient = Patient.objects.create(company=self.company, nom='X')
        self.convention = Convention.objects.create(
            company=self.company, nom='CNOPS', type=Convention.Type.CNOPS)

    def _make_pec(self, date_expiration, statut=PriseEnCharge.Statut.ACCORDEE):
        return PriseEnCharge.objects.create(
            company=self.company, patient=self.patient,
            convention=self.convention,
            date_demande=timezone.localdate(),
            statut=statut, date_expiration=date_expiration)

    def test_notifies_pec_expiring_in_exactly_seven_days(self):
        cible = timezone.localdate() + dt.timedelta(days=7)
        self._make_pec(cible)

        result = alertes_prise_en_charge_expirant()

        self.assertEqual(result['prises_en_charge'], 1)
        self.assertGreaterEqual(result['notifications'], 1)
        self.assertTrue(
            Notification.objects.filter(
                event_type='warranty_expiring',
                recipient=self.admin).exists())

    def test_does_not_notify_pec_expiring_at_other_horizons(self):
        self._make_pec(timezone.localdate() + dt.timedelta(days=3))
        self._make_pec(timezone.localdate() + dt.timedelta(days=30))

        result = alertes_prise_en_charge_expirant()

        self.assertEqual(result['prises_en_charge'], 0)

    def test_no_duplicate_notification_when_run_twice_same_day(self):
        cible = timezone.localdate() + dt.timedelta(days=7)
        self._make_pec(cible)

        alertes_prise_en_charge_expirant()
        count_apres_premiere = Notification.objects.filter(
            event_type='warranty_expiring', recipient=self.admin).count()

        alertes_prise_en_charge_expirant()
        count_apres_deuxieme = Notification.objects.filter(
            event_type='warranty_expiring', recipient=self.admin).count()

        self.assertEqual(count_apres_premiere, count_apres_deuxieme)
