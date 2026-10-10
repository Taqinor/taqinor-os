"""ACRM43 — ``create_lead_depuis_ticket`` ne réutilise jamais un lead
archivé et trace le ``contexte`` du ticket au chatter du lead réutilisé —
rejoue la sonde LSVC3-8.

Test-du-test : retirer ``is_archived=False`` ⇒ test_archive_non_reutilise
échoue.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm import stages, leads_intake
from apps.crm.models import Client, Lead, LeadActivity

User = get_user_model()


class TicketLeadTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM43 Solaire', slug='acrm43-ticket')
        self.user = User.objects.create_user(
            username='acrm43-sav', password='x', company=self.company,
            role_legacy='responsable')
        self.client_c = Client.objects.create(
            company=self.company, nom='Ticket', prenom='Client')

    def test_archive_non_reutilise(self):
        archive = Lead.objects.create(
            company=self.company, nom='Ancien', client=self.client_c,
            stage=stages.CONTACTED, is_archived=True)
        lead, created = leads_intake.create_lead_depuis_ticket(
            company=self.company, user=self.user, client=self.client_c,
            contexte='upsell ticket')
        self.assertTrue(created)
        self.assertNotEqual(lead.pk, archive.pk)
        lead.refresh_from_db()
        self.assertFalse(lead.is_archived)
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body='upsell ticket').exists())

    def test_contexte_ecrit_a_la_reutilisation(self):
        ouvert = Lead.objects.create(
            company=self.company, nom='Ouvert', client=self.client_c,
            stage=stages.CONTACTED)
        lead, created = leads_intake.create_lead_depuis_ticket(
            company=self.company, user=self.user, client=self.client_c,
            contexte='upsell ticket')
        self.assertFalse(created)
        self.assertEqual(lead.pk, ouvert.pk)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)
        self.assertTrue(LeadActivity.objects.filter(
            lead=ouvert, kind=LeadActivity.Kind.NOTE,
            body='upsell ticket').exists())
