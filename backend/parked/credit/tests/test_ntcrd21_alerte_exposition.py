"""NTCRD21 — alerte seuil d'exposition société : dépassement → une seule
notification par jour (dédup, pas de spam)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.credit.models import ReglageCredit
from apps.credit.tasks import alerter_exposition_globale_pour_societe
from apps.crm.models import Client
from apps.notifications.models import Notification
from apps.ventes.models import Facture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='ntcrd21-co', nom='NTCRD21 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD21AlerteExpositionTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ntcrd21_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='ntcrd21@example.com')
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-N21001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('100000'), created_by=self.admin)

    def test_no_alert_when_threshold_disabled(self):
        ReglageCredit.objects.create(
            company=self.company, seuil_alerte_exposition_globale=Decimal('0'))
        fired = alerter_exposition_globale_pour_societe(self.company)
        self.assertFalse(fired)
        self.assertEqual(Notification.objects.count(), 0)

    def test_alert_fires_once_per_day(self):
        ReglageCredit.objects.create(
            company=self.company,
            seuil_alerte_exposition_globale=Decimal('50000'))
        today = timezone.localdate()
        fired = alerter_exposition_globale_pour_societe(
            self.company, today=today)
        self.assertTrue(fired)
        count_after_first = Notification.objects.filter(
            recipient=self.admin).count()
        self.assertGreaterEqual(count_after_first, 1)
        # Second run same day → no new notification (dedup).
        fired2 = alerter_exposition_globale_pour_societe(
            self.company, today=today)
        self.assertFalse(fired2)
        self.assertEqual(
            Notification.objects.filter(recipient=self.admin).count(),
            count_after_first)

    def test_no_alert_below_threshold(self):
        ReglageCredit.objects.create(
            company=self.company,
            seuil_alerte_exposition_globale=Decimal('500000'))
        fired = alerter_exposition_globale_pour_societe(self.company)
        self.assertFalse(fired)
