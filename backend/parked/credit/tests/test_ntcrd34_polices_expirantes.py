"""NTCRD34 — alerte polices d'assurance proches de l'échéance (J-30) : une
police expirant dans 25 jours génère une notification unique."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.credit.models import PoliceAssuranceCredit
from apps.credit.tasks import alerter_polices_expirantes
from apps.notifications.models import Notification

User = get_user_model()


def make_company(slug='ntcrd34-co', nom='NTCRD34 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD34PolicesExpirantesTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ntcrd34_admin', password='x', role_legacy='admin',
            company=self.company)

    def test_alert_for_police_expiring_soon_once(self):
        today = timezone.localdate()
        PoliceAssuranceCredit.objects.create(
            company=self.company, assureur='Allianz Trade',
            numero_police='AT-1', actif=True,
            date_fin=today + timedelta(days=25))
        emises = alerter_polices_expirantes(today=today)
        self.assertEqual(emises, 1)
        self.assertTrue(
            Notification.objects.filter(recipient=self.admin).exists())
        count = Notification.objects.filter(recipient=self.admin).count()
        # Second run same day → dedup, no new notification.
        self.assertEqual(alerter_polices_expirantes(today=today), 0)
        self.assertEqual(
            Notification.objects.filter(recipient=self.admin).count(), count)

    def test_no_alert_for_far_police(self):
        today = timezone.localdate()
        PoliceAssuranceCredit.objects.create(
            company=self.company, assureur='Coface', actif=True,
            date_fin=today + timedelta(days=120))
        self.assertEqual(alerter_polices_expirantes(today=today), 0)
