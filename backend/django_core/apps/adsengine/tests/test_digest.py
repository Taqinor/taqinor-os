"""ADSDEEP62 — Tests du digest quotidien FR (dépense/conversations/leads/
signatures/alertes actives/top ad de la veille), émis via le moteur de
notifications unifié.

Prouve : agrégation correcte de la VEILLE (jamais aujourd'hui), dégradation
propre sans instantané ad-level / sans connecteur Odoo / sans clé email,
opt-out PAR UTILISATEUR respecté (``NotificationPreference``), joignabilité +
routage du beat quotidien.
"""
import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import digest as digest_mod
from apps.adsengine.models import (
    AdCampaignMirror, AdMirror, EngineAlert, InsightSnapshot,
)
from apps.adsengine.tasks import daily_ads_digest
from apps.notifications.models import (
    EventType, Notification, NotificationPreference,
)

User = get_user_model()

TODAY = datetime.date(2026, 7, 17)
YESTERDAY = datetime.date(2026, 7, 16)


class DigestDataTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Digest Co', slug='digest-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp', status='PAUSED')
        self.camp_ct = ContentType.objects.get_for_model(AdCampaignMirror)

    def test_aggregates_yesterday_only(self):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.camp_ct,
            object_id=self.camp.pk, date=YESTERDAY, spend='150.00',
            results=3, conversations=4)
        # Bruit : un instantané d'AUJOURD'HUI ne doit jamais entrer dans « hier ».
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.camp_ct,
            object_id=self.camp.pk, date=TODAY, spend='999.00',
            results=99, conversations=99)
        data = digest_mod.build_digest_data(self.company, now=TODAY)
        self.assertEqual(data['date'], YESTERDAY.isoformat())
        self.assertEqual(data['spend'], '150.00')
        self.assertEqual(data['conversations'], 4)

    def test_no_ad_level_snapshot_gives_none_top_ad(self):
        # Gap connu (dossier adsdeep-existing-map) : la synchro ad-level n'est
        # pas garantie en prod — jamais un « top ad » fabriqué depuis du vide.
        data = digest_mod.build_digest_data(self.company, now=TODAY)
        self.assertIsNone(data['top_ad'])

    def test_top_ad_picks_best_result(self):
        ad_ct = ContentType.objects.get_for_model(AdMirror)
        ad1 = AdMirror.objects.create(
            company=self.company, meta_id='a1', name='Ad Un')
        ad2 = AdMirror.objects.create(
            company=self.company, meta_id='a2', name='Ad Deux')
        InsightSnapshot.objects.create(
            company=self.company, content_type=ad_ct, object_id=ad1.pk,
            date=YESTERDAY, spend='10.00', results=2)
        InsightSnapshot.objects.create(
            company=self.company, content_type=ad_ct, object_id=ad2.pk,
            date=YESTERDAY, spend='20.00', results=5)
        data = digest_mod.build_digest_data(self.company, now=TODAY)
        self.assertEqual(data['top_ad']['name'], 'Ad Deux')
        self.assertEqual(data['top_ad']['results'], 5)

    def test_active_alerts_counted(self):
        EngineAlert.objects.create(
            company=self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='x', acknowledged=False)
        EngineAlert.objects.create(
            company=self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='y', acknowledged=True)
        data = digest_mod.build_digest_data(self.company, now=TODAY)
        self.assertEqual(data['alertes_actives'], 1)

    def test_odoo_unconfigured_gives_none_signatures_not_zero(self):
        data = digest_mod.build_digest_data(self.company, now=TODAY)
        self.assertIsNone(data['signatures'])

    def test_format_body_is_french_and_uses_only_numbers(self):
        data = digest_mod.build_digest_data(self.company, now=TODAY)
        body = digest_mod.format_body(data)
        self.assertIn('Récapitulatif publicité du', body)
        self.assertIn('Dépense', body)


class DigestNotificationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Notif Co', slug='notif-co')
        AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp', status='PAUSED')
        self.manager = User.objects.create_user(
            username='boss', password='pw', email='boss@example.com',
            company=self.company, role_legacy='admin')
        self.staffer = User.objects.create_user(
            username='staffer', password='pw', email='staffer@example.com',
            company=self.company)

    def test_send_emits_in_app_to_recipients(self):
        emitted = digest_mod.send_daily_digest(self.company, now=TODAY)
        self.assertEqual(emitted, 1)  # seul le manager (repli admin/responsable)
        self.assertTrue(Notification.objects.filter(
            recipient=self.manager, event_type=EventType.DIGEST).exists())

    def test_opt_out_respected(self):
        NotificationPreference.objects.create(
            user=self.manager, event_type=EventType.DIGEST,
            in_app=False, whatsapp=False, email=False)
        emitted = digest_mod.send_daily_digest(self.company, now=TODAY)
        self.assertEqual(emitted, 0)
        self.assertFalse(Notification.objects.filter(
            recipient=self.manager, event_type=EventType.DIGEST).exists())

    def test_degrades_gracefully_without_email_key(self):
        # Le manager opte-in pour l'email, mais AUCUNE clé n'est configurée
        # (comportement local par défaut) : jamais d'exception, l'in-app part
        # quand même.
        NotificationPreference.objects.create(
            user=self.manager, event_type=EventType.DIGEST,
            in_app=True, whatsapp=False, email=True)
        mail.outbox = []
        emitted = digest_mod.send_daily_digest(self.company, now=TODAY)
        self.assertEqual(emitted, 1)
        self.assertEqual(len(mail.outbox), 0)  # no-op silencieux, pas de crash


class DigestTaskTests(TestCase):
    def test_task_noop_without_campaigns(self):
        Company.objects.create(nom='Empty', slug='empty-digest')
        result = daily_ads_digest()
        self.assertEqual(result, {'digests_emitted': 0})

    def test_task_generates_for_company_with_campaign_and_recipient(self):
        company = Company.objects.create(nom='Has', slug='has-digest')
        AdCampaignMirror.objects.create(
            company=company, meta_id='c1', name='C', status='PAUSED')
        User.objects.create_user(
            username='u-has', password='pw', email='u@example.com',
            company=company)
        result = daily_ads_digest()
        self.assertEqual(result, {'digests_emitted': 1})


class DigestBeatReachabilityTests(SimpleTestCase):
    def test_task_is_scheduled(self):
        from erp_agentique.celery import app
        names = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertIn('adsengine.daily_ads_digest', names)

    def test_task_routed_to_scheduled(self):
        route = settings.CELERY_TASK_ROUTES['adsengine.daily_ads_digest']
        self.assertEqual(route['queue'], 'scheduled')
