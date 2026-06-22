"""B3 — the Lead detail serializer exposes the client's roof/bill fields
read-only, so the authenticated design page can hydrate the pinned roof via
GET /api/django/crm/leads/<id>/.

Run:
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \
        python manage.py test apps.crm.tests_lead_roof_fields -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from .models import Lead

User = get_user_model()


class TestLeadRoofFieldsExposed(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='b3-co', defaults={'nom': 'B3 Co'})[0]
        self.user = User.objects.create_user(
            username='b3user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Roof', prenom='Lead',
            roof_point={'lat': 34.02, 'lng': -6.83},
            roof_outline=[[34.0, -6.8], [34.001, -6.8], [34.001, -6.801]],
            bill_kwh=Decimal('420.00'))

    def _detail(self, lead_id):
        return self.api.get(f'/api/django/crm/leads/{lead_id}/')

    def test_detail_includes_roof_and_bill_fields(self):
        resp = self._detail(self.lead.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('roof_point', resp.data)
        self.assertIn('roof_outline', resp.data)
        self.assertIn('bill_kwh', resp.data)
        self.assertEqual(resp.data['roof_point'], {'lat': 34.02, 'lng': -6.83})
        self.assertEqual(len(resp.data['roof_outline']), 3)
        self.assertEqual(str(resp.data['bill_kwh']), '420.00')

    def test_roof_fields_are_read_only_not_writable(self):
        # A PATCH must NOT overwrite the server-side roof pin (read-only).
        resp = self.api.patch(
            f'/api/django/crm/leads/{self.lead.id}/',
            {'roof_point': {'lat': 0, 'lng': 0}, 'bill_kwh': '1'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        # Unchanged — the read-only fields were ignored.
        self.assertEqual(self.lead.roof_point, {'lat': 34.02, 'lng': -6.83})
        self.assertEqual(str(self.lead.bill_kwh), '420.00')
