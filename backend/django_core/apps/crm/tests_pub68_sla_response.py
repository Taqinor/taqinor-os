"""PUB68 — SLA première réponse : leads_meta_sla_depasse (sous-ensemble Meta
de YLEAD14 leads_sla_depasse) + leads_response_time_rows (temps de première
réponse par lead réellement contacté, matière première de la médiane par
ad)."""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Lead
from apps.crm.selectors import (
    leads_meta_sla_depasse, leads_response_time_rows,
)


class LeadsMetaSlaDepasseTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB68 CRM Co')

    def test_meta_lead_over_sla_included(self):
        now = timezone.now()
        old = now - datetime.timedelta(hours=5)
        lead = Lead.objects.create(
            company=self.company, nom='MetaColdLead', canal=Lead.Canal.META_ADS)
        Lead.objects.filter(pk=lead.pk).update(date_creation=old)
        rows = leads_meta_sla_depasse(self.company, now=now, seuil_heures=1)
        self.assertIn(lead, list(rows))

    def test_non_meta_canal_excluded(self):
        now = timezone.now()
        old = now - datetime.timedelta(hours=5)
        lead = Lead.objects.create(
            company=self.company, nom='PhoneLead', canal=Lead.Canal.TELEPHONE)
        Lead.objects.filter(pk=lead.pk).update(date_creation=old)
        rows = leads_meta_sla_depasse(self.company, now=now, seuil_heures=1)
        self.assertNotIn(lead, list(rows))

    def test_already_contacted_meta_lead_excluded(self):
        now = timezone.now()
        old = now - datetime.timedelta(hours=5)
        lead = Lead.objects.create(
            company=self.company, nom='ContactedMeta',
            canal=Lead.Canal.WHATSAPP_CTWA, first_contacted_at=now)
        Lead.objects.filter(pk=lead.pk).update(date_creation=old)
        rows = leads_meta_sla_depasse(self.company, now=now, seuil_heures=1)
        self.assertNotIn(lead, list(rows))


class LeadsResponseTimeRowsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB68 Response Co')

    def test_never_contacted_lead_absent(self):
        Lead.objects.create(company=self.company, nom='JamaisContacte')
        self.assertEqual(leads_response_time_rows(self.company), [])

    def test_contacted_lead_response_minutes_computed(self):
        lead = Lead.objects.create(
            company=self.company, nom='Contacte', meta_ad_id='ad_pub68')
        created = lead.date_creation
        contacted = created + datetime.timedelta(minutes=7)
        Lead.objects.filter(pk=lead.pk).update(first_contacted_at=contacted)
        rows = leads_response_time_rows(self.company)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]['response_minutes'], 7.0, places=1)
        self.assertEqual(rows[0]['meta_ad_id'], 'ad_pub68')
