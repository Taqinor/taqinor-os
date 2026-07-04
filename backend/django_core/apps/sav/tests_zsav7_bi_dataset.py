"""ZSAV7 — dataset BI `sav_tickets` (déclaré côté sav, lu par core.data_explorer).

Couvre :
  * le dataset est enregistré (via apps.py ready(), déjà chargé en test) ;
  * le queryset est scopé société (aucune fuite cross-tenant) ;
  * `delai_resolution_jours` se calcule correctement / reste vide (ticket
    ouvert) ;
  * `cout` est un champ interrogeable (le masquage vit côté reporting).
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.sav.bi_datasets import DATASET_NAME
from apps.sav.models import Ticket
from authentication.models import Company
from core import data_explorer

User = get_user_model()


class SavTicketsDatasetTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='zsav7-co', defaults={'nom': 'ZSAV7 Co'})[0]
        self.other_company = Company.objects.get_or_create(
            slug='zsav7-other', defaults={'nom': 'ZSAV7 Other'})[0]
        self.user = User.objects.create_user(
            username='zsav7_u', password='x', company=self.company)
        self.tech = User.objects.create_user(
            username='zsav7_tech', password='x', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='ClientZSAV7')

    def test_dataset_registered(self):
        names = {d['name'] for d in data_explorer.list_datasets()}
        self.assertIn(DATASET_NAME, names)

    def test_scoped_to_company(self):
        Ticket.objects.create(
            company=self.company, reference='ZT-1', client=self.client_obj,
            technicien_responsable=self.tech)
        other_client = Client.objects.create(
            company=self.other_company, nom='AutreClient')
        Ticket.objects.create(
            company=self.other_company, reference='ZT-OTHER',
            client=other_client)
        rows = data_explorer.run_query(
            DATASET_NAME, self.company, self.user,
            {'select': ['id', 'statut']})
        self.assertEqual(len(rows), 1)

    def test_delai_resolution_jours_computed(self):
        today = date.today()
        t = Ticket.objects.create(
            company=self.company, reference='ZT-2', client=self.client_obj,
            technicien_responsable=self.tech, date_resolution=today)
        Ticket.objects.filter(pk=t.pk).update(
            date_creation=today - timedelta(days=3))
        rows = data_explorer.run_query(
            DATASET_NAME, self.company, self.user,
            {'select': ['id', 'delai_resolution_jours']})
        row = next(r for r in rows if r['id'] == t.id)
        self.assertEqual(row['delai_resolution_jours'].days, 3)

    def test_delai_resolution_jours_none_when_open(self):
        t = Ticket.objects.create(
            company=self.company, reference='ZT-3', client=self.client_obj)
        rows = data_explorer.run_query(
            DATASET_NAME, self.company, self.user,
            {'select': ['id', 'delai_resolution_jours']})
        row = next(r for r in rows if r['id'] == t.id)
        self.assertIsNone(row['delai_resolution_jours'])

    def test_group_by_technicien_statut(self):
        Ticket.objects.create(
            company=self.company, reference='ZT-4', client=self.client_obj,
            technicien_responsable=self.tech, statut=Ticket.Statut.NOUVEAU)
        Ticket.objects.create(
            company=self.company, reference='ZT-5', client=self.client_obj,
            technicien_responsable=self.tech, statut=Ticket.Statut.CLOTURE)
        rows = data_explorer.run_query(
            DATASET_NAME, self.company, self.user, {
                'group_by': ['technicien_responsable__username', 'statut'],
                'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}],
            })
        total = sum(r['n'] for r in rows)
        self.assertEqual(total, 2)

    def test_cout_field_queryable(self):
        from decimal import Decimal
        Ticket.objects.create(
            company=self.company, reference='ZT-6', client=self.client_obj,
            cout=Decimal('150.00'))
        rows = data_explorer.run_query(
            DATASET_NAME, self.company, self.user, {'select': ['id', 'cout']})
        self.assertTrue(any(r['cout'] == Decimal('150.00') for r in rows))
