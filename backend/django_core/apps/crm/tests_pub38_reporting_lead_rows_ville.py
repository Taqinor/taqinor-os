"""PUB38 — ``reporting_lead_rows`` porte désormais ``ville`` (additif).

Le harnais d'incrémentalité geo-holdout d'``apps.adsengine`` (zone tenue vs
zones actives) a besoin de la ville du lead pour grouper leads/signatures par
zone — champ ajouté SANS casser les consommateurs existants (entonnoir/
cohortes de ``apps.adsengine.reporting``, qui ignorent simplement la clé).
"""
import datetime

from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Lead
from apps.crm.selectors import reporting_lead_rows


class ReportingLeadRowsVilleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='RLV Co', slug='rlv-co')

    def test_row_carries_raw_ville(self):
        Lead.objects.create(
            company=self.company, nom='Client A', ville='Casablanca')
        rows = reporting_lead_rows(self.company)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['ville'], 'Casablanca')

    def test_missing_ville_normalized_to_empty_string(self):
        Lead.objects.create(company=self.company, nom='Client B', ville=None)
        rows = reporting_lead_rows(self.company)
        self.assertEqual(rows[0]['ville'], '')

    def test_existing_keys_untouched(self):
        Lead.objects.create(
            company=self.company, nom='Client C', ville='Rabat')
        rows = reporting_lead_rows(self.company)
        for key in ('id', 'utm_campaign', 'meta_campaign_id', 'stage',
                    'perdu', 'is_meta_channel', 'created_date',
                    'signature_date'):
            self.assertIn(key, rows[0])

    def test_date_window_still_applies(self):
        old = Lead.objects.create(
            company=self.company, nom='Old', ville='Fès')
        Lead.objects.filter(pk=old.pk).update(
            date_creation=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc))
        rows = reporting_lead_rows(
            self.company, date_start=datetime.date(2026, 1, 1))
        self.assertEqual(rows, [])
