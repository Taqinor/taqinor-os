"""Tests du contexte opaque du feedback produit (NTIDE43).

Couvre : ``FeedbackProduit.context_type``/``context_id`` (vide/None par
défaut, écrit à la création — même patron opaque que
``Idee.linked_type``/``linked_id``, NTIDE14/NTIDE1)."""
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


class FeedbackContextModelTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide43-a', 'A')
        self.user = make_user(self.co_a, 'ntide43-user')

    def test_context_blank_by_default(self):
        fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='Sans contexte')
        self.assertEqual(fb.context_type, '')
        self.assertIsNone(fb.context_id)

    def test_context_accepts_devis(self):
        fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.user, titre='Depuis un devis',
            context_type='devis', context_id=123)
        self.assertEqual(fb.context_type, 'devis')
        self.assertEqual(fb.context_id, 123)


class FeedbackContextCreateEndpointTests(TestCase):
    BASE = '/api/django/innovation/feedback-produit/'

    def setUp(self):
        self.co_a = make_company('innov-ntide43-ep-a', 'A')
        self.normal = make_user(self.co_a, 'ntide43-ep-normal')

    def test_context_writable_at_creation(self):
        resp = auth(self.normal).post(self.BASE, {
            'titre': 'Ouvert depuis le devis #123',
            'context_type': 'devis', 'context_id': 123,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        fb = FeedbackProduit.objects.get(pk=resp.data['id'])
        self.assertEqual(fb.context_type, 'devis')
        self.assertEqual(fb.context_id, 123)

    def test_context_optional(self):
        resp = auth(self.normal).post(self.BASE, {
            'titre': 'Sans contexte particulier',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        fb = FeedbackProduit.objects.get(pk=resp.data['id'])
        self.assertEqual(fb.context_type, '')
        self.assertIsNone(fb.context_id)

    def test_invalid_context_type_rejected(self):
        resp = auth(self.normal).post(self.BASE, {
            'titre': 'Contexte invalide',
            'context_type': 'inconnu',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
