"""DC13 — localisation chantier : repli sur ``client.adresse`` sans lead.

``installations.create_installation_from_devis`` consomme ce selector pour
remplir ``site_adresse``. Avec un lead on garde ses valeurs ; sans lead,
``site_adresse`` retombe sur l'adresse du client au lieu de rester vide.
"""
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.crm import selectors


class TestSiteLocationForDevis(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='dc13-co', defaults={'nom': 'DC13 Co'})[0]
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', adresse='12 rue du Client')

    def test_lead_values_used_when_lead_present(self):
        lead = Lead.objects.create(
            company=self.company, nom='Prospect', adresse='5 av du Lead',
            ville='Casablanca', gps_lat=Decimal('33.5'),
            gps_lng=Decimal('-7.6'))
        devis = SimpleNamespace(lead=lead, client=self.client_obj)
        loc = selectors.site_location_for_devis(devis)
        self.assertEqual(loc['site_adresse'], '5 av du Lead')
        self.assertEqual(loc['site_ville'], 'Casablanca')
        self.assertEqual(loc['gps_lat'], Decimal('33.5'))
        self.assertEqual(loc['gps_lng'], Decimal('-7.6'))

    def test_client_address_fallback_without_lead(self):
        devis = SimpleNamespace(lead=None, client=self.client_obj)
        loc = selectors.site_location_for_devis(devis)
        self.assertEqual(loc['site_adresse'], '12 rue du Client')
        # Le client n'a ni ville ni GPS → restent None (jamais fabriqués).
        self.assertIsNone(loc['site_ville'])
        self.assertIsNone(loc['gps_lat'])
        self.assertIsNone(loc['gps_lng'])

    def test_no_lead_no_client(self):
        devis = SimpleNamespace(lead=None, client=None)
        loc = selectors.site_location_for_devis(devis)
        self.assertEqual(loc, {
            'site_adresse': None, 'site_ville': None,
            'gps_lat': None, 'gps_lng': None})
