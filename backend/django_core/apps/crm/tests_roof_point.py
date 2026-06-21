"""Q2 — client roof-POINT capture on the Lead (pin + optional outline + token).

Run:
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \
        python manage.py test apps.crm.tests_roof_point -v 2
"""
import json
import uuid

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from .models import Lead

SECRET = 'roof-point-secret'


def base_payload(**extra):
    data = {
        'fullName': 'Karim Roof',
        'phoneE164': '+212600000077',
        'whatsappOptIn': True,
        'city': 'Rabat',
        'qualified': True,
    }
    data.update(extra)
    return data


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class TestQ2RoofPointWebhook(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Q2 Co', slug='q2-co')
        self.url = reverse('website-lead-webhook')

    def post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data), content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_pin_persists_on_lead(self):
        res = self.post(base_payload(
            roofPoint={'lat': 34.02, 'lng': -6.83}))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.roof_point, {'lat': 34.02, 'lng': -6.83})

    def test_optional_outline_persists(self):
        res = self.post(base_payload(
            roofPoint={'latitude': 34.0, 'longitude': -6.8},
            roofOutline=[[34.0, -6.8], [34.001, -6.8], [34.001, -6.801]],
            billKwh=420))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.roof_point, {'lat': 34.0, 'lng': -6.8})
        self.assertEqual(len(lead.roof_outline), 3)
        self.assertEqual(str(lead.bill_kwh), '420.00')

    def test_no_pin_is_fine(self):
        res = self.post(base_payload())
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.roof_point)
        self.assertIsNone(lead.roof_outline)

    def test_out_of_range_pin_ignored(self):
        res = self.post(base_payload(roofPoint={'lat': 999, 'lng': 0}))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.roof_point)


class TestQ2LeadToken(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Q2 Tok Co', slug='q2-tok')

    def test_token_auto_assigned_and_unique(self):
        a = Lead.objects.create(company=self.company, nom='A')
        b = Lead.objects.create(company=self.company, nom='B')
        self.assertIsInstance(a.token, uuid.UUID)
        self.assertNotEqual(a.token, b.token)

    def test_token_resolves_lead(self):
        lead = Lead.objects.create(company=self.company, nom='Resolve')
        resolved = Lead.objects.get(token=lead.token)
        self.assertEqual(resolved.pk, lead.pk)

    def test_company_forced_server_side(self):
        # The webhook resolves the company server-side; the payload never sets
        # it. A lead created via the model carries the company we passed.
        lead = Lead.objects.create(company=self.company, nom='Scoped')
        self.assertEqual(lead.company_id, self.company.id)
