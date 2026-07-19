"""PUB57 — Liens profonds PAR ITEM dans le digest quotidien (alertes / ad).

Prouve : ``build_digest_data`` porte un lien profond par section actionnable
(alertes actives → Règles & anomalies ; meilleure ad → Cockpit, jamais quand
la section est vide) ; ``format_body`` les rend en clair (« → /publicite/... »)
lisibles en in-app comme en repli texte email ; et le lien PRINCIPAL de la
notification émise (``send_daily_digest``) n'est plus TOUJOURS le dashboard
générique — il pointe vers l'item le plus actionnable du jour (alertes en
premier, sinon la meilleure ad, sinon le dashboard).
"""
import datetime

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import digest as digest_mod
from apps.adsengine.models import AdCampaignMirror, AdMirror, EngineAlert, InsightSnapshot
from apps.notifications.models import EventType, Notification

User = get_user_model()

TODAY = datetime.date(2026, 7, 17)
YESTERDAY = datetime.date(2026, 7, 16)


class DigestDeepLinksDataTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='DL Digest Co', slug='dl-digest-co')
        AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp', status='PAUSED')

    def test_no_alerts_no_top_ad_gives_no_deep_links(self):
        data = digest_mod.build_digest_data(self.company, now=TODAY)
        self.assertIsNone(data['alertes_lien'])
        self.assertIsNone(data['top_ad_lien'])

    def test_active_alert_gets_regles_link(self):
        EngineAlert.objects.create(
            company=self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='x', acknowledged=False)
        data = digest_mod.build_digest_data(self.company, now=TODAY)
        self.assertEqual(data['alertes_lien'], '/publicite/regles')

    def test_top_ad_gets_cockpit_link(self):
        ad_ct = ContentType.objects.get_for_model(AdMirror)
        ad = AdMirror.objects.create(company=self.company, meta_id='a1', name='Ad Un')
        InsightSnapshot.objects.create(
            company=self.company, content_type=ad_ct, object_id=ad.pk,
            date=YESTERDAY, spend='10.00', results=2)
        data = digest_mod.build_digest_data(self.company, now=TODAY)
        self.assertEqual(data['top_ad_lien'], '/publicite/cockpit')

    def test_format_body_shows_deep_link_when_present(self):
        EngineAlert.objects.create(
            company=self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='x', acknowledged=False)
        data = digest_mod.build_digest_data(self.company, now=TODAY)
        body = digest_mod.format_body(data)
        self.assertIn('/publicite/regles', body)

    def test_format_body_omits_deep_link_when_no_alerts(self):
        data = digest_mod.build_digest_data(self.company, now=TODAY)
        body = digest_mod.format_body(data)
        self.assertNotIn('/publicite/regles', body)


class DigestPrimaryLinkTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='DL Notif Co', slug='dl-notif-co')
        AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp', status='PAUSED')
        self.manager = User.objects.create_user(
            username='dlboss', password='pw', email='dlboss@example.com',
            company=self.company, role_legacy='admin')

    def _notif_link(self):
        return Notification.objects.get(
            recipient=self.manager, event_type=EventType.DIGEST).link

    def test_no_alerts_no_top_ad_falls_back_to_dashboard(self):
        digest_mod.send_daily_digest(self.company, now=TODAY)
        self.assertEqual(self._notif_link(), '/publicite/tableau-de-bord')

    def test_top_ad_present_links_to_cockpit(self):
        ad_ct = ContentType.objects.get_for_model(AdMirror)
        ad = AdMirror.objects.create(company=self.company, meta_id='a1', name='Ad Un')
        InsightSnapshot.objects.create(
            company=self.company, content_type=ad_ct, object_id=ad.pk,
            date=YESTERDAY, spend='10.00', results=2)
        digest_mod.send_daily_digest(self.company, now=TODAY)
        self.assertEqual(self._notif_link(), '/publicite/cockpit')

    def test_active_alerts_outrank_top_ad(self):
        # Une alerte active ET une meilleure ad présentes simultanément :
        # l'alerte (sécurité budget) prime toujours sur la vitrine créative.
        ad_ct = ContentType.objects.get_for_model(AdMirror)
        ad = AdMirror.objects.create(company=self.company, meta_id='a1', name='Ad Un')
        InsightSnapshot.objects.create(
            company=self.company, content_type=ad_ct, object_id=ad.pk,
            date=YESTERDAY, spend='10.00', results=2)
        EngineAlert.objects.create(
            company=self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='x', acknowledged=False)
        digest_mod.send_daily_digest(self.company, now=TODAY)
        self.assertEqual(self._notif_link(), '/publicite/regles')
