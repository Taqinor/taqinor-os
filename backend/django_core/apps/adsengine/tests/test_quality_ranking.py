"""PUB32 — Diagnostics de classement Meta (qualité/engagement/conversion) au
niveau ad + câblage du garde-fou DUR ``signal_guards.quality_ranking_guard``.

Prouve : la synchro ad-level peuple les colonnes de classement (l'adset ne les
touche pas), la None-protection d'``upsert_insight`` ne clobber pas un classement
connu, le guard (resté sans appelant) freine sur « below_average » soutenu
(alerte, jamais une accélération ni un contournement du spine), et les
classements sont visibles au cockpit.
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import metrics, sync, tasks
from apps.adsengine.models import (
    AdMirror, AdSetMirror, EngineAlert, InsightSnapshot, MetaConnection,
)

DAY = datetime.date(2026, 7, 16)


class FakeRankingClient:
    """Client Meta mocké : ``get_insights`` renvoie des rows ad-level fixés."""

    def __init__(self, rows):
        self.rows = rows

    def get_insights(self, node, *, fields=None, params=None):
        return self.rows


class RankingSyncTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QR Co', slug='qr-co')
        self.conn = MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'x'}, ad_account_id='act_1')
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad1', name='Ad 1')

    def _snap(self):
        ct = ContentType.objects.get_for_model(AdMirror)
        return InsightSnapshot.objects.get(
            company=self.company, content_type=ct, object_id=self.ad.pk)

    def test_ad_level_sync_populates_rankings(self):
        client = FakeRankingClient([{
            'ad_id': 'ad1', 'date_start': DAY.isoformat(),
            'spend': '10.00', 'impressions': 1000,
            'quality_ranking': 'below_average',
            'engagement_rate_ranking': 'average',
            'conversion_rate_ranking': 'above_average'}])
        tasks._sync_level_insights(self.company, self.conn, client, level='ad')
        snap = self._snap()
        self.assertEqual(snap.quality_ranking, 'below_average')
        self.assertEqual(snap.engagement_rate_ranking, 'average')
        self.assertEqual(snap.conversion_rate_ranking, 'above_average')

    def test_adset_level_does_not_write_rankings(self):
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as1', name='AS 1')
        client = FakeRankingClient([{
            'adset_id': 'as1', 'date_start': DAY.isoformat(),
            'spend': '10.00', 'impressions': 1000,
            'quality_ranking': 'below_average'}])
        tasks._sync_level_insights(
            self.company, self.conn, client, level='adset')
        ct = ContentType.objects.get_for_model(AdSetMirror)
        snap = InsightSnapshot.objects.get(
            company=self.company, content_type=ct, object_id=adset.pk)
        # L'adset n'expose pas les classements → colonne intacte ('').
        self.assertEqual(snap.quality_ranking, '')

    def test_partial_resync_does_not_clobber_ranking(self):
        # 1) écrit un classement.
        sync.upsert_insight(
            self.company, self.ad, date=DAY, spend='10',
            quality_ranking='below_average', impressions=1000)
        # 2) re-sync partiel SANS classement (None) → ne l'efface pas.
        sync.upsert_insight(self.company, self.ad, date=DAY, spend='12')
        snap = self._snap()
        self.assertEqual(snap.quality_ranking, 'below_average')
        self.assertEqual(str(snap.spend), '12.00')


class RankingGuardTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='GR Co', slug='gr-co')
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad1', name='Ad 1')

    def _snap(self, ranking, impressions):
        ct = ContentType.objects.get_for_model(AdMirror)
        return InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=self.ad.pk,
            date=DAY, quality_ranking=ranking, impressions=impressions)

    def test_below_average_triggers_brake_alert(self):
        self._snap('below_average', 1000)
        n = tasks._evaluate_ranking_guards_for_company(self.company)
        self.assertEqual(n, 1)
        alert = EngineAlert.objects.get(
            company=self.company, entity_key=f'ad:{self.ad.pk}')
        self.assertEqual(alert.detail['guard'], 'quality_ranking')
        self.assertEqual(alert.severity, EngineAlert.Severity.CRITIQUE)

    def test_alert_is_deduped(self):
        self._snap('below_average', 1000)
        tasks._evaluate_ranking_guards_for_company(self.company)
        tasks._evaluate_ranking_guards_for_company(self.company)
        self.assertEqual(
            EngineAlert.objects.filter(
                company=self.company, entity_key=f'ad:{self.ad.pk}',
                acknowledged=False).count(), 1)

    def test_above_average_no_alert(self):
        self._snap('above_average', 1000)
        n = tasks._evaluate_ranking_guards_for_company(self.company)
        self.assertEqual(n, 0)
        self.assertEqual(EngineAlert.objects.count(), 0)

    def test_below_average_low_impressions_no_alert(self):
        # <500 impr. : le diagnostic n'est pas fiable → aucun frein.
        self._snap('below_average', 100)
        n = tasks._evaluate_ranking_guards_for_company(self.company)
        self.assertEqual(n, 0)


class RankingCockpitTests(TestCase):
    def test_ranking_visible_in_cockpit_rows(self):
        company = Company.objects.create(nom='CK Co', slug='ck-co')
        ad = AdMirror.objects.create(
            company=company, meta_id='ad1', name='Ad 1')
        ct = ContentType.objects.get_for_model(AdMirror)
        InsightSnapshot.objects.create(
            company=company, content_type=ct, object_id=ad.pk, date=DAY,
            spend='10.00', impressions=1000,
            quality_ranking='below_average',
            engagement_rate_ranking='average',
            conversion_rate_ranking='above_average')
        rows = metrics.ads_cockpit_rows(company, as_of=DAY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['classement_qualite'], 'below_average')
        self.assertEqual(rows[0]['classement_engagement'], 'average')
        self.assertEqual(rows[0]['classement_conversion'], 'above_average')
