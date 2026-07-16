"""QX31be — escalade speed-to-lead des leads chauds non contactés + métrique.

  * un lead chaud (score élevé) dont la notif d'arrivée reste non lue au-delà
    du seuil déclenche une escalade (managers + destinataire) ;
  * un lead froid (score bas) n'escalade pas ;
  * la métrique time-to-first-touch apparaît dans le dashboard commercial.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity
from apps.notifications.models import EventType, Notification


User = get_user_model()


@override_settings(HOT_LEAD_SCORE_THRESHOLD=70, HOT_LEAD_UNREAD_MINUTES=30)
class Qx31HotLeadEscalationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QX31 Co')
        self.manager = User.objects.create_user(
            username='qx31_mgr', password='x', role_legacy='responsable',
            company=self.company)
        self.seller = User.objects.create_user(
            username='qx31_seller', password='x', role_legacy='commercial',
            company=self.company)

    def _hot_lead(self, score=90):
        return Lead.objects.create(
            company=self.company, nom='Hot Lead',
            telephone='+212600000051', score=score)

    def _stale_notif(self, lead, minutes=45):
        n = Notification.objects.create(
            company=self.company, recipient=self.seller,
            event_type=EventType.LEAD_NEW, title='Nouveau lead',
            link=f'/crm/leads?lead={lead.id}', read=False)
        # Antidate la création (auto_now_add) via update direct.
        Notification.objects.filter(pk=n.pk).update(
            created_at=timezone.now() - timedelta(minutes=minutes))
        return n

    def test_hot_lead_unread_escalates(self):
        lead = self._hot_lead(score=90)
        self._stale_notif(lead)
        from apps.notifications.sweeps import sweep_hot_leads
        posted = sweep_hot_leads()
        self.assertGreaterEqual(posted, 1)
        self.assertTrue(Notification.objects.filter(
            event_type=EventType.HOT_LEAD_UNREAD).exists())

    def test_cold_lead_does_not_escalate(self):
        lead = self._hot_lead(score=10)
        self._stale_notif(lead)
        from apps.notifications.sweeps import sweep_hot_leads
        sweep_hot_leads()
        self.assertFalse(Notification.objects.filter(
            event_type=EventType.HOT_LEAD_UNREAD).exists())

    def test_recent_notif_does_not_escalate(self):
        lead = self._hot_lead(score=90)
        self._stale_notif(lead, minutes=5)  # trop récente
        from apps.notifications.sweeps import sweep_hot_leads
        sweep_hot_leads()
        self.assertFalse(Notification.objects.filter(
            event_type=EventType.HOT_LEAD_UNREAD).exists())

    def test_idempotent(self):
        lead = self._hot_lead(score=90)
        self._stale_notif(lead)
        from apps.notifications.sweeps import sweep_hot_leads
        sweep_hot_leads()
        first = Notification.objects.filter(
            event_type=EventType.HOT_LEAD_UNREAD).count()
        sweep_hot_leads()
        second = Notification.objects.filter(
            event_type=EventType.HOT_LEAD_UNREAD).count()
        self.assertEqual(first, second)


class Qx31TimeToFirstTouchTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        self.company = Company.objects.create(nom='QX31 TTFT Co')
        self.manager = User.objects.create_user(
            username='qx31_ttft', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.manager)}')

    def test_metric_present_in_dashboard(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead', telephone='+212600000052')
        # Premier contact 20 min après la création.
        act = LeadActivity.objects.create(
            company=self.company, lead=lead, kind=LeadActivity.Kind.APPEL,
            user=self.manager, body='Appel')
        LeadActivity.objects.filter(pk=act.pk).update(
            created_at=lead.date_creation + timedelta(minutes=20))
        resp = self.api.get('/api/django/reporting/commercial/dashboard/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn('time_to_first_touch', resp.data)
        ttft = resp.data['time_to_first_touch']
        self.assertIsNotNone(ttft['avg_minutes'])
        self.assertGreaterEqual(ttft['sample_count'], 1)
