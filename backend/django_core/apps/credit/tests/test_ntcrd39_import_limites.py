"""NTCRD39 — import CSV en masse : lignes avec client inexistant en erreur,
les autres créées (jamais un blocage de tout le batch)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.credit.models import LimiteCredit
from apps.credit.services import importer_limites_csv
from apps.crm.models import Client

User = get_user_model()


def make_company(slug='ntcrd39-co', nom='NTCRD39 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class NTCRD39ImportLimitesTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ntcrd39_user', password='x', role_legacy='admin',
            company=self.company)
        self.c1 = Client.objects.create(
            company=self.company, nom='Un', email='c1@ntcrd39.com')
        self.c2 = Client.objects.create(
            company=self.company, nom='Deux', email='c2@ntcrd39.com')

    def test_partial_import_with_errors(self):
        csv = (
            'client,montant_limite,mode_hold\n'
            'c1@ntcrd39.com,50000,blocage\n'
            'c2@ntcrd39.com,30000,avertissement\n'
            'inconnu@ntcrd39.com,10000,\n'
        ).encode('utf-8')
        rapport = importer_limites_csv(
            self.company, csv, 'limites.csv', user=self.user)
        self.assertEqual(rapport['crees'], 2)
        self.assertEqual(len(rapport['erreurs']), 1)
        self.assertEqual(
            LimiteCredit.objects.get(client=self.c1).montant_limite,
            Decimal('50000'))
        self.assertEqual(
            LimiteCredit.objects.get(client=self.c1).mode_hold, 'blocage')

    def test_idempotent_upsert(self):
        csv = b'client,montant_limite\nc1@ntcrd39.com,50000\n'
        importer_limites_csv(self.company, csv, 'l.csv', user=self.user)
        csv2 = b'client,montant_limite\nc1@ntcrd39.com,70000\n'
        importer_limites_csv(self.company, csv2, 'l.csv', user=self.user)
        self.assertEqual(
            LimiteCredit.objects.filter(client=self.c1).count(), 1)
        self.assertEqual(
            LimiteCredit.objects.get(client=self.c1).montant_limite,
            Decimal('70000'))
