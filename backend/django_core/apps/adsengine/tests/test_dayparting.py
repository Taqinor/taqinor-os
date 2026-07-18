"""ADSDEEP36 — Dayparting : horaire NATIF (adset_schedule, lifetime budget) OU
planification INTERNE (budget quotidien, jamais un adrule Meta auto-exécuté).

Couvre les DEUX chemins : conversion grille→blocs natifs (bornes à l'heure
pleine, fusion des heures consécutives), rejet d'un ``set_adset_schedule`` dont
une borne n'est pas à l'heure pleine, et le chemin interne qui ne peut JAMAIS
proposer autre chose qu'une PAUSE (aucune méthode de réactivation n'existe —
invariant permanent règle #3).
"""
import datetime
from unittest.mock import Mock

import httpx
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company

from apps.adsengine import dayparting
from apps.adsengine import meta_client as mc
from apps.adsengine import services
from apps.adsengine.models import AdSetMirror, EngineAction

User = get_user_model()

TOKEN = 'tok-daypart'


def make_client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1', http_client=http_client,
        max_retries=0, backoff_base=0, **kwargs)


class GridConversionTests(SimpleTestCase):
    def test_empty_grid_all_allowed_by_default(self):
        grid = dayparting.empty_grid()
        for day in dayparting.DAYS:
            self.assertEqual(grid[day], [1] * 24)

    def test_validate_grid_rejects_missing_day(self):
        grid = dayparting.empty_grid()
        del grid['sun']
        with self.assertRaises(dayparting.DaypartingError):
            dayparting.validate_grid(grid)

    def test_validate_grid_rejects_wrong_row_length(self):
        grid = dayparting.empty_grid()
        grid['mon'] = [1] * 23
        with self.assertRaises(dayparting.DaypartingError):
            dayparting.validate_grid(grid)

    def test_native_conversion_merges_consecutive_hours_and_whole_hour_bounds(self):
        grid = dayparting.empty_grid(allowed=False)
        # Lundi : allumé de 9h à 12h (3 heures) → UN seul bloc 540-720 minutes.
        grid['mon'][9] = grid['mon'][10] = grid['mon'][11] = 1
        blocks = dayparting.to_native_adset_schedule(grid)
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        self.assertEqual(block['start_minute'], 9 * 60)
        self.assertEqual(block['end_minute'], 12 * 60)
        self.assertEqual(block['start_minute'] % 60, 0)
        self.assertEqual(block['end_minute'] % 60, 0)
        # Index Meta lundi = 1 (0=dimanche..6=samedi).
        self.assertEqual(block['days'], [1])

    def test_native_conversion_separates_non_consecutive_windows(self):
        grid = dayparting.empty_grid(allowed=False)
        grid['tue'][8] = 1
        grid['tue'][18] = 1  # non consécutif → 2 blocs
        blocks = dayparting.to_native_adset_schedule(grid)
        self.assertEqual(len(blocks), 2)

    def test_full_day_allowed_produces_one_block_per_day(self):
        grid = dayparting.empty_grid(allowed=True)
        blocks = dayparting.to_native_adset_schedule(grid)
        self.assertEqual(len(blocks), 7)
        for b in blocks:
            self.assertEqual(b['start_minute'], 0)
            self.assertEqual(b['end_minute'], 24 * 60)


class InternalPauseNeededTests(SimpleTestCase):
    def test_paused_already_never_re_proposed(self):
        grid = dayparting.empty_grid(allowed=False)  # tout bloqué
        now = datetime.datetime(2026, 7, 20, 10, 0)  # lundi
        self.assertFalse(
            dayparting.internal_pause_needed(
                grid, now=now, is_currently_paused=True))

    def test_out_of_window_and_not_paused_needs_pause(self):
        grid = dayparting.empty_grid(allowed=False)
        now = datetime.datetime(2026, 7, 20, 3, 0)  # lundi 3h, rien d'allumé
        self.assertTrue(
            dayparting.internal_pause_needed(
                grid, now=now, is_currently_paused=False))

    def test_inside_window_no_pause_needed(self):
        grid = dayparting.empty_grid(allowed=False)
        grid['mon'][10] = 1
        now = datetime.datetime(2026, 7, 20, 10, 30)  # lundi 10h → allumé
        self.assertFalse(
            dayparting.internal_pause_needed(
                grid, now=now, is_currently_paused=False))


class MetaClientScheduleTests(SimpleTestCase):
    def test_set_adset_schedule_sends_no_status(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'success': True})

        client = make_client(handler)
        blocks = [{'days': [1], 'start_minute': 540, 'end_minute': 720,
                   'timezone_type': 'USER'}]
        client.set_adset_schedule(adset_id='as-1', adset_schedule=blocks)
        body = captured['request'].content.decode('utf-8')
        self.assertNotIn('status', body)
        self.assertIn('adset_schedule', body)

    def test_rejects_non_hour_boundary(self):
        client = make_client(lambda r: httpx.Response(200, json={}))
        bad = [{'days': [1], 'start_minute': 545, 'end_minute': 600}]
        with self.assertRaises(mc.MetaError):
            client.set_adset_schedule(adset_id='as-1', adset_schedule=bad)


class ProposeNativeScheduleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='DP Co', slug='dp-co')
        self.user = User.objects.create_user(
            username='dp-approver', password='x', company=self.company)

    def test_native_schedule_cycle_reaches_client(self):
        grid = dayparting.empty_grid(allowed=False)
        grid['wed'][14] = 1
        action = services.propose_native_schedule(
            self.company, adset_id='as-9', grid=grid)
        self.assertEqual(action.kind, services.KIND_SET_SCHEDULE)
        services.approve_action(action, user=self.user)
        client = Mock()
        client.set_adset_schedule.return_value = {'success': True}
        services.apply_action(action, client=client)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        client.set_adset_schedule.assert_called_once()
        _, kwargs = client.set_adset_schedule.call_args
        self.assertEqual(kwargs['adset_id'], 'as-9')
        self.assertTrue(len(kwargs['adset_schedule']) >= 1)


class ProposeInternalDaypartingPauseTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='DP Internal Co', slug='dp-int-co')

    def _adset(self, status=''):
        return AdSetMirror.objects.create(
            company=self.company, meta_id='as-int-1', name='AdSet quotidien',
            status=status)

    def test_no_pause_proposed_inside_window(self):
        adset = self._adset()
        grid = dayparting.empty_grid(allowed=True)
        result = services.propose_internal_dayparting_pause(
            self.company, adset=adset, grid=grid, now=timezone.now())
        self.assertIsNone(result)
        self.assertEqual(EngineAction.objects.count(), 0)

    def test_pause_proposed_outside_window_never_activation_kind(self):
        adset = self._adset(status='ACTIVE')
        grid = dayparting.empty_grid(allowed=False)
        now = timezone.make_aware(datetime.datetime(2026, 7, 20, 2, 0))
        action = services.propose_internal_dayparting_pause(
            self.company, adset=adset, grid=grid, now=now)
        self.assertIsNotNone(action)
        # Le SEUL kind jamais produit par ce chemin est PAUSE (aucune méthode
        # de réactivation n'existe côté client — invariant permanent règle #3).
        self.assertEqual(action.kind, EngineAction.Kind.PAUSE)
        self.assertEqual(action.payload['target_meta_id'], 'as-int-1')

    def test_no_pause_reproposed_if_already_paused(self):
        adset = self._adset(status='PAUSED')
        grid = dayparting.empty_grid(allowed=False)
        result = services.propose_internal_dayparting_pause(
            self.company, adset=adset, grid=grid, now=timezone.now())
        self.assertIsNone(result)
