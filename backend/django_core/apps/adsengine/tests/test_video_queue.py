"""AGEN7 — Tests de la chaîne vidéo automatisée (mocked, aucun réseau).

Prouve :
  * le script est ANCRÉ sur la table de faits publiée (valeur citée depuis une
    ``FactEntry``), et sans table publiée aucun chiffre n'apparaît ;
  * la chaîne de bout en bout (voix ElevenLabs → montage JSON2Video) produit un
    ``CreativeAsset`` EXPLAINER TOUJOURS en policy PENDING (``policy_stamp={}``),
    lié à la voix ;
  * NO-OP propre sans clé JSON2Video ;
  * palier B minimum : le palier A est refusé ;
  * un gabarit en quarantaine (AGEN9) ne génère plus (no-op).
"""
import datetime
import os
from unittest.mock import Mock, patch

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import video_queue
from apps.adsengine.models import CreativeAsset, FactTable, FactEntry


class GroundedScriptTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='VQ Co', slug='vq-co')

    def test_script_grounds_on_published_fact(self):
        table = FactTable.create_draft(self.company)
        FactEntry.objects.create(
            company=self.company, table=table, cle='economie_pct',
            valeur='40', unite='%', source='Étude interne',
            verifie_le=datetime.date(2026, 1, 1))
        table.publish()
        script = video_queue.build_grounded_script(
            self.company, template_key='eco',
            beats=[{'text': "Économisez jusqu'à", 'fact_key': 'economie_pct'}])
        self.assertEqual(script['facts_version'], table.version)
        self.assertEqual(script['cited_keys'], ['economie_pct'])
        # La valeur VÉRIFIÉE est citée, jamais fabriquée.
        self.assertIn('40 %', script['lines'][0]['text'])

    def test_no_published_table_yields_no_numeric_claim(self):
        # Aucune table publiée : la fact_key est ignorée, aucun chiffre injecté.
        script = video_queue.build_grounded_script(
            self.company, beats=[{'text': 'Solaire', 'fact_key': 'economie_pct'}])
        self.assertIsNone(script['facts_version'])
        self.assertEqual(script['cited_keys'], [])
        self.assertEqual(script['lines'][0]['text'], 'Solaire')


class VideoChainTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='VC Co', slug='vc-co')

    def _run_chain(self, env):
        cf = 'apps.adsengine.creative_factory'
        with patch.dict(os.environ, env, clear=False), \
             patch(f'{cf}._store_bytes',
                   side_effect=lambda *a, **k: 'adsengine/1/x.bin'), \
             patch(f'{cf}.ElevenlabsAdapter.submit', return_value=b'AUDIO'), \
             patch(f'{cf}.ElevenlabsAdapter.poll', side_effect=lambda c, j: j), \
             patch(f'{cf}.Json2videoAdapter.submit', return_value='movie1'), \
             patch(f'{cf}.Json2videoAdapter.poll', return_value=b'VIDEO'):
            return video_queue.generate_video(
                self.company, template_key='eco', http_client=Mock())

    def test_end_to_end_creates_pending_explainer_linked_to_voice(self):
        video = self._run_chain(
            {'ELEVENLABS_API_KEY': 'k', 'JSON2VIDEO_API_KEY': 'k'})
        self.assertIsNotNone(video)
        self.assertEqual(video.asset_type, CreativeAsset.AssetType.EXPLAINER)
        # TOUJOURS pending — jamais validé automatiquement.
        self.assertEqual(video.policy_stamp, {})
        self.assertFalse(video.is_policy_passed)
        # Lié au composant voix (chaîne).
        self.assertIsNotNone(video.parent)
        self.assertEqual(video.parent.source_lane, 'elevenlabs')
        # Deux assets : voix + vidéo, tous deux pending.
        self.assertEqual(CreativeAsset.objects.count(), 2)
        for a in CreativeAsset.objects.all():
            self.assertEqual(a.policy_stamp, {})

    def test_noop_without_json2video_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('JSON2VIDEO_API_KEY', None)
            os.environ.pop('ELEVENLABS_API_KEY', None)
            video = video_queue.generate_video(
                self.company, template_key='eco', http_client=Mock())
        self.assertIsNone(video)
        self.assertEqual(CreativeAsset.objects.count(), 0)

    def test_video_without_voice_key_still_produces_pending_video(self):
        with patch.dict(os.environ, {'JSON2VIDEO_API_KEY': 'k'}, clear=False):
            os.environ.pop('ELEVENLABS_API_KEY', None)
            with patch('apps.adsengine.creative_factory._store_bytes',
                       side_effect=lambda *a, **k: 'adsengine/1/x.bin'), \
                 patch('apps.adsengine.creative_factory.Json2videoAdapter.submit',
                       return_value='movie1'), \
                 patch('apps.adsengine.creative_factory.Json2videoAdapter.poll',
                       return_value=b'VIDEO'):
                video = video_queue.generate_video(
                    self.company, template_key='eco', http_client=Mock())
        self.assertIsNotNone(video)
        self.assertIsNone(video.parent)  # pas de voix
        self.assertEqual(video.policy_stamp, {})


class TierAndQuarantineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='TQ Co', slug='tq-co')

    def test_tier_a_rejected(self):
        with self.assertRaises(ValueError):
            video_queue.generate_video(self.company, tier='A')

    def test_min_tier_is_b(self):
        self.assertEqual(video_queue.video_min_tier(), 'B')

    def test_quarantined_template_does_not_generate(self):
        from apps.adsengine import generation_audit
        generation_audit.quarantine_template(self.company, 'eco')
        with patch.dict(os.environ,
                        {'JSON2VIDEO_API_KEY': 'k'}, clear=False):
            video = video_queue.generate_video(
                self.company, template_key='eco', http_client=Mock())
        self.assertIsNone(video)
        self.assertEqual(CreativeAsset.objects.count(), 0)
