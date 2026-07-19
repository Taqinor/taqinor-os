"""PUB64 — calculateur recyclage COLD : taux de reconversion RÉEL par
âge-au-COLD (cold_reactivation_by_age_bucket) et le dénominateur CAC-par-mode
(new_leads_by_mode_meta). Aucun taux fabriqué sur un échantillon minuscule."""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity
from apps.crm.selectors import (
    cold_reactivation_by_age_bucket, new_leads_by_mode_meta,
)
from apps.crm.stages import COLD, NEW, SIGNED, STAGE_LABELS


def _enter_cold(company, lead, *, days_since_creation):
    """Écrit une LeadActivity 'entrée en COLD' à ``days_since_creation`` après
    la création du lead (horodatage forcé — auto_now_add contourné)."""
    activity = LeadActivity.objects.create(
        company=company, lead=lead, kind=LeadActivity.Kind.MODIFICATION,
        field='stage', old_value=STAGE_LABELS[NEW],
        new_value=STAGE_LABELS[COLD])
    stamp = lead.date_creation + datetime.timedelta(days=days_since_creation)
    LeadActivity.objects.filter(pk=activity.pk).update(created_at=stamp)
    return activity


def _leave_cold(company, lead, *, new_stage_label):
    LeadActivity.objects.create(
        company=company, lead=lead, kind=LeadActivity.Kind.MODIFICATION,
        field='stage', old_value=STAGE_LABELS[COLD],
        new_value=new_stage_label)


class ColdReactivationByAgeBucketTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB64 CRM Co')

    def test_no_cold_history_returns_all_none_rates(self):
        buckets = cold_reactivation_by_age_bucket(self.company)
        self.assertEqual(len(buckets), 4)
        self.assertTrue(all(b['rate'] is None for b in buckets))
        self.assertTrue(all(b['total'] == 0 for b in buckets))

    def test_lead_never_left_cold_not_reconverted(self):
        lead = Lead.objects.create(
            company=self.company, nom='ColdForever', stage=COLD)
        _enter_cold(self.company, lead, days_since_creation=10)
        rows = cold_reactivation_by_age_bucket(self.company)
        buckets = {b['bucket']: b for b in rows}
        self.assertEqual(buckets['0-30j']['total'], 1)
        self.assertEqual(buckets['0-30j']['reconverted'], 0)

    def test_lead_left_cold_and_now_signed_counts_reconverted(self):
        lead = Lead.objects.create(
            company=self.company, nom='Recycled', stage=SIGNED)
        _enter_cold(self.company, lead, days_since_creation=45)
        _leave_cold(self.company, lead, new_stage_label=STAGE_LABELS[SIGNED])
        rows = cold_reactivation_by_age_bucket(self.company)
        buckets = {b['bucket']: b for b in rows}
        self.assertEqual(buckets['30-90j']['total'], 1)
        self.assertEqual(buckets['30-90j']['reconverted'], 1)

    def test_rate_none_below_minimum_sample(self):
        lead = Lead.objects.create(
            company=self.company, nom='Solo', stage=SIGNED)
        _enter_cold(self.company, lead, days_since_creation=5)
        _leave_cold(self.company, lead, new_stage_label=STAGE_LABELS[SIGNED])
        rows = cold_reactivation_by_age_bucket(self.company)
        buckets = {b['bucket']: b for b in rows}
        # 1 lead seulement dans le bucket < MIN_SAMPLE_COLD_BUCKET (3).
        self.assertIsNone(buckets['0-30j']['rate'])

    def test_lead_perdu_never_counted_reconverted_even_if_stage_signed(self):
        lead = Lead.objects.create(
            company=self.company, nom='PerduApresRecyclage', stage=SIGNED,
            perdu=True)
        _enter_cold(self.company, lead, days_since_creation=5)
        _leave_cold(self.company, lead, new_stage_label=STAGE_LABELS[SIGNED])
        rows = cold_reactivation_by_age_bucket(self.company)
        buckets = {b['bucket']: b for b in rows}
        self.assertEqual(buckets['0-30j']['reconverted'], 0)


class NewLeadsByModeMetaTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB64 Mode Co')

    def test_meta_leads_grouped_by_mode(self):
        now = timezone.now()
        Lead.objects.create(
            company=self.company, nom='Resi', canal=Lead.Canal.META_ADS,
            type_installation='RESIDENTIEL')
        Lead.objects.create(
            company=self.company, nom='Indus', canal=Lead.Canal.WHATSAPP_CTWA,
            type_installation='INDUSTRIEL')
        # Canal non-Meta : jamais compté ici.
        Lead.objects.create(
            company=self.company, nom='Phone', canal=Lead.Canal.TELEPHONE,
            type_installation='RESIDENTIEL')
        result = new_leads_by_mode_meta(
            self.company, date_start=(now - datetime.timedelta(days=1)).date(),
            date_end=(now + datetime.timedelta(days=1)).date())
        self.assertEqual(result.get('RESIDENTIEL'), 1)
        self.assertEqual(result.get('INDUSTRIEL'), 1)

    def test_mode_absent_from_window_not_in_dict(self):
        result = new_leads_by_mode_meta(
            self.company, date_start=datetime.date(2020, 1, 1),
            date_end=datetime.date(2020, 1, 31))
        self.assertEqual(result, {})
