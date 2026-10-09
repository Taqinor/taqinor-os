"""AACQ9 — Le « coût par lead » des règles ne se calcule que sur des LEADS.

Campagne trafic : « objectif trafic : pas de coût par lead » (plus jamais un
coût par clic comparé à un plafond de CPL) ; campagne leads : dépense ÷
``leads_count`` (source « leads Meta »).
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.adsengine import rule_templates, rules_engine
from apps.adsengine.models import (
    AdCampaignMirror, EngineAction, InsightSnapshot, RulePolicy,
)

TODAY = datetime.date(2026, 7, 16)


class CplObjectifTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Obj', slug='aacq9-obj')
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        self.trafic = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c-trafic', name='Warm up',
            status='ACTIVE', objective='OUTCOME_TRAFFIC')
        self.leads = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c-leads', name='Lead form',
            status='ACTIVE', objective='OUTCOME_LEADS')
        for d in range(7):
            date = TODAY - datetime.timedelta(days=d)
            InsightSnapshot.objects.create(
                company=self.company, content_type=ct, object_id=self.trafic.pk,
                date=date, spend='400', results=40, link_clicks=40,
                leads_count=0)
            InsightSnapshot.objects.create(
                company=self.company, content_type=ct, object_id=self.leads.pk,
                date=date, spend='600', results=40, link_clicks=40,
                leads_count=2)

    def _snaps(self, camp):
        return list(InsightSnapshot.objects.filter(
            company=self.company, object_id=camp.pk))

    def _stop_loss(self):
        return RulePolicy.objects.create(
            company=self.company, template_key='stop_loss_cpl', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE)

    def test_trafic_non_applicable(self):
        lead_field, raison = rules_engine._cpl_basis(self.trafic)
        self.assertIsNone(lead_field)
        self.assertEqual(raison, 'objectif trafic : pas de coût par lead')
        policy = self._stop_loss()
        findings = rules_engine._eval_stop_loss(
            self.company, policy, rule_templates.get_template('stop_loss_cpl'),
            now=TODAY, config=None)
        trafic = [f for f in findings if f['target_meta_id'] == 'c-trafic'][0]
        self.assertFalse(trafic['fired'])
        self.assertTrue(trafic['insufficient_data'])
        self.assertEqual(trafic['blocked_fr'],
                         'objectif trafic : pas de coût par lead')
        self.assertNotIn('value', trafic['computed'])

    def test_leads_divise_par_leads_count(self):
        lead_field, raison = rules_engine._cpl_basis(self.leads)
        self.assertEqual(lead_field, 'leads_count')
        self.assertIsNone(raison)
        value, n = rules_engine._derived_metric(
            self._snaps(self.leads), 'cpl', lead_field=lead_field)
        self.assertEqual(n, 7)
        self.assertAlmostEqual(value, 300.0)  # 4200 / 14 leads (pas 40 clics)
        policy = self._stop_loss()
        rules_engine.evaluate_company(self.company, now=TODAY)
        policy.refresh_from_db()
        by_target = {f['target']: f for f in policy.last_result['findings']}
        leads = by_target['c-leads']
        self.assertTrue(leads['fired'])
        self.assertEqual(leads['computed']['value'], 300.0)
        self.assertEqual(leads['computed']['source'], 'leads Meta')

    def test_stop_loss_trafic_ne_compare_pas_un_cpc(self):
        policy = self._stop_loss()
        rules_engine.evaluate_company(self.company, now=TODAY)
        policy.refresh_from_db()
        by_target = {f['target']: f for f in policy.last_result['findings']}
        trafic = by_target['c-trafic']
        self.assertFalse(trafic['fired'])
        self.assertEqual(trafic['blocked_fr'],
                         'objectif trafic : pas de coût par lead')
        # Seule la campagne leads (CPL 300 > 250) est mise en pause proposée.
        pauses = EngineAction.objects.filter(
            company=self.company, kind=EngineAction.Kind.PAUSE)
        self.assertEqual(
            [a.payload.get('target_meta_id') for a in pauses], ['c-leads'])
