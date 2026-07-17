"""ADSDEEP17 — Tests du miroir de lead Meta alimenté par événement domaine.

Prouve : le webhook CRM existant crée le lead CRM ET (via meta_lead_captured) un
MetaLeadMirror ; jamais de doublon leadgen_id ; l'événement est catalogué
(couverture verte) ; phone_key normalisé + crm_lead_id posés.
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from apps.adsengine.models import MetaLeadMirror
from apps.adsengine.receivers import on_meta_lead_captured


class ReceiverTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ML Co', slug='ml')

    def test_upsert_creates_mirror_with_phone_key(self):
        lead = SimpleNamespace(pk=42, telephone='+212612345678')
        on_meta_lead_captured(
            sender='test', lead=lead, company=self.company,
            leadgen_id='lg-1', ad_id='ad1', adset_id='as1',
            campaign_id='', form_id='f1', created_time='2026-07-16T10:00:00Z',
            is_organic=False)
        m = MetaLeadMirror.objects.get(company=self.company, leadgen_id='lg-1')
        self.assertEqual(m.ad_id, 'ad1')
        self.assertEqual(m.adset_id, 'as1')
        self.assertEqual(m.crm_lead_id, 42)
        self.assertFalse(m.is_organic)
        self.assertTrue(m.phone_key)  # normalisé via crm.selectors
        self.assertIsNotNone(m.created_time)

    def test_idempotent_no_duplicate_leadgen(self):
        lead = SimpleNamespace(pk=7, telephone='0612345678')
        for _ in range(2):
            on_meta_lead_captured(
                sender='test', lead=lead, company=self.company,
                leadgen_id='lg-2', ad_id='ad1', adset_id='', campaign_id='',
                form_id='', created_time=None, is_organic=False)
        self.assertEqual(
            MetaLeadMirror.objects.filter(
                company=self.company, leadgen_id='lg-2').count(), 1)

    def test_organic_lead_flag(self):
        lead = SimpleNamespace(pk=8, telephone='')
        on_meta_lead_captured(
            sender='test', lead=lead, company=self.company,
            leadgen_id='lg-3', ad_id='', adset_id='', campaign_id='',
            form_id='', created_time=None, is_organic=True)
        m = MetaLeadMirror.objects.get(company=self.company, leadgen_id='lg-3')
        self.assertTrue(m.is_organic)


class EventCatalogTests(TestCase):
    def test_event_is_catalogued(self):
        # NTPLT12 — un signal non catalogué ferait échouer ce test de couverture.
        from core.event_coverage import uncatalogued_events
        self.assertNotIn('meta_lead_captured', uncatalogued_events())


@override_settings(
    META_LEAD_ADS_ACCESS_TOKEN='tok', META_LEAD_ADS_VERIFY_TOKEN='vtok')
class WebhookIntegrationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ML Web', slug='mlweb')

    @patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_webhook_creates_lead_and_mirror(self, mock_fetch):
        mock_fetch.return_value = {'field_data': [
            {'name': 'full_name', 'values': ['Ahmed Bennani']},
            {'name': 'phone_number', 'values': ['+212612345678']},
        ]}
        payload = {'entry': [{'changes': [{'value': {
            'leadgen_id': 'lg-web-1', 'ad_id': 'ad9', 'adgroup_id': 'as9',
            'form_id': 'f9', 'created_time': '2026-07-16T09:00:00Z',
        }}]}]}
        url = reverse('meta-lead-ads-webhook')
        resp = self.client.post(
            url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        # Le lead CRM a été créé (comportement existant)…
        from apps.crm.models import Lead
        self.assertTrue(Lead.objects.filter(
            company=self.company, external_id='lg-web-1').exists())
        # …ET le miroir Meta (via l'événement domaine).
        m = MetaLeadMirror.objects.get(
            company=self.company, leadgen_id='lg-web-1')
        self.assertEqual(m.ad_id, 'ad9')
        self.assertEqual(m.adset_id, 'as9')
        self.assertIsNotNone(m.crm_lead_id)

    @patch('apps.crm.webhooks.fetch_meta_lead_data')
    def test_webhook_idempotent_mirror(self, mock_fetch):
        mock_fetch.return_value = {'field_data': [
            {'name': 'phone_number', 'values': ['+212611111111']}]}
        payload = {'entry': [{'changes': [{'value': {
            'leadgen_id': 'lg-web-2', 'ad_id': 'ad1', 'form_id': 'f1'}}]}]}
        url = reverse('meta-lead-ads-webhook')
        body = json.dumps(payload)
        self.client.post(url, data=body, content_type='application/json')
        self.client.post(url, data=body, content_type='application/json')
        self.assertEqual(
            MetaLeadMirror.objects.filter(
                company=self.company, leadgen_id='lg-web-2').count(), 1)
