"""NTSEC9 — Tests du step-up MFA (``require_recent_mfa``).

Vérifie qu'une action listée sensible exige une MFA récente, qu'une session MFA
fraîche passe, qu'une session périmée ou absente est refusée (default-deny), et
que le défaut (``step_up_actions`` vide) laisse le comportement inchangé.
"""
from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.parametres.models_company import CompanyProfile
from authentication.models import UserSession
from testkit.factories import CompanyFactory, UserFactory

from apps.identity.stepup import require_recent_mfa


class StepUpMfaTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)

    def _profile(self, actions):
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'step_up_actions': actions})

    def _session(self, mfa_ago_minutes=None):
        """Crée une UserSession et renvoie le jeton refresh brut à poser en
        cookie. ``mfa_ago_minutes=None`` ⇒ pas de MFA sur la session."""
        refresh = RefreshToken.for_user(self.user)
        last = None
        if mfa_ago_minutes is not None:
            last = timezone.now() - timedelta(minutes=mfa_ago_minutes)
        UserSession.objects.create(
            user=self.user, company=self.company,
            jti=refresh['jti'], last_mfa_at=last)
        return str(refresh)

    def _req(self, refresh_raw=None, user=None):
        req = self.rf.post('/api/django/paie/run/')
        req.user = self.user if user is None else user
        if refresh_raw:
            req.COOKIES['refresh_token'] = refresh_raw
        return req

    def _perm(self, action='paie_run', minutes=5):
        return require_recent_mfa(action, minutes)()

    # ── Défaut inerte ──────────────────────────────────────────────────────
    def test_default_empty_actions_is_inactive(self):
        """Sans configuration (liste vide), l'action passe même sans MFA."""
        self._profile([])
        req = self._req()
        self.assertTrue(self._perm().has_permission(req, None))

    def test_no_profile_at_all_is_inactive(self):
        req = self._req()
        self.assertTrue(self._perm().has_permission(req, None))

    def test_action_not_listed_passes(self):
        """Une action NON listée n'est pas soumise au step-up."""
        self._profile(['autre_action'])
        req = self._req()
        self.assertTrue(self._perm(action='paie_run').has_permission(req, None))

    # ── Action sensible ────────────────────────────────────────────────────
    def test_listed_action_denied_without_session(self):
        self._profile(['paie_run'])
        req = self._req()  # aucun cookie refresh → aucune session résolue
        self.assertFalse(self._perm().has_permission(req, None))

    def test_fresh_mfa_session_passes(self):
        self._profile(['paie_run'])
        raw = self._session(mfa_ago_minutes=1)
        req = self._req(refresh_raw=raw)
        self.assertTrue(self._perm(minutes=5).has_permission(req, None))

    def test_stale_mfa_session_denied(self):
        self._profile(['paie_run'])
        raw = self._session(mfa_ago_minutes=30)
        req = self._req(refresh_raw=raw)
        self.assertFalse(self._perm(minutes=5).has_permission(req, None))

    def test_session_without_mfa_denied(self):
        self._profile(['paie_run'])
        raw = self._session(mfa_ago_minutes=None)  # last_mfa_at NULL
        req = self._req(refresh_raw=raw)
        self.assertFalse(self._perm().has_permission(req, None))

    # ── Sécurité : default-deny ────────────────────────────────────────────
    def test_unauthenticated_denied(self):
        self._profile(['paie_run'])
        req = self._req(user=AnonymousUser())
        self.assertFalse(self._perm().has_permission(req, None))
