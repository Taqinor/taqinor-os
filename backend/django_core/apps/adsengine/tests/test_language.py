"""PUB77 — Champ langue + parseur + split leaderboard par langue.

Prouve : ``naming.language_from_name`` normalise fr/darija/amazigh depuis un nom
selon convention ; le leaderboard reporting sépare la performance PAR LANGUE (un
asset sans langue compté à part, jamais rangé sous une langue fabriquée).
"""
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import naming, reporting
from apps.adsengine.models import CreativeAsset


class NamingLanguageTests(TestCase):
    def test_normalize_language_aliases(self):
        self.assertEqual(naming.normalize_language('FR'), 'fr')
        self.assertEqual(naming.normalize_language('darija'), 'ar-ma')
        self.assertEqual(naming.normalize_language('ary'), 'ar-ma')
        self.assertEqual(naming.normalize_language('amazigh'), 'amazigh')
        self.assertEqual(naming.normalize_language('klingon'), '')
        self.assertEqual(naming.normalize_language(''), '')

    def test_language_from_name_positional(self):
        # Convention avec un segment LANGUAGE en 5e position.
        conv = 'DATE_FORMAT_HOOK_ANGLE_LANGUAGE'
        self.assertEqual(
            naming.language_from_name('2026_UGC_PAIN_ROI_DARIJA', convention=conv),
            'ar-ma')
        self.assertEqual(
            naming.language_from_name('2026_UGC_PAIN_ROI_FR', convention=conv),
            'fr')

    def test_language_absent_from_default_convention(self):
        # La convention par défaut n'a pas de segment langue → '' (pas inventé).
        self.assertEqual(
            naming.language_from_name('2026_UGC_PAIN_ROI'), '')

    def test_language_in_known_fields(self):
        self.assertIn('language', naming.KNOWN_FIELDS)


class LanguageLeaderboardTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Lang Co', slug='lang-co')

    def _asset(self, language, perf):
        return CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.REEL,
            language=language, perf=perf)

    def test_leaderboard_splits_by_language(self):
        self._asset('fr', {'spend': 100, 'results': 5, 'impressions': 1000})
        self._asset('fr', {'spend': 50, 'results': 5, 'impressions': 500})
        self._asset('ar-ma', {'spend': 200, 'results': 20, 'impressions': 4000})
        self._asset('', {'spend': 999, 'results': 1})  # sans langue → à part

        board = reporting.language_leaderboard(self.company)
        self.assertEqual(board['untagged_count'], 1)
        rows = {r['language']: r for r in board['classement']}
        self.assertIn('fr', rows)
        self.assertIn('ar-ma', rows)
        # FR : 150 dépensé, 10 résultats → cost/result 15.00.
        self.assertEqual(rows['fr']['spend'], '150')
        self.assertEqual(rows['fr']['results'], 10)
        self.assertEqual(rows['fr']['cost_per_result'], '15.00')
        # Darija : meilleur coût par résultat (10.00).
        self.assertEqual(rows['ar-ma']['cost_per_result'], '10.00')
        # Trié par dépense décroissante : darija (200) avant fr (150).
        self.assertEqual(board['classement'][0]['language'], 'ar-ma')

    def test_no_results_gives_none_cost(self):
        self._asset('fr', {'spend': 100, 'results': 0})
        board = reporting.language_leaderboard(self.company)
        self.assertIsNone(board['classement'][0]['cost_per_result'])

    def test_language_label_exposed(self):
        self._asset('ar-ma', {'spend': 10, 'results': 1})
        board = reporting.language_leaderboard(self.company)
        self.assertEqual(
            board['classement'][0]['language_label'],
            'Darija (arabe marocain)')
