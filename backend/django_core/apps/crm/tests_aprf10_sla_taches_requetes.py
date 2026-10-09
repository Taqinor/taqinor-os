"""APRF10 — les tâches SLA (``recycler_leads_non_travailles`` et son jumeau
``escalader_rappels_demandes``) lisent les leads DÉJÀ escaladés en UNE
requête par société : un passage coûte le même nombre de requêtes avec 20 ou
50 dormants déjà escaladés, et un lead non escaladé l'est une seule fois.

Test-du-test : remettre le ``.exists()`` par lead ⇒ requêtes ∝ leads
(test_deja_escalades_gratuits) ; ignorer l'ensemble ⇒ double escalade
(test_nouveau_lead_escalade_une_fois).
"""
import datetime

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from authentication.models import Company
from apps.crm import stages
from apps.crm.management.commands import (
    escalader_rappels_demandes as rappels,
    recycler_leads_non_travailles as recyclage,
)
from apps.crm.models import Lead, LeadActivity
from apps.parametres.models import CompanyProfile


class SlaTachesRequetesTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='APRF10 Solaire', slug='aprf10-sla')
        CompanyProfile.objects.create(company=self.company, lead_sla_hours=24)
        self.now = timezone.now()

    def _dormant(self, marque, **kw):
        lead = Lead.objects.create(
            company=self.company, nom='Dormant', stage=stages.NEW, **kw)
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=self.now - datetime.timedelta(days=10),
            contact_preference_set_at=(
                self.now - datetime.timedelta(days=10)
                if kw.get('contact_preference') else None))
        if marque:
            LeadActivity.objects.create(
                company=self.company, lead=lead, user=None,
                kind=LeadActivity.Kind.NOTE, body=f'{marque} (déjà)')
        return lead

    def _requetes(self, fn):
        with CaptureQueriesContext(connection) as ctx:
            fn(now=self.now, dry_run=True)
        return len(ctx.captured_queries)

    def test_deja_escalades_gratuits(self):
        for _ in range(20):
            self._dormant(recyclage.ESCALATION_MARKER)
        self._requetes(recyclage.recycler_leads_non_travailles)
        a_20 = self._requetes(recyclage.recycler_leads_non_travailles)
        for _ in range(30):
            self._dormant(recyclage.ESCALATION_MARKER)
        a_50 = self._requetes(recyclage.recycler_leads_non_travailles)
        self.assertEqual(a_50, a_20)

    def test_nouveau_lead_escalade_une_fois(self):
        for _ in range(20):
            self._dormant(recyclage.ESCALATION_MARKER)
        neuf = self._dormant(None)
        nb, _ = recyclage.recycler_leads_non_travailles(now=self.now)
        self.assertEqual(nb, 1)
        nb, _ = recyclage.recycler_leads_non_travailles(now=self.now)
        self.assertEqual(nb, 0)
        self.assertEqual(LeadActivity.objects.filter(
            lead=neuf, body__startswith=recyclage.ESCALATION_MARKER).count(),
            1)

    def test_rappels_jumeau_une_seule_escalade(self):
        for _ in range(5):
            self._dormant(rappels.ESCALATION_MARKER,
                          contact_preference='phone_ok')
        neuf = self._dormant(None, contact_preference='phone_ok')
        self.assertEqual(rappels.escalader_rappels_demandes(now=self.now), 1)
        self.assertEqual(rappels.escalader_rappels_demandes(now=self.now), 0)
        self.assertEqual(LeadActivity.objects.filter(
            lead=neuf, body__startswith=rappels.ESCALATION_MARKER).count(), 1)
