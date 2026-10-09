"""AACQ5 (C-AACQ-004) — `selectors.chantier_client_id(company, chantier_id)` :
id du client propriétaire du chantier, ou None ; lecture seule, scopée société.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_aacq_chantier_client"
"""
from django.test import TestCase

from authentication.models import Company

from apps.installations import selectors
from apps.installations.models import Installation
from apps.crm.models import Client


class ChantierClientTests(TestCase):
    def setUp(self):
        self.co1 = Company.objects.create(nom='AACQ5 1', slug='aacq5-1')
        self.co2 = Company.objects.create(nom='AACQ5 2', slug='aacq5-2')
        self.client_a = Client.objects.create(
            company=self.co1, nom='A', prenom='Client',
            email='aacq5@example.invalid')
        self.chantier = Installation.objects.create(
            company=self.co1, reference='CH-AACQ5', client=self.client_a)
        self.sans_client = Installation.objects.create(
            company=self.co1, reference='CH-AACQ5-SC')

    def test_client_du_chantier(self):
        self.assertEqual(
            selectors.chantier_client_id(self.co1, self.chantier.id),
            self.client_a.id)

    def test_autre_societe_none(self):
        self.assertIsNone(
            selectors.chantier_client_id(self.co2, self.chantier.id))

    def test_sans_client_none(self):
        self.assertIsNone(
            selectors.chantier_client_id(self.co1, self.sans_client.id))
