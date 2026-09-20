"""PUB135 — Rationale de décision à DEUX fenêtres + signal leads RÉEL.

La première proposition de production jugeait « 0 résultat cette semaine » sur le
seul champ ``results`` de Meta : aveugle aux leads Odoo (la vérité du fondateur)
et sans aucun contexte historique.

Prouve :
  * le comptage par fenêtre d'``odoo_leads`` est PUR et honnête (fenêtre datée,
    vie entière, leads sans date exposés séparément, palier campagne inclus) ;
  * ``decision_evidence`` lit les DEUX fenêtres × les DEUX signaux depuis les
    snapshots et l'attribution Odoo EXISTANTE — et ne fabrique JAMAIS un
    chiffre : Odoo non configuré, aucun snapshot ou scope non résolvable sont
    DITS dans le texte ;
  * les propositions pause / rotation / rééquilibrage portent les deux fenêtres
    ET les deux signaux dans ``reason_fr`` (+ ``payload['evidence']``) ;
  * une DIVERGENCE des deux signaux (0 résultat Meta mais des leads Odoo, ou
    l'inverse) est mentionnée EXPLICITEMENT — la décision est renvoyée à la main.
"""
import datetime
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import odoo_leads, rules_engine
from apps.adsengine.models import (
    AdCampaignMirror, AdCreativeMirror, AdMirror, AdSetMirror, EngineAction,
    InsightSnapshot, MetaConnection, RulePolicy,
)

TODAY = datetime.date(2026, 9, 20)


def _snap(company, obj, *, day, spend, results, frequency=None,
          impressions=None, clicks=None, cpl=None):
    ct = ContentType.objects.get_for_model(type(obj))
    InsightSnapshot.objects.create(
        company=company, content_type=ct, object_id=obj.pk,
        date=TODAY - datetime.timedelta(days=day),
        spend=str(spend), results=results, impressions=impressions,
        clicks=clicks,
        cpl=(str(cpl) if cpl is not None else None),
        frequency=(str(frequency) if frequency is not None else None))


def _index(by_ad=None, by_campaign=None, configured=True, error=None):
    """Index leads (forme exacte de ``odoo_leads.leads_days_index``)."""
    out = {'configured': configured, 'by_ad': by_ad or {},
           'by_campaign': by_campaign or {}}
    if error is not None:
        out['odoo_error'] = error
    return out


def _iso(days_ago):
    return (TODAY - datetime.timedelta(days=days_ago)).isoformat()


class CountLeadsInWindowsTests(SimpleTestCase):
    """Le comptage par fenêtre est PUR : aucune lecture, aucune estimation."""

    def test_counts_recent_window_and_lifetime_separately(self):
        index = _index(by_ad={'ad-1': [_iso(0), _iso(3), _iso(30)]})
        counts = odoo_leads.count_leads_in_windows(
            index, ad_meta_ids=['ad-1'],
            window_start=TODAY - datetime.timedelta(days=6), as_of=TODAY)
        self.assertEqual(counts['recent'], 2)      # J-0 et J-3
        self.assertEqual(counts['lifetime'], 3)    # + J-30
        self.assertEqual(counts['undated'], 0)
        self.assertEqual(counts['first_day'], _iso(30))
        self.assertEqual(counts['last_day'], _iso(0))

    def test_undated_leads_count_in_lifetime_never_in_a_dated_window(self):
        index = _index(by_ad={'ad-1': [_iso(1), None, None]})
        counts = odoo_leads.count_leads_in_windows(
            index, ad_meta_ids=['ad-1'],
            window_start=TODAY - datetime.timedelta(days=6), as_of=TODAY)
        self.assertEqual(counts['recent'], 1)
        self.assertEqual(counts['lifetime'], 3)
        self.assertEqual(counts['undated'], 2)

    def test_campaign_tier_and_several_ads_are_summed(self):
        index = _index(by_ad={'ad-1': [_iso(1)], 'ad-2': [_iso(2)]},
                       by_campaign={'cmp-1': [_iso(3)]})
        counts = odoo_leads.count_leads_in_windows(
            index, ad_meta_ids=['ad-1', 'ad-2'], campaign_meta_ids=['cmp-1'],
            window_start=TODAY - datetime.timedelta(days=6), as_of=TODAY)
        self.assertEqual(counts['recent'], 3)
        self.assertEqual(counts['lifetime'], 3)

    def test_future_dated_lead_is_excluded_by_the_as_of_bound(self):
        index = _index(by_ad={'ad-1': [_iso(-2), _iso(1)]})
        counts = odoo_leads.count_leads_in_windows(
            index, ad_meta_ids=['ad-1'],
            window_start=TODAY - datetime.timedelta(days=6), as_of=TODAY)
        self.assertEqual(counts['recent'], 1)

    def test_unknown_target_counts_zero_without_raising(self):
        counts = odoo_leads.count_leads_in_windows(
            _index(), ad_meta_ids=['ghost'], window_start=TODAY, as_of=TODAY)
        self.assertEqual((counts['recent'], counts['lifetime']), (0, 0))


