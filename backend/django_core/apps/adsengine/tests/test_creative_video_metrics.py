"""ADSDEEP44 — Tests des métriques créatives dérivées PAR AD (barre Motion,
benchmark §2), depuis ``InsightSnapshot.video_metrics`` (ADSDEEP1, dossier
insights-api §3).

Prouve : hook rate = vues 6 s / impressions (JAMAIS un champ « 3 s » —
inexistant chez Meta) ; hold rate = thruplay / plays ; ratio 15 s / 6 s ;
courbe de rétention 25/50/75/100 (rapportée à ``plays``) ; temps de visionnage
moyen ; et — invariant DUR testé partout — un champ manquant/dénominateur nul
renvoie toujours ``None``, JAMAIS un 0 fabriqué.
"""
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import metrics
from apps.adsengine.models import AdMirror, InsightSnapshot


class HookRateTests(SimpleTestCase):
    def test_computes_from_s6_over_impressions(self):
        self.assertEqual(
            metrics.hook_rate({'s6': 300}, 1000), 0.3)

    def test_none_when_s6_missing(self):
        self.assertIsNone(metrics.hook_rate({}, 1000))

    def test_none_when_impressions_zero_or_missing(self):
        self.assertIsNone(metrics.hook_rate({'s6': 100}, 0))
        self.assertIsNone(metrics.hook_rate({'s6': 100}, None))

    def test_never_uses_a_3s_field(self):
        # Un éventuel champ « s3 »/« video_3s » ne doit JAMAIS être lu — seul
        # ``s6`` compte (dossier insights-api §3 : le 3 s n'existe pas).
        vm = {'s3': 900, 's6': 100}
        self.assertEqual(metrics.hook_rate(vm, 1000), 0.1)


class HoldRateTests(SimpleTestCase):
    def test_computes_from_thruplay_over_plays(self):
        self.assertEqual(
            metrics.hold_rate({'plays': 1000, 'thruplay': 150}), 0.15)

    def test_none_when_plays_zero_or_missing(self):
        self.assertIsNone(metrics.hold_rate({'thruplay': 10, 'plays': 0}))
        self.assertIsNone(metrics.hold_rate({'thruplay': 10}))

    def test_none_when_thruplay_missing(self):
        self.assertIsNone(metrics.hold_rate({'plays': 1000}))


class Ratio15To6Tests(SimpleTestCase):
    def test_computes_ratio(self):
        self.assertEqual(
            metrics.ratio_15s_to_6s({'s6': 200, 's15': 50}), 0.25)

    def test_none_when_either_missing(self):
        self.assertIsNone(metrics.ratio_15s_to_6s({'s15': 50}))
        self.assertIsNone(metrics.ratio_15s_to_6s({'s6': 0, 's15': 50}))


class RetentionCurveTests(SimpleTestCase):
    def test_each_quartile_over_plays(self):
        curve = metrics.retention_curve(
            {'plays': 1000, 'p25': 800, 'p50': 400, 'p75': 100})
        self.assertEqual(curve['p25'], 0.8)
        self.assertEqual(curve['p50'], 0.4)
        self.assertEqual(curve['p75'], 0.1)
        # p100 absent → None, jamais un 0 fabriqué.
        self.assertIsNone(curve['p100'])

    def test_all_none_without_plays(self):
        curve = metrics.retention_curve({'p25': 800})
        self.assertIsNone(curve['p25'])


class WatchTimeTests(SimpleTestCase):
    def test_passthrough(self):
        self.assertEqual(metrics.watch_time_avg({'avg_time': 4.5}), 4.5)

    def test_none_when_missing(self):
        self.assertIsNone(metrics.watch_time_avg({}))


