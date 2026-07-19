"""AGEN6 — Tests du routeur de paliers A/B/C + graduation.

Prouve (dd-assumption-engine §10.1) :
  * Palier C = types interdits, JAMAIS routés vers A/B (invariant), quels que
    soient les verdicts.
  * Palier A seulement si tout vert ET gabarit gradué.
  * Palier B pour tout le reste (une vérif rouge, ou gabarit non gradué).
  * graduation togglable ET révocable ; auto-graduation après N semaines propres.
"""
from django.core.cache import cache
from django.test import SimpleTestCase

from apps.adsengine import tier_router as tr
from apps.adsengine import groundedness


class _Co:
    def __init__(self, cid):
        self.id = cid


def _green_verdicts():
    return dict(
        claim_result={'ok': True},
        policy_result={'ok': True},
        groundedness_result={'tier': groundedness.TIER_A},
    )


class TierRouterTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.co = _Co(1)

    # ── Palier C — invariant ──
    def test_forbidden_type_is_always_c(self):
        for ctype in tr.FORBIDDEN_C_TYPES:
            r = tr.route_tier(self.co, content_type=ctype, **_green_verdicts(),
                              template_id='tmpl')
            self.assertEqual(r['tier'], tr.TIER_C)

    def test_forbidden_type_c_even_when_graduated_and_green(self):
        tr.set_template_graduated(self.co, 'tmpl', True)
        r = tr.route_tier(self.co, content_type='chantier_reel',
                          template_id='tmpl', **_green_verdicts())
        self.assertEqual(r['tier'], tr.TIER_C)  # jamais A malgré tout-vert+gradué

    # ── Palier A ──
    def test_all_green_and_graduated_is_a(self):
        tr.set_template_graduated(self.co, 'tmpl', True)
        r = tr.route_tier(self.co, content_type='static', template_id='tmpl',
                          **_green_verdicts())
        self.assertEqual(r['tier'], tr.TIER_A)
        self.assertTrue(r['all_green'])

    # ── Palier B ──
    def test_all_green_but_not_graduated_is_b(self):
        r = tr.route_tier(self.co, content_type='static', template_id='tmpl',
                          **_green_verdicts())
        self.assertEqual(r['tier'], tr.TIER_B)

    def test_one_red_check_is_b(self):
        tr.set_template_graduated(self.co, 'tmpl', True)
        verdicts = _green_verdicts()
        verdicts['claim_result'] = {'ok': False}
        r = tr.route_tier(self.co, content_type='static', template_id='tmpl',
                          **verdicts)
        self.assertEqual(r['tier'], tr.TIER_B)
        self.assertIn('claim_ok', r['reason'])

    def test_groundedness_b_routes_to_b(self):
        tr.set_template_graduated(self.co, 'tmpl', True)
        verdicts = _green_verdicts()
        verdicts['groundedness_result'] = {'tier': groundedness.TIER_B}
        r = tr.route_tier(self.co, content_type='static', template_id='tmpl',
                          **verdicts)
        self.assertEqual(r['tier'], tr.TIER_B)


class GraduationToggleTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.co = _Co(7)

    def test_default_off(self):
        self.assertFalse(tr.template_graduated(self.co, 'tmpl'))

    def test_toggle_on_off(self):
        tr.set_template_graduated(self.co, 'tmpl', True)
        self.assertTrue(tr.template_graduated(self.co, 'tmpl'))
        tr.set_template_graduated(self.co, 'tmpl', False)
        self.assertFalse(tr.template_graduated(self.co, 'tmpl'))

    def test_auto_graduate_after_n_clean_weeks(self):
        for _ in range(tr.CLEAN_WEEKS_FOR_GRADUATION - 1):
            tr.record_clean_week(self.co, 'tmpl')
        self.assertFalse(tr.template_graduated(self.co, 'tmpl'))
        tr.record_clean_week(self.co, 'tmpl')  # atteint le seuil
        self.assertTrue(tr.template_graduated(self.co, 'tmpl'))

    def test_revoke_graduation_resets(self):
        tr.set_template_graduated(self.co, 'tmpl', True)
        tr.revoke_graduation(self.co, 'tmpl')
        self.assertFalse(tr.template_graduated(self.co, 'tmpl'))
        self.assertEqual(tr.clean_weeks(self.co, 'tmpl'), 0)

    def test_graduation_is_per_company(self):
        other = _Co(99)
        tr.set_template_graduated(self.co, 'tmpl', True)
        self.assertFalse(tr.template_graduated(other, 'tmpl'))  # scope société
