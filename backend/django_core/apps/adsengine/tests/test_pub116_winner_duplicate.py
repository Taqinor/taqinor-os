"""PUB116 — Le moteur PROPOSE lui-même « multiplier le gagnant ».

Avant : aucun gabarit du catalogue ne routait vers l'intention ``duplicate`` de
``rules_engine._propose_v2_action`` — la seule multiplication d'un gagnant était
le duplicate MANUEL en 3 clics. Ces tests prouvent :

  * un gagnant NET sur fixtures produit DEUX propositions dans les approbations —
    duplication (``winner_duplicate``) + montée de budget (``surf_scale_budget``),
    toutes deux préfixées « [Simulation] » en dry-run (défaut du seed) ;
  * le PLANCHER DE VOLUME est honnête : même CPL en amélioration, mais trop peu
    de résultats ⇒ AUCUNE proposition ;
  * rien ne s'auto-applique (statut PROPOSÉE, ``auto`` faux) et un second passage
    dans la fenêtre de cooldown ne duplique pas la proposition ;
  * INVARIANT règle #3 sur le chemin duplicate : le payload ne porte AUCUN
    ``status``, et l'exécution réelle (transport mocké) crée l'ad set ET l'ad en
    ``PAUSED``.
"""
import datetime
import json
from urllib.parse import parse_qs

import httpx
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.adsengine import meta_client as mc
from apps.adsengine import rule_templates, rules_engine
from apps.adsengine.models import (
    AdCampaignMirror, AdCreativeMirror, AdMirror, AdSetMirror, EngineAction,
    InsightSnapshot, RulePolicy,
)
from apps.adsengine.pacing import KIND_INCREASE_PACE
from apps.adsengine.services import KIND_DUPLICATE

TODAY = datetime.date(2026, 9, 20)
TOKEN = 'tok-41827'


def _snap(company, obj, *, day, spend, results):
    ct = ContentType.objects.get_for_model(type(obj))
    InsightSnapshot.objects.create(
        company=company, content_type=ct, object_id=obj.pk,
        date=TODAY - datetime.timedelta(days=day),
        spend=str(spend), results=results)


class WinnerDuplicateTemplateTests(TestCase):
    """Le catalogue déclare bien les DEUX intentions d'action v2."""

    def test_surf_scaling_template_declares_budget_scale_up(self):
        tpl = rule_templates.get_template('surf_scale_budget')
        self.assertEqual(tpl['v2']['action'], 'budget_scale_up')

    def test_winner_duplicate_template_declares_duplicate(self):
        tpl = rule_templates.get_template('winner_duplicate')
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl['v2']['action'], 'duplicate')
        # Alerte-seule côté kind : l'action passe UNIQUEMENT par le hint v2
        # (aucun chemin kind-based « duplicate », donc aucune auto-application).
        self.assertIsNone(tpl['action'])
        self.assertFalse(rule_templates.is_actionable('winner_duplicate'))
        # Plancher de volume déclaré et modifiable par le fondateur.
        self.assertIn('min_results', tpl['editable_params'])
        self.assertGreaterEqual(tpl['default_params']['min_results'], 1)

    def test_seeded_policies_are_dry_run_and_disabled(self):
        company = Company.objects.create(nom='WD Seed', slug='wd-seed')
        rule_templates.seed_default_policies(company)
        policy = RulePolicy.objects.get(
            company=company, template_key='winner_duplicate')
        self.assertFalse(policy.enabled)
        self.assertTrue(policy.dry_run)
        self.assertEqual(policy.mode, RulePolicy.Mode.PROPOSE)


