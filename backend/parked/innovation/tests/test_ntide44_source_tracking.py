"""Tests de la provenance du feedback produit (NTIDE44).

Couvre : ``source_page`` écrit du corps de requête ; ``user_agent`` capturé
CÔTÉ SERVEUR depuis l'en-tête HTTP (jamais lu du corps — un client ne peut
pas le falsifier)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation.models import FeedbackProduit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class SourceTrackingTests(TestCase):
    BASE = '/api/django/innovation/feedback-produit/'

    def setUp(self):
        self.co_a = make_company('innov-ntide44-a', 'A')
        self.normal = make_user(self.co_a, 'ntide44-normal')

    def test_source_page_from_body(self):
        resp = auth(self.normal).post(self.BASE, {
            'titre': 'Lenteur',
            'source_page': '/chantiers/détail',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        fb = FeedbackProduit.objects.get(pk=resp.data['id'])
        self.assertEqual(fb.source_page, '/chantiers/détail')

    def test_user_agent_captured_from_header(self):
        api = auth(self.normal)
        resp = api.post(
            self.BASE, {'titre': 'Bug'}, format='json',
            HTTP_USER_AGENT='Mozilla/5.0 TestAgent/1.0')
        self.assertEqual(resp.status_code, 201, resp.data)
        fb = FeedbackProduit.objects.get(pk=resp.data['id'])
        self.assertEqual(fb.user_agent, 'Mozilla/5.0 TestAgent/1.0')

    def test_user_agent_never_taken_from_body(self):
        resp = auth(self.normal).post(
            self.BASE,
            {'titre': 'Test', 'user_agent': 'FauxAgent/9.9'},
            format='json', HTTP_USER_AGENT='RealAgent/1.0')
        self.assertEqual(resp.status_code, 201, resp.data)
        fb = FeedbackProduit.objects.get(pk=resp.data['id'])
        self.assertEqual(fb.user_agent, 'RealAgent/1.0')

    def test_source_page_optional(self):
        resp = auth(self.normal).post(
            self.BASE, {'titre': 'Sans page source'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        fb = FeedbackProduit.objects.get(pk=resp.data['id'])
        self.assertEqual(fb.source_page, '')
