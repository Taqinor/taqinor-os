"""NTOBS28 — export CSV/XLSX de l'historique SLA + incidents."""
import csv
import datetime
import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.statuspage.models import IncidentPublic
from authentication.models import Company
from core.sla import generer_snapshot_societe

User = get_user_model()


class SlaExportCsvTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='ntobs28-acme')
        self.user = User.objects.create_user(
            'u1', password='x', company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_csv_contains_sla_and_incident_rows(self):
        generer_snapshot_societe(self.company, datetime.date(2026, 6, 1))
        IncidentPublic.objects.create(
            titre='Panne API', company=None, debute_le=timezone.now())
        resp = self.client.get('/api/django/core/sla/export-csv/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        content = resp.content.decode('utf-8')
        rows = list(csv.reader(io.StringIO(content)))
        flat = [cell for row in rows for cell in row]
        self.assertIn('periode', flat)
        self.assertIn('Panne API', flat)

    def test_scoped_to_own_company(self):
        autre = Company.objects.create(nom='Autre', slug='ntobs28-autre')
        mine = generer_snapshot_societe(self.company, datetime.date(2026, 6, 1))
        mine.uptime_pct = 99.9
        mine.save(update_fields=['uptime_pct'])
        theirs = generer_snapshot_societe(autre, datetime.date(2026, 6, 1))
        theirs.uptime_pct = 42.0
        theirs.save(update_fields=['uptime_pct'])
        resp = self.client.get('/api/django/core/sla/export-csv/')
        content = resp.content.decode('utf-8')
        self.assertIn('99.9', content)
        self.assertNotIn('42.0', content)

    def test_xlsx_format_returns_spreadsheet(self):
        generer_snapshot_societe(self.company, datetime.date(2026, 6, 1))
        resp = self.client.get('/api/django/core/sla/export-csv/?format=xlsx')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_requires_authentication(self):
        resp = APIClient().get('/api/django/core/sla/export-csv/')
        self.assertEqual(resp.status_code, 401)
