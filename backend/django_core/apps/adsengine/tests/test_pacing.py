"""ADSENG20 — Tests du moteur de pacing (dd-treasury §a).

Prouve : les formules (linéaire + saisonnalité jour-de-semaine) sont exactes
et la courbe saisonnière atterrit EXACTEMENT au plafond en fin de mois ; la
prévision run-rate fin-de-mois est juste ; l'invariant « plafond jamais
dépassé » se déclenche AVANT le franchissement au flex Meta RÉEL 1,25×
(jamais 2×) ; les 5 états sont tous atteignables ; et le garde-fou G4 mesure
la variation hebdomadaire contre une VRAIE ligne de base à 7 jours — N pas
quotidiens dans la bande ne peuvent pas composer au-delà de la limite hebdo.
"""
import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.adsengine import pacing
from apps.adsengine.models import (
    AdCampaignMirror, AdSetMirror, EngineAction, GuardrailConfig,
    InsightSnapshot,
)


class PacingFormulaTests(TestCase):
    def test_flex_multiplier_is_the_verified_1_25(self):
        # SOURCE PRIMAIRE : 1,25× (pas 2×) — verrou anti-régression.
        self.assertEqual(pacing.META_DAILY_FLEX_MULTIPLIER, 1.25)

    def test_naive_linear_curve(self):
        # 3000 MAD sur 30 jours, 10 jours écoulés → 1000 MAD attendus.
        dim = pacing.days_in_month(2026, 6)  # juin = 30 jours
        self.assertEqual(dim, 30)
        self.assertAlmostEqual(
            pacing.naive_expected_spend(3000, 10, 30), 1000.0)

    def test_resolve_monthly_ceiling_derived_when_absent(self):
        company = Company.objects.create(nom='Mc', slug='mc')
        cfg = GuardrailConfig.objects.create(
            company=company, daily_budget_ceiling_mad=100)
        # Enveloppe mensuelle absente → dérivée = 100 × jours du mois.
        july = datetime.date(2026, 7, 1)  # juillet = 31 jours
        self.assertAlmostEqual(
            pacing.resolve_monthly_ceiling(cfg, july), 100 * 31)
        cfg.monthly_budget_ceiling_mad = 2500
        self.assertAlmostEqual(
            pacing.resolve_monthly_ceiling(cfg, july), 2500.0)

    def test_seasonality_curve_lands_exactly_on_ceiling_at_month_end(self):
        # Historique riche (> 28 j) pour sortir du démarrage à froid :
        # dépense constante → parts ≈ 1/7 → fin de mois : = plafond.
        start = datetime.date(2026, 6, 1)
        daily = {start - datetime.timedelta(days=i): 100 for i in range(40)}
        shares = pacing.weekday_shares(daily)
        end_expected = pacing.seasonality_expected_spend(
            3000, start, 30, shares)
        self.assertAlmostEqual(end_expected, 3000.0, places=6)
        # Jamais au-delà du plafond en cours de mois (monotone ≤ plafond).
        mid = pacing.seasonality_expected_spend(3000, start, 15, shares)
        self.assertLess(mid, 3000.0)

    def test_cold_start_uses_uniform_weekday_shares(self):
        # < 28 jours d'historique → parts uniformes 1/7 (plancher honnête).
        daily = {datetime.date(2026, 6, 1) + datetime.timedelta(days=i): 50
                 for i in range(5)}
        shares = pacing.weekday_shares(daily)
        for d in range(7):
            self.assertAlmostEqual(shares[d], 1.0 / 7.0)

    def test_forecast_run_rate(self):
        # Run-rate = moyenne 7 j ; prévision = à-date + rate × restant.
        as_of = datetime.date(2026, 6, 10)
        daily = {as_of - datetime.timedelta(days=i): 100 for i in range(7)}
        rate = pacing.trailing_run_rate(daily, as_of)
        self.assertAlmostEqual(rate, 100.0)
        # 20 jours restants → 1000 (à-date) + 100×20 = 3000.
        self.assertAlmostEqual(
            pacing.forecast_spend(1000, rate, 20), 3000.0)

    def test_pacing_ratio_floors_expected_at_one(self):
        # Jour 1, expected≈0 → dénominateur planché à 1 (anti-÷0).
        self.assertAlmostEqual(pacing.pacing_ratio(50, 0), 50.0)


