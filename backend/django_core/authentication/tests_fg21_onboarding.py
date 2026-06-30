"""FG21 — onboarding : l'admin peut exiger un changement de mot de passe à la
première connexion, à la création de l'utilisateur (via /users/ et /auth/
register/)."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role, ADMIN_PERMISSIONS

User = get_user_model()


def _company(slug='fg21-co', nom='FG21 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class FG21OnboardingTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
        self.admin = User.objects.create_user(
            username='fg21_admin', password='pw', role_legacy='admin',
            role=self.admin_role, company=self.company)
        self.api = APIClient()
        token = str(AccessToken.for_user(self.admin))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_register_sets_must_change_password(self):
        r = self.api.post('/api/django/register/', {
            'username': 'invited', 'password': 'Sup3rSecret!23',
            'email': 'a@b.c', 'must_change_password': True,
        }, format='json')
        self.assertIn(r.status_code, (200, 201), r.content)
        u = User.objects.get(username='invited')
        self.assertTrue(u.must_change_password)

    def test_register_default_false(self):
        r = self.api.post('/api/django/register/', {
            'username': 'normal_user', 'password': 'Sup3rSecret!23',
        }, format='json')
        self.assertIn(r.status_code, (200, 201), r.content)
        u = User.objects.get(username='normal_user')
        self.assertFalse(u.must_change_password)

    def test_userviewset_create_sets_flag(self):
        r = self.api.post('/api/django/users/', {
            'username': 'viacrud', 'password': 'Sup3rSecret!23',
            'must_change_password': True,
        }, format='json')
        self.assertIn(r.status_code, (200, 201), r.content)
        u = User.objects.get(username='viacrud')
        self.assertTrue(u.must_change_password)
