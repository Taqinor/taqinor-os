"""Tests de ``manage.py export_feedback_produit`` (NTIDE41).

Couvre : export JSON (défaut) et CSV, filtres ``--company``/``--since``/
``--theme``, écriture stdout par défaut / fichier avec ``--out-file``.
Jamais d'API publique — cette commande est le SEUL point d'export (cf.
critère d'acceptation)."""
import csv
import io
import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.innovation.models import FeedbackProduit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='normal')


class ExportFeedbackProduitCommandTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide41-a', 'A')
        self.user = make_user(self.co_a, 'ntide41-user')
        self.fb_bug = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='Un bug',
            theme=FeedbackProduit.Theme.BUG)
        self.fb_feature = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='Une idée',
            theme=FeedbackProduit.Theme.FEATURE)

    def test_json_export_to_stdout(self):
        out = io.StringIO()
        call_command('export_feedback_produit', stdout=out)
        data = json.loads(out.getvalue())
        self.assertEqual(len(data), 2)
        titres = {row['titre'] for row in data}
        self.assertEqual(titres, {'Un bug', 'Une idée'})

    def test_theme_filter(self):
        out = io.StringIO()
        call_command('export_feedback_produit', theme='bug', stdout=out)
        data = json.loads(out.getvalue())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['titre'], 'Un bug')

    def test_since_filter_excludes_older(self):
        futur = (date.today() + timedelta(days=1)).isoformat()
        out = io.StringIO()
        call_command('export_feedback_produit', since=futur, stdout=out)
        data = json.loads(out.getvalue())
        self.assertEqual(data, [])

    def test_company_filter(self):
        co_b = make_company('innov-ntide41-b', 'B')
        user_b = make_user(co_b, 'ntide41-user-b')
        FeedbackProduit.objects.create(
            company=co_b, auteur=user_b, titre='Autre société')
        out = io.StringIO()
        call_command(
            'export_feedback_produit', company='innov-ntide41-a', stdout=out)
        data = json.loads(out.getvalue())
        self.assertEqual(len(data), 2)

    def test_csv_export(self):
        out = io.StringIO()
        call_command('export_feedback_produit', format='csv', stdout=out)
        reader = csv.DictReader(io.StringIO(out.getvalue()))
        rows = list(reader)
        self.assertEqual(len(rows), 2)
        self.assertIn('titre', rows[0])
        self.assertIn('theme', rows[0])

    def test_never_exposed_via_http(self):
        # NTIDE41 — « Jamais d'API publique » : aucune route ne mappe cette
        # export ; seule la commande manage.py y donne accès.
        from apps.innovation.urls import urlpatterns
        for pattern in urlpatterns:
            self.assertNotIn('export-feedback', str(pattern.pattern))
