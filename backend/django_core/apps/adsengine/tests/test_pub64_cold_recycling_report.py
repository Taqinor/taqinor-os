"""PUB64 — cold_recycling_report : GO/NO-GO recycler un lead COLD vs acheter
un lead neuf. Recommandation seule ; s'abstient honnêtement sans donnée."""
import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity
from apps.crm.stages import COLD, NEW, STAGE_LABELS

from apps.adsengine import reporting
from apps.adsengine.models import AdCampaignMirror, InsightSnapshot


class ColdRecyclingReportTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB64 Report Co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp_pub64', name='Camp',
            status='PAUSED')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)

    def test_no_data_abstains_with_explicit_warning(self):
        result = reporting.cold_recycling_report(self.company)
        self.assertFalse(result['donnees_suffisantes'])
        self.assertIsNotNone(result['avertissement'])
        self.assertEqual(result['cac_par_mode'], [])

    def test_with_cold_history_and_meta_leads_computes_cac(self):
        today = datetime.date.today()
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct,
            object_id=self.camp.pk, date=today, spend=Decimal('500.00'),
            results=1)
        Lead.objects.create(
            company=self.company, nom='MetaLead', canal=Lead.Canal.META_ADS,
            type_installation='RESIDENTIEL')

        lead = Lead.objects.create(
            company=self.company, nom='Cold1', stage=COLD)
        LeadActivity.objects.create(
            company=self.company, lead=lead, kind=LeadActivity.Kind.MODIFICATION,
            field='stage', old_value=STAGE_LABELS[NEW],
            new_value=STAGE_LABELS[COLD])

        result = reporting.cold_recycling_report(self.company)
        self.assertTrue(result['donnees_suffisantes'])
        self.assertIsNone(result['avertissement'])
        cac_resi = next(
            c for c in result['cac_par_mode']
            if c['mode_installation'] == 'RESIDENTIEL')
        self.assertEqual(cac_resi['cac_actuel'], '500.00')
        self.assertEqual(len(result['reconversion_par_age_cold']), 4)