class PacingInvariantTests(TestCase):
    """L'invariant « plafond jamais dépassé » au flex maximum 1,25×."""

    def test_breach_fires_before_the_ceiling_at_max_flex(self):
        # à-date 2950, plafond quotidien 100 → demain au flex 1,25× = +125
        # → 3075 > 3000 : on DÉTECTE le franchissement AVANT qu'il arrive.
        self.assertTrue(
            pacing.would_breach_at_max_flex(2950, 100, 3000))
        state = pacing.classify_state(
            ratio=1.0, forecast=2960, spend_to_date=2950,
            daily_ceiling=100, monthly_ceiling=3000, band_pct=15)
        self.assertEqual(state, pacing.STATE_BREACH_IMMINENT)

    def test_no_false_breach_when_flex_day_stays_within_envelope(self):
        # à-date 1000, +125 au flex = 1125 << 3000 (prévision sous plafond).
        self.assertFalse(
            pacing.would_breach_at_max_flex(1000, 100, 3000))
        state = pacing.classify_state(
            ratio=1.0, forecast=2000, spend_to_date=1000,
            daily_ceiling=100, monthly_ceiling=3000, band_pct=15)
        self.assertEqual(state, pacing.STATE_ON_TRACK)

    def test_forecast_over_ceiling_is_breach_even_if_flex_day_fits(self):
        # Prévision run-rate > plafond → breach (2e branche de l'invariant).
        state = pacing.classify_state(
            ratio=1.3, forecast=3200, spend_to_date=1500,
            daily_ceiling=50, monthly_ceiling=3000, band_pct=15)
        self.assertEqual(state, pacing.STATE_BREACH_IMMINENT)


class PacingStateTableTests(TestCase):
    def test_five_states_all_reachable(self):
        # under
        self.assertEqual(
            pacing.classify_state(
                ratio=0.5, forecast=1000, spend_to_date=500,
                daily_ceiling=100, monthly_ceiling=3000, band_pct=15),
            pacing.STATE_UNDER_PACING)
        # on_track
        self.assertEqual(
            pacing.classify_state(
                ratio=1.0, forecast=1000, spend_to_date=500,
                daily_ceiling=100, monthly_ceiling=3000, band_pct=15),
            pacing.STATE_ON_TRACK)
        # over (mais prévision sous plafond → pas breach)
        self.assertEqual(
            pacing.classify_state(
                ratio=1.4, forecast=2500, spend_to_date=1200,
                daily_ceiling=50, monthly_ceiling=3000, band_pct=15),
            pacing.STATE_OVER_PACING)
        # breach
        self.assertEqual(
            pacing.classify_state(
                ratio=1.4, forecast=3500, spend_to_date=1200,
                daily_ceiling=50, monthly_ceiling=3000, band_pct=15),
            pacing.STATE_BREACH_IMMINENT)
        # paused_for_month prime sur tout
        self.assertEqual(
            pacing.classify_state(
                ratio=1.4, forecast=3500, spend_to_date=1200,
                daily_ceiling=50, monthly_ceiling=3000, band_pct=15,
                already_paused=True),
            pacing.STATE_PAUSED_FOR_MONTH)

    def test_states_match_pacing_state_model_choices(self):
        from apps.adsengine.models import PacingState
        self.assertEqual(
            pacing.PACING_STATES,
            {c[0] for c in PacingState.State.choices})

    def test_recommended_action_mapping(self):
        self.assertEqual(
            pacing.recommended_action_for_state(pacing.STATE_UNDER_PACING),
            pacing.KIND_INCREASE_PACE)
        self.assertEqual(
            pacing.recommended_action_for_state(pacing.STATE_BREACH_IMMINENT),
            pacing.KIND_PAUSE_FOR_MONTH)
        self.assertIsNone(
            pacing.recommended_action_for_state(pacing.STATE_ON_TRACK))
        self.assertIsNone(
            pacing.recommended_action_for_state(pacing.STATE_OVER_PACING))


