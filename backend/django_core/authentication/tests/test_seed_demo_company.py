"""Tests de la commande ``seed_demo_company`` (NTDMO1-5)."""
from django.core.management import call_command
from django.test import TestCase, override_settings

from authentication.models import Company, CustomUser


@override_settings(DEBUG=True)
class SeedDemoCompanyNTDMO1Test(TestCase):
    SLUG = 'taqinor-demo-full'

    def test_creates_company_profile_users_and_marks_demo(self):
        call_command('seed_demo_company', verbosity=0)
        company = Company.objects.get(slug=self.SLUG)
        # NTDMO8 — la société est marquée démo.
        self.assertTrue(company.est_demo)
        self.assertFalse(company.mode_presentation_actif)
        # Profil complet avec identité légale placeholder.
        profile = company.profile
        self.assertTrue(profile.ice)
        self.assertTrue(profile.identifiant_fiscal)
        self.assertTrue(profile.rc)
        # Utilisateurs connus créés et protégés.
        admin = CustomUser.objects.get(username='demo_admin_full')
        self.assertTrue(admin.is_protected)
        self.assertTrue(admin.check_password('DemoFull@2026!'))
        self.assertTrue(
            CustomUser.objects.filter(username='demo_resp_full').exists())

    def test_never_collides_with_seed_demo_company(self):
        call_command('seed_demo_company', verbosity=0)
        self.assertFalse(Company.objects.filter(slug='taqinor-demo').exists())

    def test_idempotent_run_twice_stable_counts(self):
        call_command('seed_demo_company', verbosity=0)
        c1 = Company.objects.count()
        u1 = CustomUser.objects.count()
        call_command('seed_demo_company', verbosity=0)
        self.assertEqual(Company.objects.count(), c1)
        self.assertEqual(CustomUser.objects.count(), u1)

    @override_settings(DEBUG=False)
    def test_refused_outside_debug_without_force(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('seed_demo_company', verbosity=0)
