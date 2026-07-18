"""Tests de la commande ``reset_demo_company`` (NTDMO6)."""
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from authentication.models import Company


@override_settings(DEBUG=True)
class ResetDemoCompanyTest(TestCase):
    SLUG = 'taqinor-demo-full'

    def test_refuses_slug_without_demo(self):
        with self.assertRaises(CommandError):
            call_command('reset_demo_company', slug='acme-corp', verbosity=0)

    def test_requires_slug(self):
        # --slug est obligatoire (pas de défaut) → erreur sans lui.
        with self.assertRaises(CommandError):
            call_command('reset_demo_company', verbosity=0)

    def test_wipes_and_reseeds_to_identical_counts(self):
        from apps.crm.models import Lead
        from apps.ventes.models import Devis
        call_command('seed_demo_company', verbosity=0)
        company = Company.objects.get(slug=self.SLUG)
        leads_before = Lead.objects.filter(company=company).count()
        devis_before = Devis.objects.filter(company=company).count()
        self.assertGreater(leads_before, 0)

        call_command('reset_demo_company', slug=self.SLUG, verbosity=0)
        company = Company.objects.get(slug=self.SLUG)  # re-created
        self.assertEqual(
            Lead.objects.filter(company=company).count(), leads_before)
        self.assertEqual(
            Devis.objects.filter(company=company).count(), devis_before)

    def test_reset_on_missing_company_just_seeds(self):
        call_command('reset_demo_company', slug=self.SLUG, verbosity=0)
        self.assertTrue(Company.objects.filter(slug=self.SLUG).exists())
