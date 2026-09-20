"""NTOBS17 — export PDF du trust center (dossier d'appel d'offres, générique)."""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from core.pdf_trust_center import _derniere_moyenne_sla, _trust_center_html
from core.sla import generer_snapshot_societe
from core.trust_center import TrustCenterEntry

User = get_user_model()


class DerniereMoyenneSlaTest(TestCase):
    def test_no_snapshot_returns_none(self):
        periode, moyenne = _derniere_moyenne_sla()
        self.assertIsNone(periode)
        self.assertIsNone(moyenne)

    def test_averages_across_companies_for_latest_period(self):
        c1 = Company.objects.create(nom='C1', slug='ntobs17-c1')
        c2 = Company.objects.create(nom='C2', slug='ntobs17-c2')
        periode = datetime.date(2026, 6, 1)
        s1 = generer_snapshot_societe(c1, periode)
        s1.uptime_pct = 99.0
        s1.save(update_fields=['uptime_pct'])
        s2 = generer_snapshot_societe(c2, periode)
        s2.uptime_pct = 97.0
        s2.save(update_fields=['uptime_pct'])
        found_periode, moyenne = _derniere_moyenne_sla()
        self.assertEqual(found_periode, periode)
        self.assertEqual(moyenne, 98.0)


class TrustCenterHtmlTest(TestCase):
    def test_html_never_leaks_company_identity(self):
        c1 = Company.objects.create(nom='SecretCo', slug='ntobs17-secret')
        generer_snapshot_societe(c1, datetime.date(2026, 6, 1))
        TrustCenterEntry.objects.create(
            categorie=TrustCenterEntry.Categorie.POLITIQUE, titre='Politique X')
        html = _trust_center_html()
        self.assertNotIn('SecretCo', html)
        self.assertIn('Politique X', html)


class TrustCenterExportPdfEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='ntobs17-acme')
        self.user = User.objects.create_user(
            'u1', password='x', company=self.company)
        self.client = APIClient()

    def test_public_endpoint_returns_pdf(self):
        with mock.patch('core.pdf.render_pdf', return_value=b'%PDF-fake'):
            resp = self.client.get('/api/django/core/trust-center/export-pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_endpoint_accessible_without_authentication(self):
        """Document commercial générique — pas de donnée société, pas
        d'authentification requise (comme /trust-center/)."""
        with mock.patch('core.pdf.render_pdf', return_value=b'%PDF-fake'):
            resp = APIClient().get('/api/django/core/trust-center/export-pdf/')
        self.assertEqual(resp.status_code, 200)
