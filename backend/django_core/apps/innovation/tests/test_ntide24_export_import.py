"""Tests d'export/import JSON des idées (NTIDE24, dev/test).

Couvre : ``data_io.export_ideas``/``import_ideas`` (round-trip,
idempotence via titre+company+auteur, résolution société/auteur par
référence stable), et les deux commandes ``manage.py`` (fichier réel sur
disque, isolation multi-société via ``--company``).
"""
import json
import os
import tempfile

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.innovation.data_io import export_ideas, import_ideas
from apps.innovation.models import Idee

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company)


class DataIoRoundTripTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide24-a', 'A')
        self.co_b = make_company('innov-ntide24-b', 'B')
        self.author = make_user(self.co_a, 'ntide24-author')

    def test_export_serializes_key_fields(self):
        Idee.objects.create(
            company=self.co_a, titre='Idée export', description='Détail',
            contexte='SAV', auteur=self.author, votes_count=3)
        data = export_ideas(company=self.co_a)
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row['titre'], 'Idée export')
        self.assertEqual(row['description'], 'Détail')
        self.assertEqual(row['contexte'], 'SAV')
        self.assertEqual(row['auteur'], 'ntide24-author')
        self.assertEqual(row['company'], 'innov-ntide24-a')
        self.assertEqual(row['votes_count'], 3)

    def test_export_filters_by_company(self):
        Idee.objects.create(company=self.co_a, titre='A')
        Idee.objects.create(company=self.co_b, titre='B')
        data = export_ideas(company=self.co_a)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['titre'], 'A')

    def test_export_without_company_covers_all(self):
        Idee.objects.create(company=self.co_a, titre='A')
        Idee.objects.create(company=self.co_b, titre='B')
        data = export_ideas()
        self.assertEqual(len(data), 2)

    def test_import_creates_idea(self):
        records = [{'titre': 'Nouvelle', 'description': 'X', 'company': 'innov-ntide24-a'}]
        result = import_ideas(records)
        self.assertEqual(result.created, 1)
        self.assertEqual(result.skipped, 0)
        self.assertTrue(
            Idee.objects.filter(company=self.co_a, titre='Nouvelle').exists())

    def test_import_resolves_auteur_by_username(self):
        records = [{'titre': 'Avec auteur', 'company': 'innov-ntide24-a',
                    'auteur': 'ntide24-author'}]
        import_ideas(records)
        idee = Idee.objects.get(titre='Avec auteur')
        self.assertEqual(idee.auteur_id, self.author.id)

    def test_import_idempotent_same_titre_company_auteur(self):
        records = [{'titre': 'Dup', 'company': 'innov-ntide24-a',
                    'auteur': 'ntide24-author'}]
        r1 = import_ideas(records)
        r2 = import_ideas(records)
        self.assertEqual(r1.created, 1)
        self.assertEqual(r2.created, 0)
        self.assertEqual(r2.skipped, 1)
        self.assertEqual(
            Idee.objects.filter(company=self.co_a, titre='Dup').count(), 1)

    def test_import_unknown_company_reported_as_error(self):
        records = [{'titre': 'Perdue', 'company': 'ne-existe-pas'}]
        result = import_ideas(records)
        self.assertEqual(result.created, 0)
        self.assertEqual(len(result.errors), 1)

    def test_import_missing_company_without_override_is_error(self):
        records = [{'titre': 'Sans société'}]
        result = import_ideas(records)
        self.assertEqual(result.created, 0)
        self.assertEqual(len(result.errors), 1)

    def test_import_company_override_wins_over_record(self):
        records = [{'titre': 'Rejouée', 'company': 'innov-ntide24-a'}]
        import_ideas(records, company=self.co_b)
        self.assertTrue(
            Idee.objects.filter(company=self.co_b, titre='Rejouée').exists())
        self.assertFalse(
            Idee.objects.filter(company=self.co_a, titre='Rejouée').exists())

    def test_full_round_trip(self):
        Idee.objects.create(
            company=self.co_a, titre='Round trip', auteur=self.author,
            votes_count=5, contexte='Stock')
        data = export_ideas(company=self.co_a)
        Idee.objects.all().delete()
        result = import_ideas(data)
        self.assertEqual(result.created, 1)
        restored = Idee.objects.get(company=self.co_a, titre='Round trip')
        self.assertEqual(restored.votes_count, 5)
        self.assertEqual(restored.contexte, 'Stock')
        self.assertEqual(restored.auteur_id, self.author.id)


class ManagementCommandsTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide24-cmd-a', 'A')
        self.co_b = make_company('innov-ntide24-cmd-b', 'B')

    def test_export_ideas_writes_json_file(self):
        Idee.objects.create(company=self.co_a, titre='Export CLI')
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'out.json')
            call_command(
                'export_ideas', '--company', 'innov-ntide24-cmd-a',
                '--out-file', path)
            with open(path, encoding='utf-8') as fh:
                data = json.load(fh)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]['titre'], 'Export CLI')

    def test_import_ideas_from_file_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'in.json')
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump([{'titre': 'Import CLI', 'company': 'innov-ntide24-cmd-a'}], fh)
            call_command('import_ideas', path)
            call_command('import_ideas', path)
            self.assertEqual(
                Idee.objects.filter(
                    company=self.co_a, titre='Import CLI').count(), 1)

    def test_import_ideas_company_override_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'in.json')
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump([{'titre': 'Forcée', 'company': 'innov-ntide24-cmd-a'}], fh)
            call_command('import_ideas', path, '--company', 'innov-ntide24-cmd-b')
            self.assertTrue(
                Idee.objects.filter(company=self.co_b, titre='Forcée').exists())
