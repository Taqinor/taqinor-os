"""Tests YHARD10 — export anonymisé du parc de données (clone UAT/staging).

Couvre : garde --confirm, anonymisation de chaque catégorie PII (aucune vraie
PII ne subsiste dans le fichier de sortie), intégrité FK (les identifiants ne
changent jamais), et non-modification de la base source (lecture seule).
"""
import json
import os
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from authentication.models import Company
from core import anonymize_export
from apps.crm.models import Client


class ExportAnonymiseGuardTests(TestCase):
    def test_refuses_without_confirm(self):
        with self.assertRaises(CommandError):
            call_command('export_anonymise')


class ExportAnonymiseContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='YHARD10 Co')
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Kasri', prenom='Reda',
            email='reda.kasri@example.com', telephone='+212600112233',
            adresse='123 rue Réelle, Casablanca')

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.output_path = os.path.join(self.tmpdir, 'export.json')
        anonymize_export.reset_counter()

    def test_source_database_is_never_modified(self):
        call_command(
            'export_anonymise', confirm=True, output=self.output_path,
            models=['crm.Client'])
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.nom, 'Kasri')
        self.assertEqual(self.client_obj.email, 'reda.kasri@example.com')

    def test_output_file_contains_no_real_pii(self):
        call_command(
            'export_anonymise', confirm=True, output=self.output_path,
            models=['crm.Client'])
        with open(self.output_path, encoding='utf-8') as fh:
            data = json.load(fh)
        serialized = json.dumps(data)
        self.assertNotIn('Kasri', serialized)
        self.assertNotIn('reda.kasri@example.com', serialized)
        self.assertNotIn('+212600112233', serialized)
        self.assertNotIn('123 rue Réelle', serialized)

    def test_output_preserves_relational_integrity_pk(self):
        call_command(
            'export_anonymise', confirm=True, output=self.output_path,
            models=['crm.Client'])
        with open(self.output_path, encoding='utf-8') as fh:
            data = json.load(fh)
        pks = [row['pk'] for row in data if row['model'] == 'crm.client']
        self.assertIn(self.client_obj.pk, pks)

    def test_each_client_gets_distinct_anonymized_values(self):
        Client.objects.create(
            company=self.company, nom='Dupont', prenom='Jean',
            email='jean.dupont@example.com', telephone='+212611223344')
        call_command(
            'export_anonymise', confirm=True, output=self.output_path,
            models=['crm.Client'])
        with open(self.output_path, encoding='utf-8') as fh:
            data = json.load(fh)
        noms = [row['fields']['nom'] for row in data if row['model'] == 'crm.client']
        self.assertEqual(len(noms), len(set(noms)))

    def test_unknown_model_raises(self):
        with self.assertRaises(CommandError):
            call_command(
                'export_anonymise', confirm=True, output=self.output_path,
                models=['bogus.NoSuchModel'])
