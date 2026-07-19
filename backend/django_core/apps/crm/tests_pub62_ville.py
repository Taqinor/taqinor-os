"""PUB62 — leads_ville_rows : matière première (ville/signé) de la carte
chaleur ville adsengine (jamais une ville vide fabriquée)."""
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.crm.selectors import leads_ville_rows
from apps.crm.stages import COLD, SIGNED


class LeadsVilleRowsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB62 CRM Co')

    def test_lead_without_ville_absent(self):
        Lead.objects.create(company=self.company, nom='Sans ville')
        self.assertEqual(leads_ville_rows(self.company), [])

    def test_lead_with_ville_present_and_signed_flag(self):
        Lead.objects.create(
            company=self.company, nom='Signé Casa', ville='Casablanca',
            stage=SIGNED)
        Lead.objects.create(
            company=self.company, nom='Froid Rabat', ville='Rabat',
            stage=COLD)
        rows = {r['ville']: r for r in leads_ville_rows(self.company)}
        self.assertTrue(rows['Casablanca']['signed'])
        self.assertFalse(rows['Rabat']['signed'])

    def test_perdu_lead_never_counted_signed_even_if_stage_signed(self):
        Lead.objects.create(
            company=self.company, nom='Perdu', ville='Marrakech',
            stage=SIGNED, perdu=True)
        rows = leads_ville_rows(self.company)
        self.assertFalse(rows[0]['signed'])

    def test_archived_lead_excluded(self):
        Lead.objects.create(
            company=self.company, nom='Archivé', ville='Fès',
            is_archived=True)
        self.assertEqual(leads_ville_rows(self.company), [])

    def test_ville_is_stripped(self):
        Lead.objects.create(
            company=self.company, nom='Espace', ville='  Tanger  ')
        rows = leads_ville_rows(self.company)
        self.assertEqual(rows[0]['ville'], 'Tanger')
