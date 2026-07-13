"""YAPIC9 — pilote `core.idempotency.IdempotentCreateMixin` sur
`DevisViewSet.create`.

  * rejouer un POST « créer devis » avec la même `Idempotency-Key` renvoie
    le devis initial SANS en créer un second ;
  * la MÊME clé avec un corps DIFFÉRENT -> 409 ;
  * sans en-tête, création normale (comportement inchangé, testé ailleurs
    dans ce dossier — ex. test_fg52_devise.py) ;
  * isolation tenant : la même clé pour DEUX sociétés ne se gêne jamais.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis

User = get_user_model()


def _make_company(slug):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return co


def _make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', role_legacy='admin', company=company)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Yapic9DevisIdempotencyTests(TestCase):

    def setUp(self):
        self.company = _make_company('yapic9-co')
        self.user = _make_user(self.company, 'yapic9_user')
        self.api = _auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YAPIC9',
            telephone='+212600000099')

    def _payload(self, **extra):
        payload = {'client': self.client_obj.id, 'taux_tva': '20.00'}
        payload.update(extra)
        return payload

    def test_same_idempotency_key_replayed_creates_no_second_devis(self):
        headers = {'HTTP_IDEMPOTENCY_KEY': 'yapic9-key-1'}
        first = self.api.post(
            '/api/django/ventes/devis/', self._payload(), format='json',
            **headers)
        self.assertIn(first.status_code, (200, 201), first.content)
        first_id = first.json()['id']

        second = self.api.post(
            '/api/django/ventes/devis/', self._payload(), format='json',
            **headers)
        self.assertEqual(second.status_code, first.status_code)
        self.assertEqual(second.json()['id'], first_id)
        self.assertEqual(Devis.objects.filter(company=self.company).count(), 1)

    def test_same_key_different_body_returns_409(self):
        headers = {'HTTP_IDEMPOTENCY_KEY': 'yapic9-key-2'}
        first = self.api.post(
            '/api/django/ventes/devis/', self._payload(), format='json',
            **headers)
        self.assertIn(first.status_code, (200, 201), first.content)

        second = self.api.post(
            '/api/django/ventes/devis/',
            self._payload(taux_tva='0.00'), format='json', **headers)
        self.assertEqual(second.status_code, 409)

    def test_without_header_creates_normally_each_time(self):
        first = self.api.post(
            '/api/django/ventes/devis/', self._payload(), format='json')
        second = self.api.post(
            '/api/django/ventes/devis/', self._payload(), format='json')
        self.assertIn(first.status_code, (200, 201), first.content)
        self.assertIn(second.status_code, (200, 201), second.content)
        self.assertNotEqual(first.json()['id'], second.json()['id'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(), 2)

    def test_cross_company_isolation_on_same_key(self):
        other_company = _make_company('yapic9-co-2')
        other_user = _make_user(other_company, 'yapic9_user_2')
        other_client = Client.objects.create(
            company=other_company, nom='Autre', prenom='Client',
            telephone='+212600000098')
        other_api = _auth(other_user)

        headers = {'HTTP_IDEMPOTENCY_KEY': 'shared-key-cross-co'}
        first = self.api.post(
            '/api/django/ventes/devis/', self._payload(), format='json',
            **headers)
        self.assertIn(first.status_code, (200, 201), first.content)

        second = other_api.post(
            '/api/django/ventes/devis/',
            {'client': other_client.id, 'taux_tva': '20.00'}, format='json',
            **headers)
        self.assertIn(second.status_code, (200, 201), second.content)
        self.assertNotEqual(first.json()['id'], second.json()['id'])
