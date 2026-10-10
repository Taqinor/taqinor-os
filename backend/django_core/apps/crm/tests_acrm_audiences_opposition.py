"""ACRM56 (D-ACRM-5 (1)=(a)) — un lead « ne plus contacter » est exclu de
TOUT export d'audience publicitaire : graine lookalike, segments marketing,
identifiants de contact.

Test-du-test : retirer le filtre ``ne_plus_contacter`` des sélecteurs ⇒
``test_graine_sans_oppose`` et ``test_segment_sans_oppose`` échouent.
"""
from django.test import TestCase

from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.crm.selectors import (
    clients_contact_identifiers, lead_contact_identifiers,
    leads_matching_regles)
from authentication.models import Company


class AudiencesOppositionTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ACRM56', slug='taqinor-acrm56')
        self.client_oppose = Client.objects.create(
            company=self.company, nom='Oppose', prenom='Client',
            email='client-oppose@example.com', telephone='+212661000001')
        self.client_ok = Client.objects.create(
            company=self.company, nom='Ok', prenom='Client',
            email='client-ok@example.com', telephone='+212661000002')
        self.oppose = Lead.objects.create(
            company=self.company, nom='Oppose', prenom='Lead',
            email='oppose@example.com', telephone='+212661000003',
            stage=stages.SIGNED, ne_plus_contacter=True,
            client=self.client_oppose)
        self.ok = Lead.objects.create(
            company=self.company, nom='Ok', prenom='Lead',
            email='ok@example.com', telephone='+212661000004',
            stage=stages.SIGNED, client=self.client_ok)

    def test_graine_sans_oppose(self):
        from apps.adsengine.audiences import _signed_seed_contacts
        emails = {c['email'] for c in _signed_seed_contacts(self.company)}
        self.assertIn('ok@example.com', emails)
        self.assertNotIn('oppose@example.com', emails)

    def test_segment_sans_oppose(self):
        ids = set(leads_matching_regles(self.company, {}).values_list(
            'id', flat=True))
        self.assertIn(self.ok.id, ids)
        self.assertNotIn(self.oppose.id, ids)

    def test_identifiants_lead_sans_oppose(self):
        rows = lead_contact_identifiers(
            self.company, [self.oppose.id, self.ok.id])
        self.assertEqual([r['email'] for r in rows], ['ok@example.com'])

    def test_clients_via_lead_sans_oppose(self):
        emails = {r['email'] for r in clients_contact_identifiers(self.company)}
        self.assertIn('client-ok@example.com', emails)
        self.assertNotIn('client-oppose@example.com', emails)
