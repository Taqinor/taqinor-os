"""Tests de ``manage.py seed_innovation_demo`` (NTIDE66).

Couvre : les volumes semés (5 idées / 2 campagnes / 10 retours),
l'idempotence (relancer ne duplique rien), le scope société, et les deux
refus explicites (société inconnue, société sans utilisateur).
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from authentication.models import Company

from apps.innovation.models import CampagneInnovation, FeedbackProduit, Idee

User = get_user_model()


@override_settings(DEBUG=True)
class SeedInnovationDemoTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='innov-ntide66', defaults={'nom': 'Démo NTIDE66'})
        self.user = User.objects.create_user(
            username='ntide66-user', password='x', company=self.company)

    def _seed(self):
        call_command('seed_innovation_demo', '--company', 'innov-ntide66')

    def test_seeds_expected_volumes(self):
        self._seed()
        self.assertEqual(Idee.objects.filter(company=self.company).count(), 5)
        self.assertEqual(
            CampagneInnovation.objects.filter(company=self.company).count(), 2)
        self.assertEqual(
            FeedbackProduit.objects.filter(company=self.company).count(), 10)

    def test_is_idempotent(self):
        self._seed()
        self._seed()
        self.assertEqual(Idee.objects.filter(company=self.company).count(), 5)
        self.assertEqual(
            CampagneInnovation.objects.filter(company=self.company).count(), 2)
        self.assertEqual(
            FeedbackProduit.objects.filter(company=self.company).count(), 10)

    def test_scoped_to_the_requested_company(self):
        autre, _ = Company.objects.get_or_create(
            slug='innov-ntide66-b', defaults={'nom': 'Autre'})
        self._seed()
        self.assertEqual(Idee.objects.filter(company=autre).count(), 0)

    def test_unknown_company_refused(self):
        with self.assertRaises(CommandError):
            call_command('seed_innovation_demo', '--company', 'inexistante')

    def test_company_without_user_refused(self):
        Company.objects.get_or_create(
            slug='innov-ntide66-vide', defaults={'nom': 'Vide'})
        with self.assertRaises(CommandError):
            call_command('seed_innovation_demo',
                         '--company', 'innov-ntide66-vide')

    @override_settings(DEBUG=False)
    def test_refused_outside_debug_without_force(self):
        with self.assertRaises(CommandError):
            self._seed()
        self.assertEqual(Idee.objects.filter(company=self.company).count(), 0)