class WinnerOnFixturesTests(TestCase):
    """Fixtures : un ad set gagnant NET (CPL en baisse + volume réel)."""

    def setUp(self):
        self.company = Company.objects.create(nom='WD Co', slug='wd-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='CAMP', status='ACTIVE')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as1', name='WINNER',
            status='ACTIVE', campaign=self.camp, budget='10000')
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad1', name='AD-A', status='ACTIVE',
            adset=self.adset)
        AdCreativeMirror.objects.create(
            company=self.company, ad=self.ad, creative_meta_id='cr1')

    def _winner_fixtures(self):
        # CPL court (3 j) = 1,0 ; CPL long (7 j) = 100/50 = 2,0 ⇒ amélioration.
        # Résultats cumulés sur 7 j = 50 ⇒ très au-dessus du plancher (5).
        for d in (0, 1, 2):
            _snap(self.company, self.adset, day=d, spend=10, results=10)
        for d in (3, 4, 5, 6):
            _snap(self.company, self.adset, day=d, spend=17.5, results=5)

    def _thin_fixtures(self):
        # CPL court = 3/3 = 1,0 ; CPL long = 15/3 = 5,0 ⇒ l'amélioration est
        # RÉELLE, mais 3 résultats cumulés seulement : sous le plancher (5).
        for d in (0, 1, 2):
            _snap(self.company, self.adset, day=d, spend=1, results=1)
        for d in (3, 4, 5, 6):
            _snap(self.company, self.adset, day=d, spend=3, results=0)

    def _policy(self, template_key, **kwargs):
        defaults = {'enabled': True, 'dry_run': True,
                    'mode': RulePolicy.Mode.PROPOSE}
        defaults.update(kwargs)
        return RulePolicy.objects.create(
            company=self.company, template_key=template_key, **defaults)

    def test_net_winner_proposes_duplicate_and_budget_up_in_simulation(self):
        self._winner_fixtures()
        self._policy('winner_duplicate')
        self._policy('surf_scale_budget')
        rules_engine.evaluate_company(self.company, now=TODAY)

        actions = EngineAction.objects.filter(company=self.company)
        kinds = sorted(a.kind for a in actions)
        self.assertEqual(kinds, sorted([KIND_DUPLICATE, KIND_INCREASE_PACE]))
        for act in actions:
            # Propose-only : jamais appliquée, jamais une activation.
            self.assertEqual(act.status, EngineAction.Statut.PROPOSEE)
            self.assertFalse(act.auto)
            # Dry-run (défaut du seed) ⇒ raison préfixée « [Simulation] ».
            self.assertTrue(act.reason_fr.startswith('[Simulation] '),
                            act.reason_fr)

        dup = actions.get(kind=KIND_DUPLICATE)
        self.assertEqual(dup.payload.get('source_adset_id'), 'as1')
        self.assertEqual(dup.payload.get('creative_id'), 'cr1')
        # INVARIANT règle #3 : rien dans le payload ne porte un statut.
        self.assertNotIn('status', dup.payload)
        self.assertNotIn(
            'status', dup.payload.get('adset_extra_fields') or {})

    def test_volume_floor_blocks_a_lucky_thin_adset(self):
        self._thin_fixtures()
        self._policy('winner_duplicate')
        rules_engine.evaluate_company(self.company, now=TODAY)
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)

    def test_lowered_floor_lets_the_same_thin_adset_through(self):
        # Preuve que c'est BIEN le plancher qui a bloqué (et non les données).
        self._thin_fixtures()
        self._policy('winner_duplicate', params={'min_results': 1})
        rules_engine.evaluate_company(self.company, now=TODAY)
        self.assertEqual(
            EngineAction.objects.filter(
                company=self.company, kind=KIND_DUPLICATE).count(), 1)

    def test_second_pass_in_cooldown_does_not_duplicate_the_proposal(self):
        self._winner_fixtures()
        self._policy('winner_duplicate')
        rules_engine.evaluate_company(self.company, now=TODAY)
        rules_engine.evaluate_company(self.company, now=TODAY)
        self.assertEqual(
            EngineAction.objects.filter(
                company=self.company, kind=KIND_DUPLICATE).count(), 1)

    def test_no_live_creative_means_alert_only_never_an_empty_action(self):
        self._winner_fixtures()
        AdCreativeMirror.objects.filter(company=self.company).delete()
        self._policy('winner_duplicate')
        rules_engine.evaluate_company(self.company, now=TODAY)
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)


class DuplicatePathIsBornPausedTests(TestCase):
    """Le chemin d'application de la duplication naît PAUSED (règle #3)."""

    def test_duplicate_adset_with_ad_forces_paused_on_both_creations(self):
        bodies = []

        def handler(request):
            bodies.append(parse_qs(request.content.decode('utf-8')))
            return httpx.Response(200, json={'id': f'obj-{len(bodies)}'})

        client = mc.MetaClient(
            access_token=TOKEN, ad_account_id='act_1',
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            max_retries=0, backoff_base=0)
        client.duplicate_adset_with_ad(
            campaign_id='c1', new_adset_name='WINNER (copie)',
            new_ad_name='AD-A (copie)', creative_id='cr1',
            adset_extra_fields={'daily_budget': 10000},
            ad_extra_fields={'status': 'ACTIVE'})  # tentative d'activation

        self.assertEqual(len(bodies), 2)
        for form in bodies:
            self.assertEqual(form['status'], ['PAUSED'])
        # L'ad réutilise bien le créatif LIVE de la source.
        self.assertEqual(
            json.loads(bodies[1]['creative'][0]), {'creative_id': 'cr1'})
