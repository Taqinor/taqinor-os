"""APRF18 (C-APRF-009) — ``relances`` et ``sla-breach`` sérialisent EN LOT,
comme la liste des leads.

Sonde P-4 V_VA : ``relances`` 32 → 132 requêtes (10 par lead),
``sla-breach`` 87 → 137 (5 par lead), alors que ``/crm/leads/`` restait
plat. Les deux actions passent désormais par la sérialisation partagée de
``LeadViewSet.list`` (cartes posées en contexte).

``CaptureQueriesContext`` à 3 puis 13 leads ; aucun mock.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

User = get_user_model()
RELANCES = '/api/django/crm/leads/relances/?scope=overdue'
SLA = '/api/django/crm/leads/sla-breach/'


class JumeauxListeLeadsTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='APRF18 Solaire', slug='aprf18-leads')
        self.user = User.objects.create_user(
            username='aprf18-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))
        self.n = 0

    def _leads(self, nombre):
        ancien = timezone.now() - datetime.timedelta(days=5)
        for _ in range(nombre):
            self.n += 1
            lead = Lead.objects.create(
                company=self.company, nom=f'Lead {self.n}', owner=self.user,
                stage=stages.NEW)
            Lead.objects.filter(pk=lead.pk).update(
                relance_date=timezone.localdate() - datetime.timedelta(days=2),
                date_creation=ancien, first_contacted_at=None,
                stage=stages.NEW)
            Devis.objects.create(
                company=self.company, reference=f'DEV-APRF18-{self.n:04d}',
                lead=lead, client=Client.objects.create(
                    company=self.company, nom=f'Client {self.n}'),
                statut='brouillon', taux_tva=Decimal('20.00'),
                remise_globale=Decimal('0'), created_by=self.user)

    def _compter(self, url):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200, resp.content)
        return len(ctx.captured_queries), resp.data

    def test_requetes_constantes(self):
        self._leads(3)
        relances_3, data_r3 = self._compter(RELANCES)
        sla_3, data_s3 = self._compter(SLA)
        self.assertEqual(len(data_r3['results']), 3)
        self.assertEqual(len(data_s3['results']), 3)
        self._leads(10)
        relances_13, data_r13 = self._compter(RELANCES)
        sla_13, data_s13 = self._compter(SLA)
        self.assertEqual(len(data_r13['results']), 13)
        self.assertEqual(len(data_s13['results']), 13)
        self.assertEqual(relances_3, relances_13)
        self.assertEqual(sla_3, sla_13)
        # Même forme que la liste des leads.
        liste = self.api.get('/api/django/crm/leads/').data
        ligne = (liste['results'] if isinstance(liste, dict) else liste)[0]
        self.assertEqual(set(data_r13['results'][0]), set(ligne))
