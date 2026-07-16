"""QX30be — moteur de relance déclenchée par le comportement + engagement
race-safe.

  * chaque déclencheur (not_opened_24h / opened_not_signed_48h / reopened_3x)
    pose UNE notification, idempotente ;
  * le beacon d'engagement fusionne sous verrou (pas de perte de mise à jour).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, ShareLink

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class Qx30EngagementEngineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QX30 Co')
        self.seller = User.objects.create_user(
            username='qx30_seller', password='x', role_legacy='commercial',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX30',
            telephone='+212600000050')

    def _devis(self, ref, days_ago=2):
        return Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            created_by=self.seller,
            date_envoi=timezone.now() - timedelta(days=days_ago))

    def _run(self):
        from apps.ventes.scheduled import engagement_followup_engine
        return engagement_followup_engine()

    def test_not_opened_24h_trigger(self):
        devis = self._devis(f'DEV-{MONTH}-QX3001', days_ago=2)
        ShareLink.objects.create(
            company=self.company, devis=devis, view_count=0)
        posted = self._run()
        self.assertGreaterEqual(posted, 1)
        from apps.notifications.models import Notification
        self.assertTrue(Notification.objects.filter(
            recipient=self.seller).exists())

    def test_opened_not_signed_48h_trigger(self):
        devis = self._devis(f'DEV-{MONTH}-QX3002', days_ago=3)
        ShareLink.objects.create(
            company=self.company, devis=devis, view_count=1,
            first_viewed_at=timezone.now() - timedelta(hours=49),
            last_viewed_at=timezone.now() - timedelta(hours=49))
        self._run()
        link = ShareLink.objects.get(devis=devis)
        self.assertIn('opened_not_signed_48h',
                      link.engagement_triggers_fired or [])

    def test_reopened_3x_trigger(self):
        devis = self._devis(f'DEV-{MONTH}-QX3003', days_ago=1)
        ShareLink.objects.create(
            company=self.company, devis=devis, view_count=3,
            first_viewed_at=timezone.now() - timedelta(hours=2))
        self._run()
        link = ShareLink.objects.get(devis=devis)
        self.assertIn('reopened_3x', link.engagement_triggers_fired or [])

    def test_idempotent_no_double_notification(self):
        from apps.notifications.models import Notification
        devis = self._devis(f'DEV-{MONTH}-QX3004', days_ago=2)
        ShareLink.objects.create(
            company=self.company, devis=devis, view_count=0)
        self._run()
        first = Notification.objects.filter(recipient=self.seller).count()
        self._run()  # second pass — must not re-post the same trigger
        second = Notification.objects.filter(recipient=self.seller).count()
        self.assertEqual(first, second)

    def test_engagement_beacon_merges_sections(self):
        """Deux sections différentes cumulent (fusion, pas d'écrasement)."""
        from rest_framework.test import APIClient
        devis = self._devis(f'DEV-{MONTH}-QX3005')
        link = ShareLink.objects.create(company=self.company, devis=devis)
        api = APIClient()
        url = f'/api/django/public/proposal/{link.token}/engagement/'
        api.post(url, {'section': 'prix', 'seconds': 10}, format='json')
        api.post(url, {'section': 'etude', 'seconds': 5}, format='json')
        link.refresh_from_db()
        eng = link.engagement or {}
        self.assertIn('prix', eng)
        self.assertIn('etude', eng)
        self.assertEqual(eng['prix']['seconds'], 10)
        self.assertEqual(eng['etude']['seconds'], 5)
