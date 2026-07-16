"""ADSENG9 — Tests récompense proxy + détecteur de divergence CRM/proxy.

Prouve (dd-science-core §2.7) :
  * la récompense proxy = conversations / impressions (0 si 0 impression) ;
  * le cœur PUR ``evaluate_divergence`` : convergence ⇒ rien ; un écart d'une
    seule position = bruit (rien) ; un écart ≥ 2 positions AVEC ≥ 10 leads
    qualifiés ⇒ divergence ; sous 10 leads ⇒ rien ;
  * la boucle I/O ``run_divergence_check`` lève une ``EngineAction`` propose-only
    (``auto=False``, ``status='proposee'``) en cas de divergence synthétique, et
    JAMAIS d'action en convergence — jamais d'action auto.
"""
import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.crm.stages import CONTACTED

from apps.adsengine import rewards
from apps.adsengine.models import (
    AdCampaignMirror, AdMirror, AdSetMirror, ArmDailyStat, EngineAction,
    Experiment, ExperimentArm, InsightSnapshot,
)


class ProxyRewardTests(SimpleTestCase):
    def test_ratio(self):
        self.assertAlmostEqual(rewards.proxy_reward(1000, 40), 0.04)

    def test_zero_impressions_is_zero(self):
        self.assertEqual(rewards.proxy_reward(0, 5), 0.0)

    def test_negative_conversions_floored(self):
        self.assertEqual(rewards.proxy_reward(100, -3), 0.0)


def _arm(label, proxy, crm_cost, qualified):
    return {'label': label, 'proxy': proxy,
            'crm_cost': crm_cost, 'qualified': qualified}


class EvaluateDivergenceTests(SimpleTestCase):
    def test_convergence_no_divergence(self):
        # Classements identiques (proxy A>B>C ; coût A<B<C) ⇒ rien.
        arms = [_arm('A', 0.04, 10.0, 6),
                _arm('B', 0.03, 20.0, 4),
                _arm('C', 0.02, 30.0, 2)]
        d = rewards.evaluate_divergence(arms)
        self.assertFalse(d['diverged'])
        self.assertEqual(d['max_rank_gap'], 0)
        self.assertEqual(d['reason_fr'], '')

    def test_single_position_swap_is_noise(self):
        # Échange adjacent (B et C permutés côté coût) ⇒ écart max = 1 ⇒ bruit.
        arms = [_arm('A', 0.04, 10.0, 6),
                _arm('B', 0.03, 30.0, 4),
                _arm('C', 0.02, 20.0, 4)]
        d = rewards.evaluate_divergence(arms)
        self.assertEqual(d['max_rank_gap'], 1)
        self.assertFalse(d['diverged'])

    def test_two_position_swap_with_enough_leads_diverges(self):
        # Classement coût inversé (C<B<A) ⇒ A et C bougent de 2 positions.
        arms = [_arm('A', 0.04, 50.0, 2),
                _arm('B', 0.03, 25.0, 4),
                _arm('C', 0.02, 16.0, 6)]
        d = rewards.evaluate_divergence(arms)
        self.assertEqual(d['max_rank_gap'], 2)
        self.assertEqual(d['qualified_total'], 12)
        self.assertTrue(d['diverged'])
        self.assertEqual(d['proxy_best'], 'A')
        self.assertEqual(d['crm_best'], 'C')
        self.assertIn('Divergence', d['reason_fr'])
        self.assertIn('A', d['reason_fr'])
        self.assertIn('C', d['reason_fr'])

    def test_two_position_swap_below_lead_threshold_is_silent(self):
        # Même inversion mais < 10 leads qualifiés cumulés ⇒ le proxy règne.
        arms = [_arm('A', 0.04, 50.0, 1),
                _arm('B', 0.03, 25.0, 2),
                _arm('C', 0.02, 16.0, 3)]
        d = rewards.evaluate_divergence(arms)
        self.assertEqual(d['max_rank_gap'], 2)
        self.assertEqual(d['qualified_total'], 6)
        self.assertFalse(d['diverged'])
        self.assertEqual(d['reason_fr'], '')

    def test_none_crm_cost_ranked_last(self):
        # Un bras sans lead qualifié (coût None) est classé dernier côté CRM,
        # jamais « coût zéro ».
        arms = [_arm('A', 0.02, None, 0),
                _arm('B', 0.04, 10.0, 12)]
        d = rewards.evaluate_divergence(arms)
        self.assertEqual(d['crm_ranking'][-1], 'A')

    def test_fewer_than_two_arms_never_diverges(self):
        d = rewards.evaluate_divergence([_arm('A', 0.04, 10.0, 50)])
        self.assertFalse(d['diverged'])
        self.assertEqual(d['max_rank_gap'], 0)

    def test_custom_thresholds(self):
        arms = [_arm('A', 0.04, 50.0, 3),
                _arm('B', 0.03, 25.0, 3),
                _arm('C', 0.02, 16.0, 3)]
        # Baisser le seuil à 9 leads rend la même inversion divergente.
        d = rewards.evaluate_divergence(arms, min_qualified=9)
        self.assertTrue(d['diverged'])


