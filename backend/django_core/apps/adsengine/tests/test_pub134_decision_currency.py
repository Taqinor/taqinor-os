"""PUB134 — La devise RÉELLE du compte dans les textes de décision.

Meta rapporte TOUS les montants dans la devise DU COMPTE. Les textes composés
par le moteur écrivaient « MAD » en dur : sur un compte facturé en USD, la
première proposition de production affichait « a dépensé 17.60 MAD » — chiffre
juste, unité fausse.

Prouve :
  * les détecteurs PURS d'``anomaly.py`` portent la devise reçue et n'écrivent
    AUCUNE unité quand elle est inconnue (jamais une devise devinée) ;
  * ``rules_engine.account_currency`` lit la ``MetaConnection`` (repli MAD,
    convention société, quand il n'y a ni connexion ni devise synchronisée) ;
  * sur un compte USD, la proposition de montée de budget, l'anomalie de bande
    CPL et l'alerte « dépense sans résultat » disent toutes « USD » — et plus
    jamais « MAD ».
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.adsengine import anomaly, guardrails, rules_engine
from apps.adsengine.models import (
    AdCampaignMirror, AdSetMirror, AnomalyEvent, EngineAction, EngineAlert,
    InsightSnapshot, MetaConnection, RulePolicy,
)

TODAY = datetime.date(2026, 9, 20)


def _snap(company, obj, *, day, spend, results, impressions=None, cpl=None):
    ct = ContentType.objects.get_for_model(type(obj))
    InsightSnapshot.objects.create(
        company=company, content_type=ct, object_id=obj.pk,
        date=TODAY - datetime.timedelta(days=day),
        spend=str(spend), results=results, impressions=impressions,
        cpl=(str(cpl) if cpl is not None else None))


class PureDetectorCurrencyTests(SimpleTestCase):
    def test_cpl_band_message_uses_the_given_currency(self):
        det = anomaly.detect_cpl_band(
            [10, 10, 10, 10, 10], 95, 20, currency='USD')
        self.assertTrue(det.fired)
        self.assertIn('USD', det.message_fr)
        self.assertNotIn('MAD', det.message_fr)
        self.assertEqual(det.computed['currency'], 'USD')

    def test_unknown_currency_writes_no_unit_at_all(self):
        det = anomaly.detect_cpl_band([10, 10, 10, 10, 10], 95, 20)
        self.assertTrue(det.fired)
        self.assertNotIn('MAD', det.message_fr)
        self.assertNotIn('USD', det.message_fr)
        self.assertIn('95', det.message_fr)  # le CHIFFRE reste, lui

    def test_spend_anomaly_and_zero_delivery_carry_the_currency(self):
        spike = anomaly.detect_spend_anomaly(
            [10, 10, 10], 500, currency='USD')
        self.assertTrue(spike.fired)
        self.assertIn('USD', spike.message_fr)
        self.assertNotIn('MAD', spike.message_fr)

        zero = anomaly.detect_zero_delivery(
            spend=17.60, impressions=0, clicks=0, leads=0,
            hours_since_launch=48, currency='USD')
        self.assertTrue(zero.fired)
        self.assertIn('17.6 USD', zero.message_fr)
        self.assertNotIn('MAD', zero.message_fr)


class AccountCurrencyResolutionTests(TestCase):
    def test_no_connection_falls_back_to_company_currency(self):
        company = Company.objects.create(nom='NC Co', slug='nc-co')
        self.assertEqual(rules_engine.account_currency(company), 'MAD')

    def test_connection_without_synced_currency_falls_back(self):
        company = Company.objects.create(nom='EC Co', slug='ec-co')
        MetaConnection.objects.create(
            company=company, ad_account_id='act_1', currency='')
        self.assertEqual(rules_engine.account_currency(company), 'MAD')

    def test_usd_account_resolves_to_usd(self):
        company = Company.objects.create(nom='UC Co', slug='uc-co')
        MetaConnection.objects.create(
            company=company, ad_account_id='act_1', currency='USD')
        self.assertEqual(rules_engine.account_currency(company), 'USD')


class UsdAccountDecisionTextTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='UA Co', slug='ua-co')
        MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1', currency='USD')

    def test_budget_scale_up_proposal_names_usd(self):
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as1', name='WINNER',
            status='ACTIVE', budget='10000')
        # CPL court (3 j) nettement sous le CPL long (7 j) ⇒ surf-scaling.
        for d in (0, 1, 2):
            _snap(self.company, adset, day=d, spend=10, results=10)
        for d in (3, 4, 5, 6):
            _snap(self.company, adset, day=d, spend=30, results=5)
        RulePolicy.objects.create(
            company=self.company, template_key='surf_scale_budget',
            enabled=True, dry_run=False, mode=RulePolicy.Mode.PROPOSE)

        rules_engine.evaluate_company(self.company, now=TODAY)
        act = EngineAction.objects.filter(company=self.company).first()
        self.assertIsNotNone(act)
        self.assertIn('USD', act.reason_fr)
        self.assertNotIn('MAD', act.reason_fr)

    def test_cpl_band_anomaly_message_names_usd(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='CAMP', status='ACTIVE')
        # Médiane trainante à 10 ; le CPL du jour explose à 95 (hors bande 2×).
        for d in range(1, 6):
            _snap(self.company, camp, day=d, spend=10, results=1, cpl=10)
        _snap(self.company, camp, day=0, spend=95, results=1, cpl=95)
        RulePolicy.objects.create(
            company=self.company, template_key='cpl_band',
            enabled=True, dry_run=True, mode=RulePolicy.Mode.PROPOSE)

        rules_engine.evaluate_company(self.company, now=TODAY)
        event = AnomalyEvent.objects.filter(company=self.company).first()
        self.assertIsNotNone(event)
        self.assertIn('USD', event.message_fr)
        self.assertNotIn('MAD', event.message_fr)

    def test_zero_result_sweep_alert_names_usd(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c9', name='ZERO', status='ACTIVE')
        _snap(self.company, camp, day=0, spend='17.60', results=0,
              impressions=0)
        guardrails.detect_anomalies(self.company, now=TODAY)
        alert = EngineAlert.objects.filter(
            company=self.company,
            alert_type=guardrails.ALERT_ANOMALY).first()
        self.assertIsNotNone(alert)
        self.assertIn('17.60 USD', alert.message)
        self.assertNotIn('MAD', alert.message)
        self.assertEqual(alert.detail.get('currency'), 'USD')
