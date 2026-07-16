"""NTPLT47 — générateur de données à l'échelle : garde-fou DEBUG + création."""
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from authentication.models import Company


class SeedScaleGuardTests(TestCase):
    @override_settings(DEBUG=False)
    def test_refuses_outside_debug_without_force(self):
        with self.assertRaises(CommandError):
            call_command('seed_scale', '--companies', '1', stdout=StringIO())

    @override_settings(DEBUG=False)
    def test_force_flag_allows_outside_debug(self):
        call_command('seed_scale', '--companies', '1', '--users', '0',
                     '--leads', '0', '--devis', '0', '--lignes', '0',
                     '--mouvements', '0', '--force-je-sais', stdout=StringIO())
        self.assertTrue(Company.objects.filter(nom__startswith='[SEED_SCALE]')
                        .exists())


@override_settings(DEBUG=True)
class SeedScaleCreationTests(TestCase):
    def test_seeds_companies_and_users(self):
        call_command('seed_scale', '--companies', '2', '--users', '3',
                     '--leads', '0', '--devis', '0', '--lignes', '0',
                     '--mouvements', '0', stdout=StringIO())
        self.assertEqual(
            Company.objects.filter(nom__startswith='[SEED_SCALE]').count(), 2)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.assertEqual(
            User.objects.filter(username__startswith='seed_scale_u').count(), 3)

    def test_idempotent_by_tag(self):
        call_command('seed_scale', '--companies', '2', '--users', '0',
                     '--leads', '0', '--devis', '0', '--lignes', '0',
                     '--mouvements', '0', stdout=StringIO())
        call_command('seed_scale', '--companies', '2', '--users', '0',
                     '--leads', '0', '--devis', '0', '--lignes', '0',
                     '--mouvements', '0', stdout=StringIO())
        # Relancer avec le même --companies ne double pas les sociétés taguées.
        self.assertEqual(
            Company.objects.filter(nom__startswith='[SEED_SCALE]').count(), 2)

    def test_missing_faker_raises(self):
        with mock.patch.dict('sys.modules', {'faker': None}):
            with self.assertRaises(CommandError):
                call_command('seed_scale', '--companies', '1',
                             stdout=StringIO())
