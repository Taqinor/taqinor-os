"""AACQ2 — Porte unique de devise : un seuil/plafond ``*_mad`` n'est comparé
qu'à un compte MAD.

Compte Meta en USD : stop-loss et coût par conversation rendent « non
applicable » (``insufficient_data`` + raison FR, aucune comparaison, aucune
action) ; le plafond quotidien et le budget_applier refusent fail-closed
(``GuardrailInoperative``). Contre-épreuve MAD : comportement inchangé
(251 → déclenché, 249 → non). Aucun taux de change inventé, aucun appel Meta.
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.adsengine import budget_applier, guardrails, rule_templates, rules_engine
from apps.adsengine.models import (
    AdCampaignMirror, AdSetMirror, EngineAction, GuardrailConfig,
    InsightSnapshot, MetaConnection, RulePolicy,
)

TODAY = datetime.date(2026, 7, 16)
RAISON = ("Seuil en MAD, compte facturé en USD : seuil non applicable tant "
          "que la devise n'est pas décidée (aucun taux inventé).")


def _snap(company, obj, *, day, spend, results):
    ct = ContentType.objects.get_for_model(type(obj))
    InsightSnapshot.objects.create(
        company=company, content_type=ct, object_id=obj.pk,
        date=TODAY - datetime.timedelta(days=day),
        spend=str(spend), results=results)


class PorteDeviseTests(TestCase):
    def _societe(self, slug, currency):
        company = Company.objects.create(nom=slug, slug=slug)
        MetaConnection.objects.create(
            company=company, ad_account_id='act_' + slug, currency=currency,
            enabled=True, credentials={'access_token': 'tok'})
        return company

    def _campagne_cpl(self, company, cpl):
        camp = AdCampaignMirror.objects.create(
            company=company, meta_id='c-' + company.slug, name='CAMP',
            status='ACTIVE')
        for d in range(5):
            _snap(company, camp, day=d, spend=cpl, results=1)
        return camp

    def _stop_loss(self, company):
        return RulePolicy.objects.create(
            company=company, template_key='stop_loss_cpl', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE)

    def test_stop_loss_usd_non_applicable(self):
        company = self._societe('aacq2-usd-sl', 'USD')
        self._campagne_cpl(company, 251)
        policy = self._stop_loss(company)
        rules_engine.evaluate_company(company, now=TODAY)
        self.assertFalse(EngineAction.objects.filter(company=company).exists())
        policy.refresh_from_db()
        finding = policy.last_result['findings'][0]
        self.assertFalse(finding['fired'])
        self.assertTrue(finding['insufficient_data'])
        self.assertEqual(finding['blocked_fr'], RAISON)
        # Appel direct : aucune comparaison, aucune valeur calculée.
        template = rule_templates.get_template('stop_loss_cpl')
        direct = rules_engine._eval_stop_loss(
            company, policy, template, now=TODAY, config=None)
        self.assertEqual(len(direct), 1)
        self.assertFalse(direct[0]['fired'])
        self.assertEqual(direct[0]['blocked_fr'], RAISON)
        self.assertNotIn('threshold', direct[0]['computed'])
        # La raison revient au passage suivant.
        rules_engine.evaluate_company(company, now=TODAY)
        policy.refresh_from_db()
        self.assertEqual(policy.last_result['findings'][0]['blocked_fr'],
                         RAISON)

    def test_cout_conversation_usd_non_applicable(self):
        company = self._societe('aacq2-usd-cpc', 'USD')
        self._campagne_cpl(company, 251)
        policy = RulePolicy.objects.create(
            company=company, template_key='cost_per_conversation_high',
            enabled=True, dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        template = rule_templates.get_template('cost_per_conversation_high')
        findings = rules_engine._eval_metric_threshold(
            company, policy, template, now=TODAY, config=None)
        self.assertTrue(findings)
        for f in findings:
            self.assertFalse(f['fired'])
            self.assertTrue(f['insufficient_data'])
            self.assertEqual(f['blocked_fr'], RAISON)

    def test_plafond_quotidien_usd_fail_closed(self):
        company = self._societe('aacq2-usd-gf', 'USD')
        config = GuardrailConfig.objects.create(
            company=company, daily_budget_ceiling_mad=100)
        with self.assertRaises(guardrails.GuardrailInoperative) as ctx:
            guardrails.check_daily_ceiling(config, 40, company=company)
        self.assertEqual(str(ctx.exception), RAISON)
        # Sans ``company`` explicite : la société de la config fait foi.
        with self.assertRaises(guardrails.GuardrailInoperative):
            guardrails.check_daily_ceiling(config, 40)

    def test_budget_applier_usd_refuse(self):
        company = self._societe('aacq2-usd-ba', 'USD')
        AdSetMirror.objects.create(
            company=company, meta_id='as-usd', name='AS', status='ACTIVE',
            budget='10000')
        GuardrailConfig.objects.create(
            company=company, daily_budget_ceiling_mad=100)
        with self.assertRaises(guardrails.GuardrailInoperative):
            budget_applier.propose_rebalance_adset_budget(
                company, adset_meta_id='as-usd', current_daily_budget_mad=40,
                target_daily_budget_mad=45, reason_fr='Rééquilibrer.')
        self.assertFalse(EngineAction.objects.filter(company=company).exists())

    def test_compte_mad_inchange(self):
        for cpl, attendu in ((251, True), (249, False)):
            with self.subTest(cpl=cpl):
                company = self._societe(f'aacq2-mad-{cpl}', 'MAD')
                self._campagne_cpl(company, cpl)
                policy = self._stop_loss(company)
                template = rule_templates.get_template('stop_loss_cpl')
                direct = rules_engine._eval_stop_loss(
                    company, policy, template, now=TODAY, config=None)
                self.assertEqual(direct[0]['fired'], attendu)
                self.assertNotIn('blocked_fr', direct[0])
        config = GuardrailConfig(daily_budget_ceiling_mad=100)
        self.assertTrue(guardrails.check_daily_ceiling(config, 90))