class DerivedBundleTests(SimpleTestCase):
    def test_static_ad_has_no_video_metrics_never_fake_zero(self):
        # Ad statique : video_metrics vide (dict() par défaut du modèle).
        bundle = metrics.derived_ad_video_metrics({}, 5000)
        self.assertIsNone(bundle['hook_rate'])
        self.assertIsNone(bundle['hold_rate'])
        self.assertIsNone(bundle['ratio_15s_to_6s'])
        self.assertIsNone(bundle['watch_time_avg_s'])
        self.assertEqual(
            bundle['retention'], {'p25': None, 'p50': None, 'p75': None,
                                  'p100': None})

    def test_full_video_ad_bundle(self):
        vm = {'s6': 400, 's15': 150, 'plays': 1000, 'thruplay': 200,
              'p25': 700, 'p50': 300, 'p75': 100, 'p100': 40,
              'avg_time': 3.2}
        bundle = metrics.derived_ad_video_metrics(vm, 2000)
        self.assertEqual(bundle['hook_rate'], 0.2)
        self.assertEqual(bundle['hold_rate'], 0.2)
        self.assertEqual(bundle['ratio_15s_to_6s'], 0.375)
        self.assertEqual(bundle['watch_time_avg_s'], 3.2)
        self.assertEqual(bundle['retention']['p100'], 0.04)


class SumVideoMetricsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Vid Co', slug='vid-co')
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad1', name='Reel v1')
        self.ct = ContentType.objects.get_for_model(AdMirror)

    def _snap(self, day, *, impressions, video_metrics):
        return InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=self.ad.pk,
            date=day, impressions=impressions, video_metrics=video_metrics)

    def test_sums_counters_and_averages_avg_time(self):
        import datetime
        self._snap(datetime.date(2026, 7, 1), impressions=1000,
                   video_metrics={'s6': 100, 'plays': 500, 'avg_time': 2.0})
        self._snap(datetime.date(2026, 7, 2), impressions=1000,
                   video_metrics={'s6': 200, 'plays': 500, 'avg_time': 4.0})
        totals, impressions = metrics.sum_video_metrics(
            InsightSnapshot.objects.filter(company=self.company))
        self.assertEqual(totals['s6'], 300.0)
        self.assertEqual(totals['plays'], 1000.0)
        # avg_time = MOYENNE des jours (2.0, 4.0) → 3.0, jamais la somme (6.0).
        self.assertEqual(totals['avg_time'], 3.0)
        self.assertEqual(impressions, 2000)

    def test_key_absent_everywhere_stays_absent_never_fake_zero(self):
        import datetime
        self._snap(datetime.date(2026, 7, 1), impressions=500,
                   video_metrics={'s6': 50})
        totals, _ = metrics.sum_video_metrics(
            InsightSnapshot.objects.filter(company=self.company))
        self.assertNotIn('thruplay', totals)
        self.assertNotIn('plays', totals)

    def test_ad_video_metrics_for_window(self):
        import datetime
        self._snap(datetime.date(2026, 7, 1), impressions=1000,
                   video_metrics={'s6': 100, 'plays': 500, 'thruplay': 50})
        self._snap(datetime.date(2026, 7, 2), impressions=1000,
                   video_metrics={'s6': 100, 'plays': 500, 'thruplay': 50})
        bundle = metrics.ad_video_metrics_for_window(
            InsightSnapshot.objects.filter(company=self.company))
        self.assertEqual(bundle['hook_rate'], 0.1)  # 200/2000
        self.assertEqual(bundle['hold_rate'], 0.1)  # 100/1000

    def test_no_snapshots_gives_all_none(self):
        bundle = metrics.ad_video_metrics_for_window([])
        self.assertIsNone(bundle['hook_rate'])
        self.assertIsNone(bundle['hold_rate'])


class DecimalSpendUnaffectedTests(SimpleTestCase):
    """Garde-fou : ces fonctions n'ont rien à voir avec ``Decimal`` (dépense) —
    vérifie juste qu'un video_metrics vide ne casse rien même avec des types
    Decimal ailleurs dans le même module (pas de collision de types)."""

    def test_hook_rate_ignores_unrelated_decimal(self):
        _ = Decimal('10.00')
        self.assertIsNone(metrics.hook_rate(None, None))
