"""NTCRD1 — squelette app ``apps.credit`` monté (aucun modèle pour l'instant).

Critère d'acceptation : ``python manage.py check`` passe, l'endpoint racine
répond 200/404 propre (ici : ``/api/django/credit/ping/`` → 200).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


def make_company(slug='ntcrd1-co', nom='NTCRD1 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTCRD1ScaffoldTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ntcrd1_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def test_ping_returns_200(self):
        r = self.api.get('/api/django/credit/ping/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['app'], 'credit')

    def test_unauthenticated_ping_is_401(self):
        r = APIClient().get('/api/django/credit/ping/')
        self.assertEqual(r.status_code, 401)

    def test_unknown_credit_route_is_clean_404(self):
        r = self.api.get('/api/django/credit/route-inexistante/')
        self.assertEqual(r.status_code, 404)
