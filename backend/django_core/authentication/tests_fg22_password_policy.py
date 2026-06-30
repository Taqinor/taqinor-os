"""FG22 — politique de mot de passe & verrouillage de compte (par société).

Inerte par défaut (rien ne change) ; durcie via le CompanyProfile, elle
s'applique au changement de mot de passe et au verrouillage après N échecs."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from authentication import password_policy as pp
from apps.parametres.models import CompanyProfile

User = get_user_model()


def _company(slug='fg22-co', nom='FG22 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class FG22PolicyHelperTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.profile = CompanyProfile.objects.create(company=self.company)

    def test_default_policy_is_inert(self):
        # Défauts (min 8, pas de complexité) → aucune erreur supplémentaire.
        self.assertEqual(pp.validate_password_policy('abcdefgh', self.company),
                         [])

    def test_min_length_enforced(self):
        self.profile.password_min_length = 12
        self.profile.save()
        errs = pp.validate_password_policy('short', self.company)
        self.assertTrue(errs)

    def test_complexity_enforced(self):
        self.profile.password_require_complexity = True
        self.profile.save()
        self.assertTrue(pp.validate_password_policy('alllower', self.company))
        self.assertEqual(
            pp.validate_password_policy('Abcdef1!', self.company), [])

    def test_no_profile_is_inert(self):
        other = _company(slug='fg22-noprofile', nom='No Profile')
        self.assertEqual(pp.validate_password_policy('x', other), [])


class FG22LockoutTest(TestCase):
    def setUp(self):
        self.company = _company(slug='fg22-lock', nom='FG22 Lock')
        self.profile = CompanyProfile.objects.create(
            company=self.company, lockout_max_attempts=3,
            lockout_duration_minutes=15)
        self.user = User.objects.create_user(
            username='fg22_user', password='goodpass', company=self.company)

    def test_lockout_after_n_failures(self):
        # 3 échecs consécutifs → verrouillé.
        for _ in range(3):
            pp.register_failed_login(self.user)
        self.user.refresh_from_db()
        self.assertTrue(pp.is_locked(self.user))

    def test_lockout_disabled_by_default(self):
        other = _company(slug='fg22-nolock', nom='No Lock')
        CompanyProfile.objects.create(company=other)
        u = User.objects.create_user(
            username='nolock', password='pw', company=other)
        for _ in range(10):
            pp.register_failed_login(u)
        u.refresh_from_db()
        self.assertFalse(pp.is_locked(u))

    def test_reset_clears_lock(self):
        self.user.failed_login_count = 2
        self.user.locked_until = timezone.now() + timezone.timedelta(minutes=5)
        self.user.save()
        pp.reset_failed_login(self.user)
        self.user.refresh_from_db()
        self.assertFalse(pp.is_locked(self.user))
        self.assertEqual(self.user.failed_login_count, 0)


class FG22ChangePasswordTest(TestCase):
    def setUp(self):
        self.company = _company(slug='fg22-chg', nom='FG22 Chg')
        self.profile = CompanyProfile.objects.create(
            company=self.company, password_min_length=12)
        self.user = User.objects.create_user(
            username='fg22_chg', password='currentpass', company=self.company)
        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_change_password_rejects_short_under_policy(self):
        r = self.api.post('/api/django/auth/change-password/', {
            'current_password': 'currentpass', 'new_password': 'Short1!a',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_change_password_accepts_compliant(self):
        r = self.api.post('/api/django/auth/change-password/', {
            'current_password': 'currentpass',
            'new_password': 'LongEnoughPwd99',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content)
