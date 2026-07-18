"""ADSDEEP48 — Tests des benchmarks internes (cadence créative + taux de
gagnants), barre Motion (benchmark concurrent §2 : 12-19 créatifs neufs/
semaine, ~9 % de winners).

Prouve : la cadence compte les ``CreativeAsset`` NEUFS de la fenêtre et se
compare au repère [12, 19] ; le taux de gagnants ne fabrique JAMAIS un 0 %
quand aucun ad n'a été lancé (``None``) ; les deux chiffres atterrissent dans
``WeeklyBrief.data`` ET son rendu markdown.
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import brief as brief_mod
from apps.adsengine.models import AdMirror, CreativeAsset, InsightSnapshot

NOW = datetime.date(2026, 7, 16)


class WeeklyCreativeCadenceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Cad Co', slug='cad-co')

    def _asset(self, day):
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC)
        CreativeAsset.objects.filter(pk=asset.pk).update(
            created_at=datetime.datetime.combine(day, datetime.time(12, 0)))
        return asset

    def test_counts_new_assets_in_window(self):
        for i in range(5):
            self._asset(NOW - datetime.timedelta(days=i))
        cadence = brief_mod.weekly_creative_cadence(
            self.company, start=NOW - datetime.timedelta(days=6), end=NOW)
        self.assertEqual(cadence['count'], 5)
        self.assertEqual(cadence['target_min'], 12)
        self.assertEqual(cadence['target_max'], 19)
        self.assertEqual(cadence['statut'], 'sous_cible')

    def test_within_target_band(self):
        for i in range(15):
            self._asset(NOW)
        cadence = brief_mod.weekly_creative_cadence(
            self.company, start=NOW - datetime.timedelta(days=6), end=NOW)
        self.assertEqual(cadence['statut'], 'dans_la_cible')

    def test_above_target_band(self):
        for i in range(25):
            self._asset(NOW)
        cadence = brief_mod.weekly_creative_cadence(
            self.company, start=NOW - datetime.timedelta(days=6), end=NOW)
        self.assertEqual(cadence['statut'], 'au_dessus_cible')

    def test_assets_outside_window_excluded(self):
        self._asset(NOW - datetime.timedelta(days=30))
        cadence = brief_mod.weekly_creative_cadence(
            self.company, start=NOW - datetime.timedelta(days=6), end=NOW)
        self.assertEqual(cadence['count'], 0)
        self.assertEqual(cadence['statut'], 'sous_cible')

    def test_zero_assets_never_fabricated_as_target(self):
        cadence = brief_mod.weekly_creative_cadence(
            self.company, start=NOW - datetime.timedelta(days=6), end=NOW)
        self.assertEqual(cadence['count'], 0)
        self.assertEqual(cadence['statut'], 'sous_cible')


class WinnerRateTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Win Co', slug='win-co')
        self.ct = ContentType.objects.get_for_model(AdMirror)

    def _ad_launched(self, meta_id, day):
        ad = AdMirror.objects.create(
            company=self.company, meta_id=meta_id, name=meta_id)
        AdMirror.objects.filter(pk=ad.pk).update(
            created_at=datetime.datetime.combine(day, datetime.time(9, 0)))
        return ad

    def _snap(self, ad, day, results):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=ad.pk,
            date=day, results=results)

    def test_none_when_no_ad_launched_never_fake_zero(self):
        rate = brief_mod.winner_rate(
            self.company, start=NOW - datetime.timedelta(days=6), end=NOW)
        self.assertIsNone(rate['valeur'])
        self.assertEqual(rate['total'], 0)

    def test_computes_fraction_of_winners(self):
        winner = self._ad_launched('w1', NOW)
        loser = self._ad_launched('l1', NOW)
        self._snap(winner, NOW, results=3)
        self._snap(loser, NOW, results=0)
        rate = brief_mod.winner_rate(
            self.company, start=NOW - datetime.timedelta(days=6), end=NOW)
        self.assertEqual(rate['gagnants'], 1)
        self.assertEqual(rate['total'], 2)
        self.assertEqual(rate['valeur'], 0.5)
        self.assertAlmostEqual(rate['reference_marche'], 0.09)

    def test_ad_without_any_snapshot_counts_as_loser_not_excluded(self):
        self._ad_launched('no-snap', NOW)
        rate = brief_mod.winner_rate(
            self.company, start=NOW - datetime.timedelta(days=6), end=NOW)
        self.assertEqual(rate['total'], 1)
        self.assertEqual(rate['gagnants'], 0)
        self.assertEqual(rate['valeur'], 0.0)

    def test_ads_launched_outside_window_excluded(self):
        old_ad = self._ad_launched(
            'old1', NOW - datetime.timedelta(days=30))
        self._snap(old_ad, NOW, results=5)
        rate = brief_mod.winner_rate(
            self.company, start=NOW - datetime.timedelta(days=6), end=NOW)
        self.assertEqual(rate['total'], 0)
        self.assertIsNone(rate['valeur'])


class WeeklyBriefBenchmarksIntegrationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='WB Co', slug='wb-co')
        self.ct = ContentType.objects.get_for_model(AdMirror)

    def test_brief_includes_cadence_and_winner_rate(self):
        # ``created_at`` est ``auto_now_add`` : forcer la date via .update()
        # APRÈS création (le ``.create()`` l'ignore silencieusement).
        for i in range(3):
            asset = CreativeAsset.objects.create(
                company=self.company,
                asset_type=CreativeAsset.AssetType.STATIC)
            CreativeAsset.objects.filter(pk=asset.pk).update(
                created_at=datetime.datetime.combine(
                    NOW, datetime.time(10, 0)))
        ad = AdMirror.objects.create(
            company=self.company, meta_id='a1', name='a1')
        AdMirror.objects.filter(pk=ad.pk).update(
            created_at=datetime.datetime.combine(NOW, datetime.time(9, 0)))
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=ad.pk,
            date=NOW, results=2)

        brief = brief_mod.build_brief(self.company, now=NOW)
        cadence = brief.data['cadence_creative']
        self.assertEqual(cadence['count'], 3)
        self.assertEqual(cadence['statut'], 'sous_cible')

        gagnants = brief.data['taux_de_gagnants']
        self.assertEqual(gagnants['total'], 1)
        self.assertEqual(gagnants['gagnants'], 1)
        self.assertEqual(gagnants['valeur'], 1.0)

        self.assertIn('Cadence créative', brief.markdown)
        self.assertIn('Taux de gagnants', brief.markdown)

    def test_brief_markdown_never_fabricates_winner_rate_with_no_launches(self):
        brief = brief_mod.build_brief(self.company, now=NOW)
        self.assertIsNone(brief.data['taux_de_gagnants']['valeur'])
        self.assertIn('indicateur non calculable', brief.markdown)