class DecisionEvidenceTests(TestCase):
    """Les DEUX fenêtres × les DEUX signaux, et ce qui manque est DIT."""

    def setUp(self):
        self.company = Company.objects.create(nom='EV Co', slug='ev-co')
        MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1', currency='USD')
        self.campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp-1', name='Solaire',
            status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-1', name='Casa',
            status='PAUSED', campaign=self.campaign, budget='10000')
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad-1', adset=self.adset, name='A1')

    def _evidence(self, index, **kw):
        with patch.object(odoo_leads, 'leads_days_index', return_value=index):
            return rules_engine.decision_evidence(
                self.company, target_type=kw.pop('target_type', 'adset'),
                target_meta_id=kw.pop('target_meta_id', 'as-1'),
                target_object_id=kw.pop('target_object_id', self.adset.pk),
                now=TODAY, **kw)

    def test_both_windows_come_from_the_snapshots(self):
        _snap(self.company, self.adset, day=0, spend=10, results=1)
        _snap(self.company, self.adset, day=2, spend=10, results=0)
        _snap(self.company, self.adset, day=40, spend=100, results=9)
        ev = self._evidence(_index(by_ad={'ad-1': [_iso(1), _iso(50)]}),
                            window_days=7)
        self.assertEqual(ev['meta']['recent']['results'], 1)
        self.assertEqual(ev['meta']['recent']['spend'], 20.0)
        self.assertEqual(ev['meta']['recent']['days'], 2)
        self.assertEqual(ev['meta']['lifetime']['results'], 10)
        self.assertEqual(ev['meta']['lifetime']['spend'], 120.0)
        self.assertEqual(ev['meta']['lifetime']['first'], _iso(40))
        self.assertEqual(ev['leads'],
                         {'available': True, 'ads': 1, 'recent': 1,
                          'lifetime': 2, 'undated': 0,
                          'first_day': _iso(50), 'last_day': _iso(1)})
        text = rules_engine.evidence_fr(ev, currency='USD')
        self.assertIn('Fenêtre 7 j', text)
        self.assertIn('Vie entière', text)
        self.assertIn('USD', text)
        self.assertIn('1 résultat Meta', text)
        self.assertIn('10 résultats Meta', text)
        self.assertIn('1 lead sur la fenêtre', text)
        self.assertIn('2 leads en vie entière', text)

    def test_zero_meta_results_with_real_odoo_leads_is_a_divergence(self):
        # LE cas de production : Meta dit « 0 résultat », Odoo a bien des leads.
        for day in (0, 1, 2):
            _snap(self.company, self.adset, day=day, spend=14, results=0)
        ev = self._evidence(_index(by_ad={'ad-1': [_iso(0), _iso(1), _iso(2)]}),
                            window_days=7)
        self.assertTrue(ev['divergence'])
        text = rules_engine.evidence_fr(ev, currency='USD')
        self.assertIn('DIVERGENTS', text)
        self.assertIn('0 résultat côté Meta', text)
        self.assertIn('3 leads attribué(s) côté Odoo', text)
        self.assertIn('à confirmer à la main', text)

    def test_meta_results_without_any_odoo_lead_also_diverges(self):
        for day in (0, 1, 2):
            _snap(self.company, self.adset, day=day, spend=14, results=2)
        ev = self._evidence(_index(by_ad={'ad-1': [_iso(60)]}), window_days=7)
        self.assertTrue(ev['divergence'])
        self.assertIn('DIVERGENTS', rules_engine.evidence_fr(ev))

    def test_signals_that_agree_carry_no_divergence_mention(self):
        for day in (0, 1, 2):
            _snap(self.company, self.adset, day=day, spend=14, results=2)
        ev = self._evidence(_index(by_ad={'ad-1': [_iso(0), _iso(2)]}),
                            window_days=7)
        self.assertFalse(ev['divergence'])
        self.assertNotIn('DIVERGENTS', rules_engine.evidence_fr(ev))

    def test_unconfigured_odoo_is_said_never_counted_as_zero(self):
        _snap(self.company, self.adset, day=0, spend=14, results=0)
        ev = self._evidence(_index(configured=False), window_days=7)
        self.assertFalse(ev['leads']['available'])
        self.assertFalse(ev['divergence'])  # aucun signal ⇒ aucune divergence
        text = rules_engine.evidence_fr(ev)
        self.assertIn('connexion Odoo non configurée', text)
        self.assertNotIn('0 lead sur la fenêtre', text)

    def test_odoo_read_error_is_said_never_counted_as_zero(self):
        _snap(self.company, self.adset, day=0, spend=14, results=0)
        ev = self._evidence(_index(by_ad={'ad-1': [_iso(0)]},
                                   error='OdooError: timeout'), window_days=7)
        self.assertFalse(ev['leads']['available'])
        self.assertIn('illisibles', rules_engine.evidence_fr(ev))

    def test_an_odoo_exception_never_breaks_the_decision(self):
        _snap(self.company, self.adset, day=0, spend=14, results=0)
        with patch.object(odoo_leads, 'leads_days_index',
                          side_effect=RuntimeError('boom')):
            ev = rules_engine.decision_evidence(
                self.company, target_type='adset', target_meta_id='as-1',
                target_object_id=self.adset.pk, now=TODAY, window_days=7)
        self.assertFalse(ev['leads']['available'])
        # Un Odoo injoignable est DIT illisible — jamais « non configuré ».
        self.assertIn('illisibles', rules_engine.evidence_fr(ev))
        self.assertIn('RuntimeError: boom', rules_engine.evidence_fr(ev))

    def test_no_snapshot_at_all_is_said_never_a_fabricated_total(self):
        ev = self._evidence(_index(by_ad={'ad-1': [_iso(0)]}), window_days=7)
        text = rules_engine.evidence_fr(ev)
        self.assertIn('aucun snapshot Meta', text)
        self.assertIn('Vie entière : aucun snapshot Meta enregistré.', text)

    def test_campaign_scope_reads_its_ads_and_its_campaign_tier(self):
        _snap(self.company, self.campaign, day=0, spend=30, results=3)
        ev = self._evidence(
            _index(by_ad={'ad-1': [_iso(0)]},
                   by_campaign={'cmp-1': [_iso(1), _iso(2)]}),
            target_type='campaign', target_meta_id='cmp-1',
            target_object_id=self.campaign.pk, window_days=7)
        self.assertEqual(ev['leads']['recent'], 3)

    def test_unresolvable_scope_says_so(self):
        ev = self._evidence(_index(), target_type='account',
                            target_meta_id='act_1', target_object_id=None,
                            window_days=7)
        self.assertIsNone(ev['meta'])
        self.assertFalse(ev['leads']['available'])
        text = rules_engine.evidence_fr(ev)
        self.assertIn('non résolvable', text)
        self.assertIn('Aucun snapshot Meta rattaché', text)

    def test_one_odoo_read_is_shared_by_every_decision_of_a_pass(self):
        _snap(self.company, self.adset, day=0, spend=14, results=1)
        cache = {}
        with patch.object(odoo_leads, 'leads_days_index',
                          return_value=_index()) as read:
            for _ in range(3):
                rules_engine.decision_evidence(
                    self.company, target_type='adset', target_meta_id='as-1',
                    target_object_id=self.adset.pk, now=TODAY,
                    leads_cache=cache)
        self.assertEqual(read.call_count, 1)


