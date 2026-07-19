"""PUB68 — response_time_by_ad : temps de première réponse MÉDIAN par ad
(minutes), résolu par la MÊME échelle d'attribution qu'ADSENG6."""
import datetime

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead

from apps.adsengine import reporting
from apps.adsengine.models import AdMirror, AdSetMirror, AdCampaignMirror


class ResponseTimeByAdTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB68 Reporting Co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp_68', name='Camp68',
            status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='ast_68', name='Adset68',
            campaign=self.camp)
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad_68', name='Ad68',
            adset=self.adset)

    def _lead(self, minutes):
        lead = Lead.objects.create(
            company=self.company, nom='P', meta_ad_id='ad_68')
        contacted = lead.date_creation + datetime.timedelta(minutes=minutes)
        Lead.objects.filter(pk=lead.pk).update(first_contacted_at=contacted)

    def test_no_contacted_leads_empty(self):
        self.assertEqual(reporting.response_time_by_ad(self.company), [])

    def test_median_computed_for_resolved_ad(self):
        self._lead(2)
        self._lead(4)
        self._lead(6)
        result = reporting.response_time_by_ad(self.company)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['meta_id'], 'ad_68')
        self.assertEqual(result[0]['median_response_minutes'], 4.0)
        self.assertEqual(result[0]['sample_size'], 3)

    def test_unresolved_ad_excluded(self):
        lead = Lead.objects.create(
            company=self.company, nom='NoAd', meta_ad_id='inconnu')
        contacted = lead.date_creation + datetime.timedelta(minutes=3)
        Lead.objects.filter(pk=lead.pk).update(first_contacted_at=contacted)
        self.assertEqual(reporting.response_time_by_ad(self.company), [])