class WeeklyBaselineG4Tests(TestCase):
    """G4 — vraie ligne de base à 7 jours, jamais une transition/jour."""

    # Référence fixe à MIDI (marges ≥ 3 jours → insensible au décalage de
    # fuseau autour de minuit, pas de flakiness #29).
    AS_OF = datetime.date(2026, 7, 20)
    REF = datetime.datetime(2026, 7, 20, 12, 0)

    def setUp(self):
        self.company = Company.objects.create(nom='G4', slug='g4')

    def _applied_change(self, adset_id, new_mad, applied_days_ago):
        naive = self.REF - datetime.timedelta(days=applied_days_ago)
        when = timezone.make_aware(naive) if timezone.is_naive(naive) \
            else naive
        return EngineAction.objects.create(
            company=self.company, kind=pacing.KIND_REBALANCE_ADSET_BUDGET,
            reason_fr='Rééquilibrage bandit.',
            status=EngineAction.Statut.APPLIQUEE,
            payload={'adset_id': adset_id,
                     'daily_budget': int(round(new_mad * 100)),
                     'new_daily_budget_mad': new_mad},
            applied_at=when)

    def test_baseline_is_the_seven_day_old_budget(self):
        # Changements: il y a 10 j (100 MAD), 5 j (112), 2 j (125).
        self._applied_change('as1', 100.0, 10)
        self._applied_change('as1', 112.0, 5)
        self._applied_change('as1', 125.0, 2)
        base = pacing.weekly_baseline_budget_mad(
            self.company, 'as1', as_of=self.AS_OF)
        # Seule l'action <= as_of-7j (il y a 10 j) est l'ancre → 100 MAD.
        self.assertAlmostEqual(base, 100.0)

    def test_no_anchor_returns_none(self):
        self._applied_change('as1', 100.0, 2)  # trop récent (< 7 j)
        self.assertIsNone(
            pacing.weekly_baseline_budget_mad(
                self.company, 'as1', as_of=self.AS_OF))

    def test_successive_within_band_changes_cannot_compound_past_weekly_limit(
            self):
        # Ancre 7 j = 100 MAD. Chaque pas quotidien +14% reste sous 15%/j,
        # MAIS 3 pas → 100×1.14^3 ≈ 148 (+48%). La garde hebdo (vs ancre)
        # (contre l'ancre à 7 j, max 20%) REFUSE tout ce qui dépasse 120 MAD.
        as_of = self.AS_OF
        self._applied_change('as1', 100.0, 10)  # ancre 7 j
        # 148 MAD proposé (composé) : refusé (48% > 20% vs ancre).
        self.assertFalse(
            pacing.weekly_change_within_baseline(
                148.0, pacing.weekly_baseline_budget_mad(
                    self.company, 'as1', as_of=as_of), 20))
        # 118 MAD (18% vs ancre) : accepté.
        self.assertTrue(
            pacing.weekly_change_within_baseline(
                118.0, pacing.weekly_baseline_budget_mad(
                    self.company, 'as1', as_of=as_of), 20))

    def test_within_baseline_true_when_no_anchor(self):
        # Pas d'ancre → repli documenté : la garde hebdo ne bloque pas (le
        # plafond par-transition gouverne ailleurs).
        self.assertTrue(pacing.weekly_change_within_baseline(999.0, None, 20))


class PacingForCompanyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Pc', slug='pc')
        self.cfg = GuardrailConfig.objects.create(
            company=self.company, daily_budget_ceiling_mad=100,
            monthly_budget_ceiling_mad=3000, pacing_band_pct=15)

    def _campaign_spend(self, date, spend):
        camp = AdCampaignMirror.objects.filter(company=self.company).first()
        if camp is None:
            camp = AdCampaignMirror.objects.create(
                company=self.company, meta_id='c1')
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=camp.pk,
            date=date, spend=Decimal(str(spend)))

    def test_reads_campaign_level_spend_only(self):
        as_of = datetime.date(2026, 7, 10)
        start = datetime.date(2026, 7, 1)
        for i in range(10):
            self._campaign_spend(start + datetime.timedelta(days=i), 100)
        result = pacing.compute_pacing_for_company(
            self.company, as_of=as_of, config=self.cfg)
        # 10 jours × 100 = 1000 MAD à date.
        self.assertAlmostEqual(result.spend_to_date, 1000.0)
        self.assertEqual(result.monthly_ceiling, 3000.0)
        self.assertEqual(result.days_elapsed, 10)
        self.assertIn(result.state, pacing.PACING_STATES)

    def test_does_not_double_count_adset_level(self):
        # Une dépense d'ad set NE DOIT PAS gonfler le total (campagne seul).
        as_of = datetime.date(2026, 7, 3)
        start = datetime.date(2026, 7, 1)
        self._campaign_spend(start, 100)
        adset = AdSetMirror.objects.create(company=self.company, meta_id='as1')
        ct = ContentType.objects.get_for_model(AdSetMirror)
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=adset.pk,
            date=start, spend=Decimal('100'))
        result = pacing.compute_pacing_for_company(
            self.company, as_of=as_of, config=self.cfg)
        self.assertAlmostEqual(result.spend_to_date, 100.0)
