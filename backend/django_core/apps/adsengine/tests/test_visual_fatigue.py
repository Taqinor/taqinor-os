"""PUB74 — Tests de la fatigue au niveau du VISUEL (``visual_asset_key``).

Prouve :
  * le détecteur PUR ``anomaly.detect_visual_reuse_fatigue`` : ne tire pas
    sous les planchers de réutilisation/hooks distincts, tire en WARNING,
    escalade en CRITICAL sur un déclin de CTR cross-ads confirmé ;
  * ``metrics.visual_fatigue_report`` regroupe les assets par
    ``visual_asset_key``, ignore les assets sans visuel, et calcule le déclin
    de CTR entre la PLUS ANCIENNE et la PLUS RÉCENTE ad ayant diffusé ce
    visuel ;
  * l'endpoint reporting est gaté ``adsengine_view``.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import anomaly, metrics
from apps.adsengine.models import (
    AdMirror, CreativeAsset, Experiment, ExperimentArm, InsightSnapshot,
)

User = get_user_model()
FATIGUE_URL = '/api/django/adsengine/reporting/creatifs/fatigue-visuelle/'


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DetectVisualReuseFatiguePureTests(SimpleTestCase):
    def test_below_reuse_floor_never_fires(self):
        d = anomaly.detect_visual_reuse_fatigue(2, 2, min_reuse=3)
        self.assertFalse(d.fired)

    def test_below_distinct_hooks_floor_never_fires(self):
        # 4 créas mais le MÊME hook à chaque fois : recyclage normal, pas un
        # signal de lassitude visuelle.
        d = anomaly.detect_visual_reuse_fatigue(
            4, 1, min_reuse=3, min_distinct_hooks=2)
        self.assertFalse(d.fired)

    def test_fires_warning_without_decline_data(self):
        d = anomaly.detect_visual_reuse_fatigue(3, 2)
        self.assertTrue(d.fired)
        self.assertEqual(d.severity, anomaly.SEVERITY_WARNING)
        self.assertEqual(d.kind, anomaly.KIND_VISUAL_FATIGUE)

    def test_escalates_to_critical_on_ctr_decline(self):
        d = anomaly.detect_visual_reuse_fatigue(
            3, 2, ctr_decline_pct=0.40, ctr_decline_warn=0.25)
        self.assertTrue(d.fired)
        self.assertEqual(d.severity, anomaly.SEVERITY_CRITICAL)

    def test_small_decline_stays_warning(self):
        d = anomaly.detect_visual_reuse_fatigue(
            3, 2, ctr_decline_pct=0.05, ctr_decline_warn=0.25)
        self.assertEqual(d.severity, anomaly.SEVERITY_WARNING)


class VisualFatigueReportTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Vis Co', slug='vis-co')
        self.ct = ContentType.objects.get_for_model(AdMirror)
        self.exp = Experiment.objects.create(company=self.company, name='E')

    def _asset(self, visual_key, hook_tag):
        return CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            visual_asset_key=visual_key, hook_tag=hook_tag)

    def _ad(self, meta_id, created_at):
        ad = AdMirror.objects.create(
            company=self.company, meta_id=meta_id, name=meta_id)
        AdMirror.objects.filter(pk=ad.pk).update(created_at=created_at)
        ad.refresh_from_db()
        return ad

    def _arm(self, asset, ad_id):
        ExperimentArm.objects.create(
            company=self.company, experiment=self.exp, creative_asset=asset,
            label=ad_id, ad_id=ad_id)

    def _snap(self, ad, *, impressions, clicks):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=ad.pk,
            date=datetime.date(2026, 7, 16), spend=Decimal('10.00'),
            results=1, impressions=impressions, clicks=clicks)

    def test_asset_without_visual_key_ignored(self):
        self._asset('', 'HOOK1')
        data = metrics.visual_fatigue_report(self.company)
        self.assertEqual(data['signals'], [])

    def test_reused_visual_with_distinct_hooks_signals(self):
        a1 = self._asset('vis/x.jpg', 'HOOK1')
        a2 = self._asset('vis/x.jpg', 'HOOK2')
        a3 = self._asset('vis/x.jpg', 'HOOK3')
        ad1 = self._ad('ad_1', datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc))
        ad2 = self._ad('ad_2', datetime.datetime(2026, 6, 15, tzinfo=datetime.timezone.utc))
        ad3 = self._ad('ad_3', datetime.datetime(2026, 7, 1, tzinfo=datetime.timezone.utc))
        self._arm(a1, 'ad_1')
        self._arm(a2, 'ad_2')
        self._arm(a3, 'ad_3')
        self._snap(ad1, impressions=1000, clicks=100)   # CTR 0.10 (le + ancien)
        self._snap(ad2, impressions=1000, clicks=60)
        self._snap(ad3, impressions=1000, clicks=40)     # CTR 0.04 (le + récent)

        data = metrics.visual_fatigue_report(self.company)
        self.assertEqual(len(data['signals']), 1)
        signal = data['signals'][0]
        self.assertEqual(signal['visual_asset_key'], 'vis/x.jpg')
        self.assertEqual(signal['creas_count'], 3)
        self.assertEqual(signal['distinct_hooks'], 3)
        self.assertEqual(signal['ad_meta_ids'], ['ad_1', 'ad_2', 'ad_3'])
        # Déclin CTR (0.10 → 0.04) = 60 % ⇒ CRITICAL.
        self.assertEqual(signal['severity'], anomaly.SEVERITY_CRITICAL)
        self.assertAlmostEqual(signal['ctr_decline_pct'], 0.6, places=2)

    def test_same_hook_reused_never_signals(self):
        a1 = self._asset('vis/y.jpg', 'HOOK1')
        a2 = self._asset('vis/y.jpg', 'HOOK1')
        a3 = self._asset('vis/y.jpg', 'HOOK1')
        self._arm(a1, 'ad_a')
        self._arm(a2, 'ad_b')
        self._arm(a3, 'ad_c')
        data = metrics.visual_fatigue_report(self.company)
        self.assertEqual(data['signals'], [])

    def test_scoped_to_company(self):
        other = Company.objects.create(nom='Other Vis', slug='other-vis')
        CreativeAsset.objects.create(
            company=other, asset_type=CreativeAsset.AssetType.STATIC,
            visual_asset_key='vis/z.jpg', hook_tag='H1')
        CreativeAsset.objects.create(
            company=other, asset_type=CreativeAsset.AssetType.STATIC,
            visual_asset_key='vis/z.jpg', hook_tag='H2')
        CreativeAsset.objects.create(
            company=other, asset_type=CreativeAsset.AssetType.STATIC,
            visual_asset_key='vis/z.jpg', hook_tag='H3')
        data = metrics.visual_fatigue_report(self.company)
        self.assertEqual(data['signals'], [])


class VisualFatigueEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='VisEp Co', slug='visep-co')
        self.viewer = make_user(self.company, 'vis-viewer', ['adsengine_view'])

    def test_endpoint_returns_shape(self):
        resp = auth(self.viewer).get(FATIGUE_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('signals', resp.data)

    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'vis-nobody', [])
        self.assertEqual(auth(nobody).get(FATIGUE_URL).status_code, 403)
