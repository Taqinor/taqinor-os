"""Tests du webhook idée-création (NTIDE51, gated).

Couvre : ``services.post_webhook_idee_creation`` — NO-OP si
``INNOVATION_WEBHOOK_URL`` est vide (défaut), POST vers l'URL configurée
sinon (payload titre/description/auteur/contexte + timestamp), jamais
d'exception remontée (défensif) même sur une erreur réseau, et la création
d'idée via l'API ne bloque jamais dessus."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import services
from apps.innovation.models import Idee

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


class WebhookServiceTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide51-a', 'A')
        self.user = make_user(self.co_a, 'ntide51-user')
        self.idee = Idee.objects.create(
            company=self.co_a, titre='Une idée', description='Détail',
            contexte='SAV', auteur=self.user)

    @patch.dict('os.environ', {}, clear=True)
    def test_noop_when_url_empty(self):
        with patch('requests.post') as mock_post:
            result = services.post_webhook_idee_creation(self.idee)
        self.assertFalse(result)
        mock_post.assert_not_called()

    @patch.dict('os.environ', {'INNOVATION_WEBHOOK_URL': 'https://example.com/hook'})
    def test_posts_payload_when_url_configured(self):
        with patch('requests.post') as mock_post:
            result = services.post_webhook_idee_creation(self.idee)
        self.assertTrue(result)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'https://example.com/hook')
        payload = kwargs['json']
        self.assertEqual(payload['titre'], 'Une idée')
        self.assertEqual(payload['description'], 'Détail')
        self.assertEqual(payload['auteur'], self.user.username)
        self.assertEqual(payload['context'], 'SAV')
        self.assertIn('timestamp', payload)

    @patch.dict('os.environ', {'INNOVATION_WEBHOOK_URL': 'https://example.com/hook'})
    def test_never_raises_on_network_error(self):
        with patch('requests.post', side_effect=Exception('boom')):
            result = services.post_webhook_idee_creation(self.idee)
        self.assertFalse(result)


class WebhookOnCreateEndpointTests(TestCase):
    BASE = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-ntide51-ep-a', 'A')
        self.user = make_user(self.co_a, 'ntide51-ep-user')

    @patch.dict('os.environ', {}, clear=True)
    def test_creation_does_not_call_webhook_when_unconfigured(self):
        with patch('requests.post') as mock_post:
            resp = auth(self.user).post(
                self.BASE, {'titre': 'Nouvelle idée'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        mock_post.assert_not_called()

    @patch.dict('os.environ', {'INNOVATION_WEBHOOK_URL': 'https://example.com/hook'})
    def test_creation_calls_webhook_when_configured(self):
        with patch('requests.post') as mock_post:
            resp = auth(self.user).post(
                self.BASE, {'titre': 'Nouvelle idée'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        mock_post.assert_called_once()

    @patch.dict('os.environ', {'INNOVATION_WEBHOOK_URL': 'https://example.com/hook'})
    def test_creation_succeeds_even_if_webhook_fails(self):
        with patch('requests.post', side_effect=Exception('boom')):
            resp = auth(self.user).post(
                self.BASE, {'titre': 'Idée résiliente'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(Idee.objects.filter(titre='Idée résiliente').exists())
