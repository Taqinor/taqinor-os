"""QX17 — Client dedup by phone, not just email.

Covers: `resolve_client_for_lead` matches an existing `crm.Client` by
`normalize_phone` equality (within the same company) when the email lookup
misses — a repeat client with no/different email must reuse the existing
Client instead of fragmenting history and `plafond_credit` into a duplicate.
"""
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.crm.services import resolve_client_for_lead


class ResolveClientForLeadPhoneDedupTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QX17', slug='taqinor-qx17')

    def test_same_phone_different_formatting_reuses_existing_client(self):
        existing = Client.objects.create(
            company=self.company, nom='Client Existant',
            telephone='0612345678')
        lead = Lead.objects.create(
            company=self.company, nom='Même Client', telephone='+212 6 12-34-56-78')
        client = resolve_client_for_lead(lead)
        self.assertEqual(client.pk, existing.pk)
        self.assertEqual(Client.objects.filter(company=self.company).count(), 1)

    def test_no_email_match_falls_back_to_phone(self):
        existing = Client.objects.create(
            company=self.company, nom='Sans Email Correspondant',
            email='autre@example.com', telephone='0600112233')
        lead = Lead.objects.create(
            company=self.company, nom='Nouveau Contact',
            email='different@example.com', telephone='0600112233')
        client = resolve_client_for_lead(lead)
        self.assertEqual(client.pk, existing.pk)

    def test_email_match_still_takes_priority_over_phone(self):
        by_email = Client.objects.create(
            company=self.company, nom='Par Email', email='cible@example.com',
            telephone='0611111111')
        Client.objects.create(
            company=self.company, nom='Par Telephone Seul',
            telephone='0622222222')
        lead = Lead.objects.create(
            company=self.company, nom='Lead Test', email='cible@example.com',
            telephone='0622222222')
        client = resolve_client_for_lead(lead)
        self.assertEqual(client.pk, by_email.pk)

    def test_no_phone_no_email_creates_new_client(self):
        lead = Lead.objects.create(company=self.company, nom='Sans Contact')
        client = resolve_client_for_lead(lead)
        self.assertIsNotNone(client.pk)
        self.assertEqual(Client.objects.filter(company=self.company).count(), 1)

    def test_cross_company_phone_never_matches(self):
        other = Company.objects.create(nom='Autre QX17', slug='autre-qx17')
        Client.objects.create(
            company=other, nom='Client Autre Societe', telephone='0699887766')
        lead = Lead.objects.create(
            company=self.company, nom='Lead Meme Tel', telephone='0699887766')
        client = resolve_client_for_lead(lead)
        # Aucun match cross-tenant — un NOUVEAU client est créé dans la
        # société du lead, jamais réutilisé depuis une autre société.
        self.assertEqual(client.company_id, self.company.pk)
        self.assertEqual(Client.objects.filter(company=other).count(), 1)
        self.assertEqual(Client.objects.filter(company=self.company).count(), 1)

    def test_no_matching_phone_creates_new_client(self):
        Client.objects.create(
            company=self.company, nom='Client Sans Rapport',
            telephone='0655555555')
        lead = Lead.objects.create(
            company=self.company, nom='Lead Different', telephone='0644444444')
        client = resolve_client_for_lead(lead)
        self.assertNotEqual(client.telephone, '0655555555')
        self.assertEqual(Client.objects.filter(company=self.company).count(), 2)
