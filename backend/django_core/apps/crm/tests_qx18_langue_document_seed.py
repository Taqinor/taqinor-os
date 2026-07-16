"""QX18 — Arabic doesn't die at the document layer.

Covers: `resolve_client_for_lead` seeds `Client.langue_document='ar'` when
the lead prefers darija — the arabophone client no longer gets a French
flagship PDF at the decision moment by default. Frontend surface (client
form language field) already existed (N93/tests_n93_langue_document.py) —
this covers the missing backend seeding link.
"""
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.crm.services import resolve_client_for_lead


class ResolveClientForLeadSeedsLangueDocumentTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QX18', slug='taqinor-qx18')

    def test_darija_lead_creates_client_with_arabic_documents(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead Darija',
            langue_preferee=Lead.LanguePreferee.DARIJA)
        client = resolve_client_for_lead(lead)
        self.assertEqual(client.langue_document, Client.LangueDocument.AR)

    def test_french_lead_creates_client_with_french_documents(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead FR',
            langue_preferee=Lead.LanguePreferee.FR)
        client = resolve_client_for_lead(lead)
        self.assertEqual(client.langue_document, Client.LangueDocument.FR)

    def test_no_preference_defaults_to_french_documents(self):
        lead = Lead.objects.create(company=self.company, nom='Lead Sans Pref')
        client = resolve_client_for_lead(lead)
        self.assertEqual(client.langue_document, Client.LangueDocument.FR)

    def test_reused_existing_client_language_never_overwritten(self):
        # Client déjà existant (matché par téléphone/email) : sa préférence
        # documentaire manuelle prime — jamais écrasée par la préférence du
        # lead qui le retrouve.
        existing = Client.objects.create(
            company=self.company, nom='Client Existant', email='existant@example.com',
            langue_document=Client.LangueDocument.FR)
        lead = Lead.objects.create(
            company=self.company, nom='Lead Darija Retrouve',
            email='existant@example.com',
            langue_preferee=Lead.LanguePreferee.DARIJA)
        client = resolve_client_for_lead(lead)
        self.assertEqual(client.pk, existing.pk)
        self.assertEqual(client.langue_document, Client.LangueDocument.FR)
