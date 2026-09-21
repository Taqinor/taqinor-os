"""Tests KB5 — seed_kb_templates management command.

Couvre :
  - le seed crée les articles attendus pour une société ;
  - idempotence : une deuxième exécution ne crée aucun doublon ;
  - isolation entre sociétés : chaque société reçoit ses propres articles ;
  - les articles créés portent bien le bon ``company`` FK (jamais cross-tenant) ;
  - l'argument ``--company`` cible une seule société.
"""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase

from authentication.models import Company

from apps.kb.models import KbArticle
from apps.kb.management.commands.seed_kb_templates import KB_TEMPLATES

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


EXPECTED_TITRES = [t[0] for t in KB_TEMPLATES]
EXPECTED_COUNT = len(EXPECTED_TITRES)


class SeedKbTemplatesTests(TestCase):

    def setUp(self):
        self.co_a = make_company('kbseed-a', 'Société A')
        self.co_b = make_company('kbseed-b', 'Société B')

    # ── articles créés ────────────────────────────────────────────────────

    def test_seed_creates_expected_articles_for_company(self):
        """All KB_TEMPLATES are created for an existing company."""
        out = StringIO()
        call_command('seed_kb_templates', '--company', 'kbseed-a', stdout=out)
        count = KbArticle.objects.filter(company=self.co_a).count()
        self.assertEqual(count, EXPECTED_COUNT)

    def test_seed_creates_correct_titres(self):
        """Every expected titre is present after seeding."""
        call_command('seed_kb_templates', '--company', 'kbseed-a',
                     stdout=StringIO())
        titres = set(
            KbArticle.objects.filter(company=self.co_a)
            .values_list('titre', flat=True)
        )
        for expected in EXPECTED_TITRES:
            self.assertIn(expected, titres, f"Missing article: {expected}")

    def test_articles_are_published(self):
        """Seeded articles have statut=PUBLIE."""
        call_command('seed_kb_templates', '--company', 'kbseed-a',
                     stdout=StringIO())
        non_publie = KbArticle.objects.filter(company=self.co_a).exclude(
            statut=KbArticle.Statut.PUBLIE)
        self.assertEqual(
            non_publie.count(), 0,
            "Some seeded articles are not in PUBLIE status")

    # ── idempotence ───────────────────────────────────────────────────────

    def test_idempotent_second_run_creates_nothing(self):
        """Running the command twice produces no duplicates."""
        call_command('seed_kb_templates', '--company', 'kbseed-a',
                     stdout=StringIO())
        call_command('seed_kb_templates', '--company', 'kbseed-a',
                     stdout=StringIO())
        count = KbArticle.objects.filter(company=self.co_a).count()
        self.assertEqual(count, EXPECTED_COUNT)

    def test_idempotent_all_companies(self):
        """Seeding all companies twice creates no duplicates."""
        call_command('seed_kb_templates', stdout=StringIO())
        call_command('seed_kb_templates', stdout=StringIO())
        for company in [self.co_a, self.co_b]:
            count = KbArticle.objects.filter(company=company).count()
            self.assertEqual(
                count, EXPECTED_COUNT,
                f"Company {company.slug} has {count} articles, "
                f"expected {EXPECTED_COUNT}")

    # ── isolation entre sociétés ──────────────────────────────────────────

    def test_company_scoping_articles_belong_to_correct_company(self):
        """Articles seeded for A are not visible from B (company FK)."""
        call_command('seed_kb_templates', '--company', 'kbseed-a',
                     stdout=StringIO())
        count_b = KbArticle.objects.filter(company=self.co_b).count()
        self.assertEqual(count_b, 0,
                         "Articles seeded for A leaked into B")

    def test_all_companies_get_independent_sets(self):
        """When seeding all companies, each gets its own copy."""
        call_command('seed_kb_templates', stdout=StringIO())
        total = KbArticle.objects.count()
        self.assertEqual(total, EXPECTED_COUNT * 2,
                         "Total article count should be templates × companies")
        for company in [self.co_a, self.co_b]:
            count = KbArticle.objects.filter(company=company).count()
            self.assertEqual(count, EXPECTED_COUNT)

    # ── option --company ──────────────────────────────────────────────────

    def test_unknown_company_raises_command_error(self):
        """Passing an unknown slug raises CommandError."""
        with self.assertRaises(CommandError):
            call_command('seed_kb_templates', '--company', 'nonexistent-slug',
                         stdout=StringIO())

    def test_company_arg_seeds_only_that_company(self):
        """--company seeds only the target company, not others."""
        call_command('seed_kb_templates', '--company', 'kbseed-a',
                     stdout=StringIO())
        count_a = KbArticle.objects.filter(company=self.co_a).count()
        count_b = KbArticle.objects.filter(company=self.co_b).count()
        self.assertEqual(count_a, EXPECTED_COUNT)
        self.assertEqual(count_b, 0)

    # ── contenu minimal ───────────────────────────────────────────────────

    def test_articles_have_non_empty_corps(self):
        """All seeded articles have non-empty body content."""
        call_command('seed_kb_templates', '--company', 'kbseed-a',
                     stdout=StringIO())
        empty_corps = KbArticle.objects.filter(
            company=self.co_a, corps='')
        self.assertEqual(empty_corps.count(), 0,
                         "Some seeded articles have empty body")

    def test_articles_have_categorie(self):
        """All seeded articles have a non-empty categorie."""
        call_command('seed_kb_templates', '--company', 'kbseed-a',
                     stdout=StringIO())
        no_cat = KbArticle.objects.filter(
            company=self.co_a, categorie='')
        self.assertEqual(no_cat.count(), 0,
                         "Some seeded articles have no categorie")
