"""PUB82 — Rétention par scène de script (beat ↔ percentile vidéo).

Prouve : les *beats* du script se persistent sur l'asset ; le reporting relie
chaque percentile de rétention (p25/50/75/100) à la SCÈNE jouée + sa valeur de
rétention (jamais un chiffre fabriqué quand la mesure manque).
"""
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import reporting, video_queue
from apps.adsengine.models import CreativeAsset

BEATS = [
    {'text': 'Passez au solaire', 'fact_key': None},
    {'text': 'Économisez chaque mois', 'fact_key': 'economie'},
    {'text': 'Le prix : 60 000 MAD', 'fact_key': 'prix'},
    {'text': 'Contactez-nous', 'fact_key': None},
]


class ScriptBeatPersistTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Beat Co', slug='beat-co')

    def test_persist_script_beats(self):
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.EXPLAINER)
        video_queue.persist_script_beats(asset, {'lines': BEATS})
        asset.refresh_from_db()
        self.assertEqual(len(asset.script_beats), 4)
        self.assertEqual(asset.script_beats[2]['text'], 'Le prix : 60 000 MAD')


class BeatRetentionMapTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Ret Co', slug='ret-co')

    def _asset(self, retention):
        return CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.EXPLAINER,
            script_beats=BEATS, perf={'retention': retention})

    def test_mapping_links_percentile_to_scene(self):
        asset = self._asset({'p25': 0.8, 'p50': 0.55, 'p75': 0.3, 'p100': 0.1})
        result = reporting.script_beat_retention(asset)
        self.assertEqual(result['beat_count'], 4)
        rows = {r['percentile']: r for r in result['mapping']}
        # p50 (la moitié du film) tombe sur la scène du prix (index 2).
        self.assertEqual(rows[50]['beat_index'], 2)
        self.assertIn('prix', rows[50]['beat_text'])
        self.assertEqual(rows[50]['retention'], 0.55)
        # p100 pointe la dernière scène (CTA).
        self.assertEqual(rows[100]['beat_index'], 3)

    def test_missing_retention_is_none_not_zero(self):
        asset = self._asset({'p25': 0.8})  # p50/p75/p100 absents
        rows = {r['percentile']: r
                for r in reporting.script_beat_retention(asset)['mapping']}
        self.assertEqual(rows[25]['retention'], 0.8)
        self.assertIsNone(rows[50]['retention'])  # jamais un 0 fabriqué

    def test_no_beats_gives_empty_mapping(self):
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.REEL,
            perf={'retention': {'p25': 0.9}})
        result = reporting.script_beat_retention(asset)
        self.assertEqual(result['beat_count'], 0)
        self.assertTrue(all(r['beat_index'] is None for r in result['mapping']))
