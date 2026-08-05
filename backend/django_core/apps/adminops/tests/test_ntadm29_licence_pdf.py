"""NTADM29 — export PDF « Utilisation des sièges » (plan, sièges, liste
nominative des comptes actifs). Moteur interne WeasyPrint mocké (comme
``apps.education.tests_ntedu17_bulletin``) — jamais le moteur de devis."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

User = get_user_model()


def _company(nom='NTADM29Co'):
    return Company.objects.create(nom=nom)


def _admin(company, username='admin'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy='admin', is_staff=True)


class LicencePdfExportTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.admin)

    def test_pdf_telechargeable(self):
        with mock.patch(
                'core.pdf.render_pdf', return_value=b'%PDF-1.4 fake') as rendu:
            resp = self.client_api.get('/api/django/adminops/licences/pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(rendu.called)

    def test_non_admin_refuse(self):
        normal = User.objects.create_user(
            username='u', password='pw', company=self.company,
            role_legacy='normal')
        c = APIClient()
        c.force_authenticate(normal)
        with mock.patch('core.pdf.render_pdf', return_value=b'%PDF-1.4 fake'):
            resp = c.get('/api/django/adminops/licences/pdf/')
        self.assertIn(resp.status_code, (401, 403))
