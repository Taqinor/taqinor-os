"""ADSDEEP40 — Tests des ACTIONS de règle v2 (propose-first, learning-safe).

Prouve, dry-run, que chaque action de règle v2 génère une ``EngineAction``
PROPOSÉE (jamais appliquée, jamais une activation) :

  * surf-scaling ⇒ montée de budget PLAFONNÉE learning-safe (≤ 20 %, en pratique
    ≤ 15 %) — même quand le fondateur pousse ``scale_pct`` à 50 % ;
  * stop-loss ⇒ PAUSE proposée (CPL campagne > plafond dur) ;
  * duplication ⇒ action ``duplicate`` proposée ;
  * mode AUTO ⇒ l'action de budget reste PROPOSÉE (propose-first inconditionnel).
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.adsengine import rules_engine
from apps.adsengine.models import (
    AdCampaignMirror, AdCreativeMirror, AdMirror, AdSetMirror, EngineAction,
    InsightSnapshot, RulePolicy,
)
from apps.adsengine.pacing import KIND_INCREASE_PACE
from apps.adsengine.services import KIND_DUPLICATE, LEARNING_SAFE_MAX_PCT

TODAY = datetime.date(2026, 7, 16)


def _snap(company, obj, *, day, spend, results):
    ct = ContentType.objects.get_for_model(type(obj))
    InsightSnapshot.objects.create(
        company=company, content_type=ct, object_id=obj.pk,
        date=TODAY - datetime.timedelta(days=day),
        spend=str(spend), results=results)


class SurfScaleBudgetActionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='SS Co', slug='ss-co')
        # Budget miroir en CENTIMES (unités mineures Meta) = 100 MAD.
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as1', name='PROSPECT', status='ACTIVE',
            budget='10000')
        # CPL récent (3 j) NETTEMENT sous le CPL long (7 j) ⇒ amélioration.
        for d in (0, 1, 2):
            _snap(self.company, self.adset, day=d, spend=10, results=10)
        for d in (3, 4, 5, 6):
            _snap(self.company, self.adset, day=d, spend=30, results=5)

    def _rule(self, **params):
        return RulePolicy.objects.create(
            company=self.company, template_key='surf_scale_budget',
            enabled=True, dry_run=False, mode=RulePolicy.Mode.PROPOSE,
            params=params)

    def test_surf_scale_proposes_budget_increase_capped_20pct(self):
        self._rule()  # scale_pct par défaut = 20
        rules_engine.evaluate_company(self.company, now=TODAY)
        actions = EngineAction.objects.filter(company=self.company)
        self.assertEqual(actions.count(), 1)
        act = actions.first()
        # Propose-first : jamais appliquée, jamais une pause/activation.
        self.assertEqual(act.status, EngineAction.Statut.PROPOSEE)
        self.assertEqual(act.kind, KIND_INCREASE_PACE)
        # Budget cap ≤ 20 % (learning-safe) : le nouveau budget ne dépasse jamais
        # +20 % du courant (100 MAD → ≤ 120 MAD ; en pratique 115).
        new_mad = act.payload['new_daily_budget_mad']
        self.assertGreater(new_mad, 100.0)         # c'est bien une MONTÉE
        self.assertLessEqual(new_mad, 100.0 * (1 + LEARNING_SAFE_MAX_PCT / 100))

    def test_scale_pct_50_is_clamped_learning_safe(self):
        # Le fondateur pousse scale_pct à 50 % : le pas reste borné ≤ 20 %.
        self._rule(scale_pct=50)
        rules_engine.evaluate_company(self.company, now=TODAY)
        act = EngineAction.objects.filter(company=self.company).first()
        self.assertIsNotNone(act)
        self.assertLessEqual(
            act.payload['new_daily_budget_mad'],
            100.0 * (1 + LEARNING_SAFE_MAX_PCT / 100))

    def test_auto_mode_still_proposes_never_applies(self):
        # mode=AUTO + hors simulation : l'action budget v2 reste PROPOSÉE.
        RulePolicy.objects.create(
            company=self.company, template_key='surf_scale_budget',
            enabled=True, dry_run=False, mode=RulePolicy.Mode.AUTO)
        rules_engine.evaluate_company(self.company, now=TODAY)
        act = EngineAction.objects.filter(company=self.company).first()
        self.assertIsNotNone(act)
        self.assertEqual(act.status, EngineAction.Statut.PROPOSEE)
        self.assertFalse(act.auto)


class StopLossActionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='SL Co', slug='sl-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='CAMP', status='ACTIVE')
        # CPL = 1500 / 5 = 300 MAD > plafond dur 250 sur 5 jours (min_samples=5).
        for d in range(5):
            _snap(self.company, self.camp, day=d, spend=300, results=1)

    def test_stop_loss_proposes_pause(self):
        RulePolicy.objects.create(
            company=self.company, template_key='stop_loss_cpl',
            enabled=True, dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        rules_engine.evaluate_company(self.company, now=TODAY)
        actions = EngineAction.objects.filter(company=self.company)
        self.assertEqual(actions.count(), 1)
        act = actions.first()
        self.assertEqual(act.status, EngineAction.Statut.PROPOSEE)
        self.assertEqual(act.kind, EngineAction.Kind.PAUSE)
        self.assertEqual(act.payload.get('target_meta_id'), 'c1')
        self.assertEqual(act.payload.get('target_type'), 'campaign')


class DuplicateActionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='DP Co', slug='dp-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='CAMP', status='ACTIVE')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as1', name='WINNER', status='ACTIVE',
            campaign=self.camp, budget='10000')
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad1', name='AD-A', status='ACTIVE',
            adset=self.adset)
        AdCreativeMirror.objects.create(
            company=self.company, ad=self.ad, creative_meta_id='cr1')

    def test_duplicate_intent_proposes_duplicate_action(self):
        policy = RulePolicy(
            company=self.company, template_key='surf_scale_budget',
            enabled=True, dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        template = {'v2': {'action': 'duplicate'}, 'severity': 'info'}
        finding = {'target_meta_id': 'as1', 'target_type': 'adset',
                   'computed': {}}
        act = rules_engine._propose_v2_action(
            self.company, policy, template, finding, config=None, dry_run=False)
        self.assertIsNotNone(act)
        self.assertEqual(act.kind, KIND_DUPLICATE)
        self.assertEqual(act.status, EngineAction.Statut.PROPOSEE)
        self.assertEqual(act.payload.get('source_adset_id'), 'as1')
