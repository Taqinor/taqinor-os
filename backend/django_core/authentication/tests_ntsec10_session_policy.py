"""NTSEC10 — Politique de session par société (durée / inactivité / concurrence).

Garanties : seuils à 0 = comportement inchangé ; une session au-delà de la
durée absolue ou d'inactivité ne peut plus rafraîchir (et est révoquée) ; la
limite concurrente évince la session la plus ancienne.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework_simplejwt.tokens import RefreshToken

from apps.parametres.models import CompanyProfile
from authentication.models import UserSession
from authentication.session_policy import (
    enforce_concurrent_limit, refresh_allowed,
)
from testkit.factories import CompanyFactory, UserFactory


class SessionPolicyTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company, username='sp1')

    def _profile(self, **fields):
        return CompanyProfile.objects.create(company=self.company, **fields)

    def _session_for_token(self):
        token = RefreshToken.for_user(self.user)
        s = UserSession.objects.create(
            company=self.company, user=self.user,
            jti=token['jti'], revoked=False)
        return token, s

    def test_no_profile_allows_refresh(self):
        token, _ = self._session_for_token()
        self.assertTrue(refresh_allowed(str(token), self.user))

    def test_zero_thresholds_allow_refresh(self):
        self._profile(session_absolute_hours=0, session_idle_minutes=0)
        token, _ = self._session_for_token()
        self.assertTrue(refresh_allowed(str(token), self.user))

    def test_absolute_expiry_blocks_and_revokes(self):
        self._profile(session_absolute_hours=1)
        token, s = self._session_for_token()
        UserSession.objects.filter(pk=s.pk).update(
            created_at=timezone.now() - timedelta(hours=2))
        self.assertFalse(refresh_allowed(str(token), self.user))
        s.refresh_from_db()
        self.assertTrue(s.revoked)

    def test_idle_expiry_blocks_and_revokes(self):
        self._profile(session_idle_minutes=30)
        token, s = self._session_for_token()
        UserSession.objects.filter(pk=s.pk).update(
            last_seen_at=timezone.now() - timedelta(minutes=90))
        self.assertFalse(refresh_allowed(str(token), self.user))
        s.refresh_from_db()
        self.assertTrue(s.revoked)

    def test_recent_session_allowed(self):
        self._profile(session_absolute_hours=8, session_idle_minutes=30)
        token, _ = self._session_for_token()
        self.assertTrue(refresh_allowed(str(token), self.user))

    def test_concurrent_limit_evicts_oldest(self):
        self._profile(max_concurrent_sessions=2)
        s1 = UserSession.objects.create(
            company=self.company, user=self.user, jti='j1', revoked=False)
        UserSession.objects.filter(pk=s1.pk).update(
            created_at=timezone.now() - timedelta(hours=3))
        s2 = UserSession.objects.create(
            company=self.company, user=self.user, jti='j2', revoked=False)
        UserSession.objects.filter(pk=s2.pk).update(
            created_at=timezone.now() - timedelta(hours=2))
        UserSession.objects.create(
            company=self.company, user=self.user, jti='j3', revoked=False)
        enforce_concurrent_limit(self.user)
        s1.refresh_from_db()
        s2.refresh_from_db()
        # La plus ancienne (s1) est révoquée ; il reste 2 sessions actives.
        self.assertTrue(s1.revoked)
        self.assertFalse(s2.revoked)
        self.assertEqual(
            UserSession.objects.filter(
                user=self.user, revoked=False).count(), 2)

    def test_zero_limit_never_evicts(self):
        self._profile(max_concurrent_sessions=0)
        for j in ('a', 'b', 'c'):
            UserSession.objects.create(
                company=self.company, user=self.user, jti=j, revoked=False)
        enforce_concurrent_limit(self.user)
        self.assertEqual(
            UserSession.objects.filter(
                user=self.user, revoked=False).count(), 3)