class RunDivergenceCheckTests(TestCase):
    """Chaîne complète (ArmDailyStat proxy + attribution CRM → propose-only)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Rew Co', slug='rew-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp', name='Solaire', status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='ast', name='Toit', campaign=self.camp)
        self.exp = Experiment.objects.create(
            company=self.company, name='Test hook',
            status=Experiment.Statut.EN_COURS)
        self.ct = ContentType.objects.get_for_model(AdMirror)
        self.today = datetime.date.today()

    def _ad(self, meta_id):
        return AdMirror.objects.create(
            company=self.company, meta_id=meta_id, name=meta_id,
            adset=self.adset)

    def _arm(self, ad, label, impressions, conversions):
        arm = ExperimentArm.objects.create(
            company=self.company, experiment=self.exp, label=label,
            ad_id=ad.meta_id)
        ArmDailyStat.upsert(arm=arm, date=self.today,
                            impressions=impressions, conversations=conversions)
        return arm

    def _spend(self, ad, amount):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=ad.pk,
            date=self.today, spend=Decimal(amount), results=1)

    def _qualified_leads(self, ad, count):
        for _ in range(count):
            Lead.objects.create(
                company=self.company, nom='Prospect', stage=CONTACTED,
                meta_ad_id=ad.meta_id, canal=Lead.Canal.META_ADS)

    def _build_divergent(self):
        # Proxy : A > B > C ; coût CRM : C < B < A (inversion de 2 positions).
        ad_a, ad_b, ad_c = self._ad('ad_A'), self._ad('ad_B'), self._ad('ad_C')
        self._arm(ad_a, 'A', 1000, 40)
        self._arm(ad_b, 'B', 1000, 30)
        self._arm(ad_c, 'C', 1000, 20)
        for ad in (ad_a, ad_b, ad_c):
            self._spend(ad, '100.00')
        self._qualified_leads(ad_a, 2)   # coût 50.00
        self._qualified_leads(ad_b, 4)   # coût 25.00
        self._qualified_leads(ad_c, 6)   # coût 16.67  → total 12 qualifiés

    def test_divergence_raises_propose_only_action(self):
        self._build_divergent()
        decision, action = rewards.run_divergence_check(
            self.company, experiment=self.exp, now=self.today)
        self.assertTrue(decision['diverged'])
        self.assertEqual(decision['proxy_best'], 'A')
        self.assertEqual(decision['crm_best'], 'C')
        self.assertIsNotNone(action)
        # Propose-only : jamais auto, statut proposée, raison FR non vide.
        self.assertFalse(action.auto)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertTrue(action.reason_fr.strip())
        self.assertEqual(action.company, self.company)
        self.assertEqual(action.kind, EngineAction.Kind.REBALANCE_BUDGET)
        self.assertEqual(action.payload['proxy_ranking'], ['A', 'B', 'C'])
        self.assertEqual(action.payload['crm_ranking'], ['C', 'B', 'A'])
        # Aucune action AUTO n'a jamais été écrite.
        self.assertFalse(
            EngineAction.objects.filter(company=self.company, auto=True).exists())

    def test_convergence_creates_no_action(self):
        # Proxy A>B>C et coût A<B<C (alignés) ⇒ aucune action.
        ad_a, ad_b, ad_c = self._ad('ad_A'), self._ad('ad_B'), self._ad('ad_C')
        self._arm(ad_a, 'A', 1000, 40)
        self._arm(ad_b, 'B', 1000, 30)
        self._arm(ad_c, 'C', 1000, 20)
        for ad in (ad_a, ad_b, ad_c):
            self._spend(ad, '100.00')
        self._qualified_leads(ad_a, 6)   # coût 16.67 (le moins cher = meilleur)
        self._qualified_leads(ad_b, 4)   # coût 25.00
        self._qualified_leads(ad_c, 2)   # coût 50.00
        decision, action = rewards.run_divergence_check(
            self.company, experiment=self.exp, now=self.today)
        self.assertFalse(decision['diverged'])
        self.assertIsNone(action)
        self.assertEqual(EngineAction.objects.count(), 0)
