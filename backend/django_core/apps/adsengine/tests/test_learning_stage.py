"""ADSDEEP32 — learning_stage_info par ad set : sync, badge, avertissement reset.

Prouve : (a) ``tasks.sync_adset_learning`` miroite status/last_sig_edit + le dict
brut depuis un client mocké ; (b) le sérialiseur expose le badge d'apprentissage ;
(c) la logique d'avertissement de reset (budget > 20 % / créatif) est correcte.
Aucun réseau (client factice) ; aucune activation (le miroir reflète l'état Meta).
"""
import datetime

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import tasks
from apps.adsengine.models import AdSetMirror
from apps.adsengine.serializers import AdSetMirrorSerializer


class FakeAdsetClient:
    """Client factice : ``get_adsets(fields=...)`` renvoie des lignes fixes."""

    def __init__(self, rows):
        self._rows = rows
        self.calls = []

    def get_adsets(self, *, fields=None, limit=None):
        self.calls.append(fields)
        return self._rows


class SyncAdsetLearningTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Learn Co', slug='learn-co')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-1', name='AdSet 1')

    def test_syncs_status_and_last_sig_edit(self):
        ts = 1_700_000_000  # unix
        client = FakeAdsetClient([{
            'id': 'as-1',
            'learning_stage_info': {
                'status': 'LEARNING', 'conversions': 12,
                'last_sig_edit_ts': ts,
                'attribution_windows': ['7d_click']},
        }])
        updated = tasks.sync_adset_learning(self.company, client)
        self.assertEqual(updated, 1)
        # Le champ learning_stage_info a bien été demandé à l'API.
        self.assertIn('learning_stage_info', client.calls[0])
        self.adset.refresh_from_db()
        self.assertEqual(self.adset.learning_status, 'LEARNING')
        self.assertTrue(self.adset.is_learning)
        self.assertEqual(self.adset.learning_stage_info['conversions'], 12)
        self.assertIsNotNone(self.adset.last_sig_edit)
        self.assertEqual(
            self.adset.last_sig_edit,
            datetime.datetime.fromtimestamp(ts, datetime.timezone.utc))

    def test_unknown_status_normalized_to_empty(self):
        client = FakeAdsetClient([{
            'id': 'as-1',
            'learning_stage_info': {'status': 'WHATEVER'}}])
        tasks.sync_adset_learning(self.company, client)
        self.adset.refresh_from_db()
        self.assertEqual(self.adset.learning_status, '')
        self.assertFalse(self.adset.is_learning)

    def test_success_status_and_iso_timestamp(self):
        client = FakeAdsetClient([{
            'id': 'as-1',
            'learning_stage_info': {
                'status': 'SUCCESS',
                'last_sig_edit_ts': '2026-06-01T10:00:00Z'}}])
        tasks.sync_adset_learning(self.company, client)
        self.adset.refresh_from_db()
        self.assertEqual(self.adset.learning_status, 'SUCCESS')
        self.assertEqual(self.adset.last_sig_edit.year, 2026)

    def test_noop_when_client_has_no_get_adsets(self):
        self.assertEqual(
            tasks.sync_adset_learning(self.company, object()), 0)


class LearningBadgeSerializerTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Badge Co', slug='badge-co')

    def test_badge_for_learning(self):
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-2', learning_status='LEARNING')
        badge = AdSetMirrorSerializer(adset).data['learning_badge']
        self.assertEqual(badge['status'], 'LEARNING')
        self.assertEqual(badge['label'], 'En apprentissage')
        self.assertTrue(badge['is_learning'])

    def test_badge_for_unknown_is_neutral(self):
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-3')
        data = AdSetMirrorSerializer(adset).data
        self.assertEqual(data['learning_status'], '')
        self.assertEqual(data['learning_badge']['tone'], 'neutral')
        self.assertFalse(data['learning_badge']['is_learning'])


class LearningResetWarningTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Warn Co', slug='warn-co')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-4', learning_status='LEARNING')

    def test_budget_over_20pct_warns(self):
        warns = self.adset.learning_reset_warnings(
            current_budget_mad=100, new_budget_mad=125)  # +25 %
        self.assertIn(
            'apprentissage', ' '.join(warns))
        self.assertEqual(len(warns), 1)

    def test_budget_at_or_below_20pct_no_warning(self):
        # Exactement 20 % (seuil strict >) → aucun avertissement.
        self.assertEqual(
            self.adset.learning_reset_warnings(
                current_budget_mad=100, new_budget_mad=120), [])
        self.assertEqual(
            self.adset.learning_reset_warnings(
                current_budget_mad=100, new_budget_mad=110), [])

    def test_creative_change_warns(self):
        warns = self.adset.learning_reset_warnings(creative_change=True)
        self.assertEqual(len(warns), 1)
        self.assertIn('créatif', warns[0])

    def test_creative_and_budget_both_warn(self):
        warns = self.adset.learning_reset_warnings(
            current_budget_mad=100, new_budget_mad=200, creative_change=True)
        self.assertEqual(len(warns), 2)

    def test_no_current_budget_is_safe(self):
        self.assertEqual(
            self.adset.learning_reset_warnings(
                current_budget_mad=0, new_budget_mad=100), [])
        self.assertEqual(
            self.adset.learning_reset_warnings(new_budget_mad=100), [])
