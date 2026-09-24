"""QX31be — escalade speed-to-lead des leads chauds non contactés + métrique.

  * un lead chaud (score élevé) jamais contacté au-delà du seuil de minutes
    OUVRÉES déclenche une escalade (managers + responsable) ;
  * un lead froid (score bas) n'escalade pas ;
  * la métrique time-to-first-touch apparaît dans le dashboard commercial.

CAD132 (audit L3 du 21/09/2026) — réaligné : le filet lit le LEAD
(``first_contacted_at`` NULL), plus la notification d'arrivée non lue, et
compte en minutes ouvrées. Horloge FIXE (``now=``). Le détail des nouveaux
comportements vit dans ``tests_cad132_filet_lead_chaud.py``.
"""
import datetime
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.crm import horaires
from apps.crm.models import Lead, LeadActivity
from apps.notifications.models import EventType, Notification


User = get_user_model()

#: Mercredi 2 septembre 2026, 9 h — jour ouvré, en pleine fenêtre.
ARRIVEE = datetime.datetime(2026, 9, 2, 9, 0, tzinfo=horaires.CASABLANCA)


@override_settings(HOT_LEAD_MINUTES_OUVREES=30)
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
        lead = Lead.objects.create(
            company=self.company, nom='Hot Lead',
            telephone='+212600000051', score=score)
        # Antidate l'arrivée (auto_now_add) via update direct.
        Lead.objects.filter(pk=lead.pk).update(date_creation=ARRIVEE)
        return lead

    def test_hot_lead_unread_escalates(self):
        self._hot_lead(score=90)
        from apps.notifications.sweeps import sweep_hot_leads
        posted = sweep_hot_leads(now=ARRIVEE + timedelta(minutes=45))
        self.assertGreaterEqual(posted, 1)
        self.assertTrue(Notification.objects.filter(
            event_type=EventType.HOT_LEAD_UNREAD).exists())

    def test_cold_lead_does_not_escalate(self):
        self._hot_lead(score=10)
        from apps.notifications.sweeps import sweep_hot_leads
        sweep_hot_leads(now=ARRIVEE + timedelta(minutes=45))
        self.assertFalse(Notification.objects.filter(
            event_type=EventType.HOT_LEAD_UNREAD).exists())

    def test_recent_lead_does_not_escalate(self):
        self._hot_lead(score=90)
        from apps.notifications.sweeps import sweep_hot_leads
        # 5 minutes ouvrées seulement : sous le seuil.
        sweep_hot_leads(now=ARRIVEE + timedelta(minutes=5))
        self.assertFalse(Notification.objects.filter(
            event_type=EventType.HOT_LEAD_UNREAD).exists())

    def test_idempotent(self):
        self._hot_lead(score=90)
        from apps.notifications.sweeps import sweep_hot_leads
        sweep_hot_leads(now=ARRIVEE + timedelta(minutes=45))
        first = Notification.objects.filter(
            event_type=EventType.HOT_LEAD_UNREAD).count()
        sweep_hot_leads(now=ARRIVEE + timedelta(minutes=60))
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