class ProposalTextTests(TestCase):
    """Les propositions RÉELLES du moteur portent la rationale complète."""

    def setUp(self):
        self.company = Company.objects.create(nom='PT Co', slug='pt-co')
        MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1', currency='USD',
            page_id='page-1')
        self.campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp-1', name='Solaire',
            status='ACTIVE')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-1', name='Casa', status='ACTIVE',
            campaign=self.campaign, budget='10000')
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad-1', adset=self.adset, name='A1')
        AdCreativeMirror.objects.create(
            company=self.company, ad=self.ad, creative_meta_id='cr-1')

    def _evaluate(self, index):
        with patch.object(odoo_leads, 'leads_days_index', return_value=index):
            rules_engine.evaluate_company(self.company, now=TODAY)
        return EngineAction.objects.filter(company=self.company).first()

    def test_rotation_proposal_shows_two_windows_two_signals(self):
        # Fréquence au-dessus du seuil ⇒ ROTATE_CREATIVE proposée (PUB119).
        for day in (0, 1, 2, 30, 31):
            _snap(self.company, self.adset, day=day, spend=12, results=0,
                  frequency=5.5, impressions=1000)
        RulePolicy.objects.create(
            company=self.company, template_key='frequency_high',
            enabled=True, dry_run=False, mode=RulePolicy.Mode.PROPOSE)

        action = self._evaluate(_index(by_ad={'ad-1': [_iso(0), _iso(1)]}))
        self.assertIsNotNone(action)
        self.assertEqual(action.kind, EngineAction.Kind.ROTATE_CREATIVE)
        self.assertIn('Fenêtre 7 j', action.reason_fr)
        self.assertIn('Vie entière', action.reason_fr)
        self.assertIn('Meta', action.reason_fr)
        self.assertIn('Leads Odoo', action.reason_fr)
        # Divergence : 0 résultat Meta récent, 2 leads Odoo récents.
        self.assertIn('DIVERGENTS', action.reason_fr)
        self.assertTrue(action.payload['evidence']['divergence'])
        self.assertEqual(
            action.payload['evidence']['meta']['recent']['results'], 0)
        self.assertEqual(action.payload['evidence']['leads']['recent'], 2)
        # PUB119 intact : le payload de rotation reste COMPLET.
        self.assertEqual(action.payload['adset_id'], 'as-1')
        self.assertTrue(action.payload['name'])
        self.assertEqual(action.payload['creative'], {'creative_id': 'cr-1'})

    def test_pause_proposal_shows_two_windows_two_signals(self):
        # Stop-loss : CPL campagne au-dessus du plafond dur ⇒ PAUSE proposée.
        for day in range(0, 7):
            _snap(self.company, self.campaign, day=day, spend=500, results=1)
        _snap(self.company, self.campaign, day=45, spend=100, results=5)
        RulePolicy.objects.create(
            company=self.company, template_key='stop_loss_cpl',
            enabled=True, dry_run=False, mode=RulePolicy.Mode.PROPOSE,
            params={'threshold_mad': 100})

        action = self._evaluate(_index(by_ad={'ad-1': [_iso(2)]}))
        self.assertIsNotNone(action)
        self.assertEqual(action.kind, EngineAction.Kind.PAUSE)
        self.assertIn('Fenêtre 7 j', action.reason_fr)
        self.assertIn('Vie entière', action.reason_fr)
        self.assertIn('7 résultats Meta', action.reason_fr)   # fenêtre
        self.assertIn('12 résultats Meta', action.reason_fr)  # vie entière
        self.assertIn('1 lead sur la fenêtre', action.reason_fr)
        self.assertNotIn('DIVERGENTS', action.reason_fr)  # les deux > 0
        self.assertEqual(
            action.payload['evidence']['leads']['lifetime'], 1)
        # Les faits sont aussi au journal de la règle (écran Règles).
        policy = RulePolicy.objects.get(company=self.company,
                                        template_key='stop_loss_cpl')
        journal = [e for e in policy.last_result['findings'] if e.get('fired')]
        self.assertTrue(journal)
        self.assertEqual(journal[0]['evidence']['meta']['recent']['results'], 7)

    def test_budget_rebalance_proposal_shows_two_windows_two_signals(self):
        # Surf-scaling : CPL court < CPL long ⇒ montée de budget proposée.
        for day in (0, 1, 2):
            _snap(self.company, self.adset, day=day, spend=10, results=10)
        for day in (3, 4, 5, 6):
            _snap(self.company, self.adset, day=day, spend=30, results=5)
        RulePolicy.objects.create(
            company=self.company, template_key='surf_scale_budget',
            enabled=True, dry_run=False, mode=RulePolicy.Mode.PROPOSE)

        action = self._evaluate(_index(by_ad={'ad-1': [_iso(1), _iso(4)]}))
        self.assertIsNotNone(action)
        self.assertIn('USD/j', action.reason_fr)          # PUB134 intact
        self.assertIn('Fenêtre 7 j', action.reason_fr)
        self.assertIn('Vie entière', action.reason_fr)
        self.assertIn('2 leads en vie entière', action.reason_fr)
        self.assertEqual(action.payload['evidence']['leads']['recent'], 2)

    def test_simulation_prefix_still_opens_the_reason(self):
        # 6 jours : au-dessus du plancher ``min_samples`` (5) du stop-loss.
        for day in range(0, 6):
            _snap(self.company, self.campaign, day=day, spend=500, results=1)
        RulePolicy.objects.create(
            company=self.company, template_key='stop_loss_cpl',
            enabled=True, dry_run=True, mode=RulePolicy.Mode.PROPOSE,
            params={'threshold_mad': 100})

        action = self._evaluate(_index(configured=False))
        self.assertIsNotNone(action)
        self.assertTrue(action.reason_fr.startswith('[Simulation] '))
        self.assertIn('connexion Odoo non configurée', action.reason_fr)

    def test_alert_only_rule_gets_no_evidence_block(self):
        # ``cpl_band`` n'engage aucune action : rien à justifier, rien d'ajouté.
        for day in range(1, 6):
            _snap(self.company, self.campaign, day=day, spend=10, results=1,
                  cpl=10)
        _snap(self.company, self.campaign, day=0, spend=95, results=1, cpl=95)
        RulePolicy.objects.create(
            company=self.company, template_key='cpl_band',
            enabled=True, dry_run=False, mode=RulePolicy.Mode.PROPOSE)

        with patch.object(odoo_leads, 'leads_days_index') as read:
            rules_engine.evaluate_company(self.company, now=TODAY)
        read.assert_not_called()

    def test_creative_fatigue_rotation_carries_the_rationale(self):
        # Fenêtre courte vs référence précédente : CTR effondré + fréquence.
        for day in range(0, 7):
            _snap(self.company, self.ad, day=day, spend=10, results=0,
                  frequency=5.0, impressions=1000, clicks=1)
        for day in range(7, 21):
            _snap(self.company, self.ad, day=day, spend=10, results=1,
                  impressions=1000, clicks=100)

        with patch.object(odoo_leads, 'leads_days_index',
                          return_value=_index(by_ad={'ad-1': [_iso(1)]})):
            findings = rules_engine.evaluate_creative_fatigue(
                self.company, now=TODAY)
        fired = [f for f in findings if f.get('fired')]
        self.assertTrue(fired, 'la fatigue doit se déclencher sur ces fixtures')
        action = EngineAction.objects.filter(company=self.company).first()
        self.assertIsNotNone(action)
        self.assertIn('Fenêtre 7 j', action.reason_fr)
        self.assertIn('Vie entière', action.reason_fr)
        self.assertIn('Leads Odoo', action.reason_fr)
        self.assertIn('DIVERGENTS', action.reason_fr)  # 0 Meta, 1 lead Odoo
        self.assertEqual(action.payload['evidence']['leads']['recent'], 1)
