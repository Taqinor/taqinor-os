"""ADSENG25 — Tests du protocole de rotation créative.

Prouve : la composition 1 champion + 2 challengers, le rythme du lundi, la
sortie bandit (règle des deux coups), l'entrée depuis le backlog, et surtout
l'INVARIANT porteur — **jamais deux ajouts par rotation** (ration stricte),
même quand deux slots sont libres et que le backlog déborde. Logique pure.
"""
import datetime

from django.test import SimpleTestCase

from apps.adsengine import rotation as rot


def _arm(arm_id, *, p_best, weak_streak=0, is_champion=False, age_days=14,
         impressions=5000, frequency=1.0, is_active=True):
    return rot.ArmSnapshot(
        arm_id=arm_id, is_champion=is_champion, age_days=age_days,
        impressions=impressions, frequency=frequency, p_best=p_best,
        weak_streak=weak_streak, is_active=is_active)


class CompositionTests(SimpleTestCase):
    def test_adset_composition_is_one_champion_two_challengers(self):
        self.assertEqual(rot.CHAMPION_COUNT, 1)
        self.assertEqual(rot.CHALLENGER_COUNT, 2)
        self.assertEqual(rot.ADS_PER_ADSET, 3)

    def test_rotation_day_is_monday(self):
        # 2026-07-13 est un lundi ; 2026-07-14 un mardi.
        self.assertTrue(rot.is_rotation_day(datetime.date(2026, 7, 13)))
        self.assertFalse(rot.is_rotation_day(datetime.date(2026, 7, 14)))


class ExitCriterionTests(SimpleTestCase):
    def test_two_strike_rule_exits_only_after_second_weak_week(self):
        # Semaine 1 : faible une fois (streak=1) → pas de sortie.
        arm_w1 = _arm('A', p_best=0.05, weak_streak=1)
        other = _arm('B', p_best=0.80)
        d1 = rot.plan_rotation([arm_w1, other],
                               today=datetime.date(2026, 7, 13))
        self.assertNotIn('A', d1.exits)
        # Semaine 2 : encore faible (streak=2) ET un autre meilleur → sortie.
        arm_w2 = _arm('A', p_best=0.05, weak_streak=2)
        d2 = rot.plan_rotation([arm_w2, other],
                               today=datetime.date(2026, 7, 20))
        self.assertIn('A', d2.exits)

    def test_no_exit_before_exploration_floor(self):
        # Deux coups faibles mais exploration incomplète (< 1000 impressions).
        young = _arm('A', p_best=0.02, weak_streak=3, age_days=3,
                     impressions=200)
        strong = _arm('B', p_best=0.90)
        d = rot.plan_rotation([young, strong])
        self.assertNotIn('A', d.exits)

    def test_champion_not_exited_on_calendar_alone(self):
        # Champion vieux (>3 sem) mais PAS un perdant bandit → jamais retiré.
        old_champ = _arm('C', p_best=0.60, is_champion=True, age_days=40,
                         weak_streak=0)
        chal = _arm('D', p_best=0.20)
        d = rot.plan_rotation([old_champ, chal])
        self.assertNotIn('C', d.exits)
        self.assertNotIn('C', d.reviews)

    def test_next_weak_streak_helper(self):
        self.assertEqual(rot.next_weak_streak(1, 0.05), 2)
        self.assertEqual(rot.next_weak_streak(3, 0.50), 0)


class RationTests(SimpleTestCase):
    def test_never_two_adds_when_two_slots_free(self):
        # Un seul ad vivant (2 slots libres) + backlog de 5 candidats.
        lone = _arm('A', p_best=0.90)
        backlog = [f'item-{i}' for i in range(5)]
        d = rot.plan_rotation([lone], backlog=backlog)
        # RATION STRICTE : exactement un ajout, jamais deux — malgré 2 slots.
        self.assertEqual(d.added_count, 1)
        self.assertLessEqual(len(d.entries), rot.MAX_NEW_ADS_PER_ROTATION)

    def test_full_slots_add_nothing(self):
        arms = [_arm('A', p_best=0.5, is_champion=True),
                _arm('B', p_best=0.3), _arm('C', p_best=0.2)]
        d = rot.plan_rotation(arms, backlog=['x', 'y'])
        self.assertEqual(d.added_count, 0)

    def test_empty_backlog_adds_nothing(self):
        lone = _arm('A', p_best=0.9)
        d = rot.plan_rotation([lone], backlog=[])
        self.assertEqual(d.added_count, 0)


class FullCycleTests(SimpleTestCase):
    def test_full_rotation_cycle_on_fixtures(self):
        # Champion fort, un challenger perdant (2 coups), un challenger sain.
        champion = _arm('CH', p_best=0.70, is_champion=True)
        loser = _arm('L', p_best=0.04, weak_streak=2)
        healthy = _arm('H', p_best=0.26)
        backlog = ['new-1', 'new-2', 'new-3']
        d = rot.plan_rotation(
            [champion, loser, healthy], backlog=backlog,
            today=datetime.date(2026, 7, 13), objective='LEADS',
            audience='CASA')
        # Le perdant sort (pause), le champion reste.
        self.assertIn('L', d.exits)
        self.assertNotIn('CH', d.exits)
        # Une sortie libère un slot → exactement UNE entrée (ration).
        self.assertEqual(d.added_count, 1)
        entry = d.entries[0]
        # La lignée est encodée dans le nom (objectif/audience) — ADSENG23.
        self.assertIn('LEADS', entry.launch_name)
        self.assertIn('CASA', entry.launch_name)
        self.assertTrue(d.reasons_fr)

    def test_launch_name_prefers_injected_identity(self):
        lone = _arm('A', p_best=0.9)

        def fake_identity(*, objective, audience, variant):
            return f'ID::{objective}::{audience}::{variant}'

        d = rot.plan_rotation([lone], backlog=['seed'],
                              identity_fn=fake_identity, objective='LEADS',
                              audience='RES')
        self.assertTrue(
            d.entries[0].launch_name.startswith('ID::LEADS::RES::'))
