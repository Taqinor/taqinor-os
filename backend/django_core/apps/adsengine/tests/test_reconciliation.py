"""ADSENG31 — Tests de la réconciliation Meta-vs-ERP (déterministes sur fixtures).

Prouve : les DEUX dénominateurs (formulaire + site = Meta-attribuable ; saisi-main
= réalité métier à part), la dédup QW10 (téléphone/email normalisés), la règle de
tolérance combinée, la détection d'une divergence SYNTHÉTIQUE + l'alerte 🟠, le
contrat JSON stable, l'upsert idempotent + non-ré-alerte, et le scoping société.
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Lead

from apps.adsengine import reconciliation
from apps.adsengine.models import (
    AdCampaignMirror, EngineAlert, InsightSnapshot, ReconciliationSnapshot,
)

DAY = datetime.date(2026, 7, 16)


class ReconciliationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Recon Co', slug='recon-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Solaire Casa',
            status='PAUSED')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _meta(self, results, spend='0', day=DAY):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=self.camp.pk,
            date=day, results=results, spend=spend)

    def _lead(self, *, company=None, day=DAY, **kwargs):
        company = company or self.company
        lead = Lead.objects.create(company=company, nom='Prospect', **kwargs)
        # date_creation est auto_now_add → forcer un jour déterministe.
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=timezone.make_aware(
                datetime.datetime.combine(day, datetime.time(12, 0))))
        return lead

    def _form_lead(self, **kw):
        return self._lead(
            source=Lead.Source.META_LEAD_ADS, canal=Lead.Canal.META_ADS,
            meta_campaign_id='c1', **kw)

    def _site_lead(self, **kw):
        return self._lead(
            source=Lead.Source.SITE_WEB, canal=Lead.Canal.META_ADS,
            utm_campaign='Solaire Casa', utm_source='facebook', **kw)

    def _manual_lead(self, **kw):
        return self._lead(
            source=Lead.Source.OS_NATIVE, canal=Lead.Canal.TELEPHONE, **kw)

    # ── règle de tolérance ───────────────────────────────────────────────────
    def test_tolerance_rule_needs_both_abs_and_ratio(self):
        # 1 lead d'écart < plancher absolu → jamais divergent, même à 100 %.
        self.assertFalse(reconciliation.is_divergent(1, 0))
        # 10 vs 5 : écart 5 ≥ 2 ET 50 % ≥ 20 % → divergent.
        self.assertTrue(reconciliation.is_divergent(10, 5))
        # 100 vs 98 : écart 2 mais 2 % < 20 % → non divergent (bruit).
        self.assertFalse(reconciliation.is_divergent(100, 98))
        # deux nuls → jamais divergent.
        self.assertFalse(reconciliation.is_divergent(0, 0))

    # ── deux dénominateurs, jamais fusionnés ────────────────────────────────
    def test_two_denominators_never_merged(self):
        self._meta(3, spend='300.00')
        self._form_lead()
        self._form_lead()
        self._site_lead()
        # saisi-main : réalité métier, JAMAIS dans le chiffre côté Meta.
        self._manual_lead()
        self._manual_lead()

        contract = reconciliation.reconcile(self.company, date=DAY)
        entry = contract['campaigns'][0]
        self.assertEqual(entry['denominators']['form_leads'], 2)
        self.assertEqual(entry['denominators']['site_leads'], 1)
        # erp_leads = form + site (Meta-attribuables), PAS les saisis-main.
        self.assertEqual(entry['erp_leads'], 3)
        self.assertEqual(entry['meta_leads'], 3)
        self.assertFalse(entry['divergent'])
        self.assertEqual(entry['status'], 'ok')
        # les saisis-main sont montrés à part.
        self.assertEqual(contract['hand_entered']['count'], 2)

    def test_ctwa_shown_separately_not_compared(self):
        self._meta(0)
        self._lead(source=Lead.Source.OS_NATIVE,
                   canal=Lead.Canal.WHATSAPP_CTWA,
                   meta_campaign_id='c1')
        contract = reconciliation.reconcile(self.company, date=DAY)
        entry = contract['campaigns'][0]
        self.assertEqual(entry['denominators']['ctwa_self_reported'], 1)
        # CTWA auto-déclaré : jamais compté dans erp_leads (côté Meta).
        self.assertEqual(entry['erp_leads'], 0)

    # ── dédup QW10 ───────────────────────────────────────────────────────────
    def test_dedup_by_normalized_phone(self):
        self._meta(1)
        # même numéro sous deux formats → un seul lead compté.
        self._form_lead(telephone='+212 612-345-678')
        self._form_lead(telephone='0612345678')
        contract = reconciliation.reconcile(self.company, date=DAY)
        entry = contract['campaigns'][0]
        self.assertEqual(entry['denominators']['form_leads'], 1)
        self.assertEqual(entry['erp_leads'], 1)

    # ── divergence synthétique + alerte 🟠 ──────────────────────────────────
    def test_synthetic_divergence_detected_and_alerted(self):
        self._meta(10, spend='500.00')
        for _ in range(3):
            self._form_lead()
        contract = reconciliation.run_daily_reconciliation(self.company, DAY)
        entry = contract['campaigns'][0]
        self.assertTrue(entry['divergent'])
        self.assertEqual(entry['status'], 'ecart')
        self.assertEqual(entry['delta_leads'], 7)
        self.assertTrue(entry['cause_fr'])
        # snapshot persisté.
        snap = ReconciliationSnapshot.objects.get(
            company=self.company, date=DAY, campaign=self.camp)
        self.assertEqual(snap.meta_leads, 10)
        self.assertEqual(snap.erp_leads, 3)
        self.assertEqual(snap.status, ReconciliationSnapshot.Statut.ECART)
        # alerte 🟠 (sévérité ATTENTION par défaut).
        alert = EngineAlert.objects.get(company=self.company)
        self.assertEqual(alert.severity, EngineAlert.Severity.ATTENTION)
        self.assertIn('Divergence silencieuse', alert.message)

    def test_webhook_gap_flagged_a_verifier(self):
        # Meta compte, ERP a zéro → statut « à vérifier » + cause « webhook ».
        self._meta(5)
        contract = reconciliation.run_daily_reconciliation(self.company, DAY)
        entry = contract['campaigns'][0]
        self.assertEqual(entry['status'], 'a_verifier')
        self.assertEqual(entry['cause_fr'], reconciliation.CAUSE_WEBHOOK)

    def test_idempotent_upsert_and_no_double_alert(self):
        self._meta(10, spend='500.00')
        for _ in range(3):
            self._form_lead()
        reconciliation.run_daily_reconciliation(self.company, DAY)
        reconciliation.run_daily_reconciliation(self.company, DAY)
        # un seul snapshot pour (société, jour, campagne).
        self.assertEqual(
            ReconciliationSnapshot.objects.filter(
                company=self.company, date=DAY, campaign=self.camp).count(), 1)
        # une seule alerte (pas de re-alerte sur divergence déjà connue).
        self.assertEqual(EngineAlert.objects.filter(
            company=self.company).count(), 1)

    # ── contrat JSON stable ─────────────────────────────────────────────────
    def test_stable_json_contract_keys(self):
        self._meta(2, spend='100.00')
        self._form_lead()
        self._form_lead()
        contract = reconciliation.reconcile(self.company, date=DAY)
        for key in ('date_start', 'date_end', 'campaigns', 'unmatched',
                    'hand_entered', 'totals'):
            self.assertIn(key, contract)
        entry = contract['campaigns'][0]
        for key in ('campaign_meta_id', 'campaign_name', 'meta_leads',
                    'meta_spend', 'erp_leads', 'delta_leads', 'ratio',
                    'status', 'divergent', 'cause_fr', 'denominators',
                    'lead_ids'):
            self.assertIn(key, entry)

    def test_unmatched_bucket_never_dropped(self):
        # lead Meta-attribuable dont la campagne ne résout pas → bucket unmatched.
        self._lead(source=Lead.Source.META_LEAD_ADS, canal=Lead.Canal.META_ADS,
                   meta_campaign_id='inconnue')
        contract = reconciliation.reconcile(self.company, date=DAY)
        self.assertEqual(contract['unmatched']['form_leads'], 1)

    # ── scoping société ─────────────────────────────────────────────────────
    def test_scoping_ignores_other_company(self):
        other = Company.objects.create(nom='Other', slug='other-recon')
        self._meta(1)
        self._form_lead()
        self._lead(company=other, source=Lead.Source.META_LEAD_ADS,
                   canal=Lead.Canal.META_ADS, meta_campaign_id='c1')
        contract = reconciliation.reconcile(self.company, date=DAY)
        self.assertEqual(contract['campaigns'][0]['erp_leads'], 1)
