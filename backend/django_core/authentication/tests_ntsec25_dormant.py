"""NTSEC25 — Comptes dormants : détection & désactivation automatique.

Garanties : un compte inactif au-delà du seuil est listé puis désactivé ;
seuil 0 = jamais ; réactivation manuelle possible ; sessions révoquées ; scope
société.
"""
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.parametres.models import CompanyProfile
from authentication.models import UserSession
from authentication.selectors import comptes_dormants
from testkit.factories import CompanyFactory, UserFactory


class DormantAccountsTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def _session(self, user, days_ago):
        s = UserSession.objects.create(
            company=self.company, user=user, jti=f'j{user.pk}', revoked=False)
        UserSession.objects.filter(pk=s.pk).update(
            last_seen_at=timezone.now() - timedelta(days=days_ago))
        return s

    def test_selector_lists_inactive(self):
        old = UserFactory(company=self.company, username='old')
        self._session(old, 120)
        recent = UserFactory(company=self.company, username='recent')
        self._session(recent, 5)
        dormants = set(
            comptes_dormants(self.company, 90).values_list(
                'username', flat=True))
        self.assertIn('old', dormants)
        self.assertNotIn('recent', dormants)

    def test_selector_includes_never_logged_in(self):
        UserFactory(company=self.company, username='ghost')
        dormants = set(
            comptes_dormants(self.company, 90).values_list(
                'username', flat=True))
        self.assertIn('ghost', dormants)

    def test_threshold_zero_is_inert(self):
        u = UserFactory(company=self.company, username='x')
        self._session(u, 999)
        self.assertEqual(comptes_dormants(self.company, 0).count(), 0)

    def test_superuser_never_dormant(self):
        su = UserFactory(
            company=self.company, username='su', is_superuser=True)
        self._session(su, 999)
        self.assertNotIn(
            'su',
            comptes_dormants(self.company, 90).values_list(
                'username', flat=True))

    def test_scoped_to_company(self):
        other = CompanyFactory()
        stranger = UserFactory(company=other, username='stranger')
        UserSession.objects.create(
            company=other, user=stranger, jti='js', revoked=False)
        UserSession.objects.filter(user=stranger).update(
            last_seen_at=timezone.now() - timedelta(days=999))
        self.assertNotIn(
            'stranger',
            comptes_dormants(self.company, 90).values_list(
                'username', flat=True))

    def test_command_deactivates_and_revokes(self):
        CompanyProfile.objects.create(company=self.company, dormant_days=90)
        old = UserFactory(company=self.company, username='dormant')
        self._session(old, 120)
        call_command('desactiver_comptes_dormants',
                     '--company', str(self.company.id))
        old.refresh_from_db()
        self.assertFalse(old.is_active)
        self.assertFalse(
            UserSession.objects.filter(user=old, revoked=False).exists())

    def test_command_zero_threshold_noop(self):
        CompanyProfile.objects.create(company=self.company, dormant_days=0)
        u = UserFactory(company=self.company, username='keep')
        self._session(u, 999)
        call_command('desactiver_comptes_dormants',
                     '--company', str(self.company.id))
        u.refresh_from_db()
        self.assertTrue(u.is_active)
