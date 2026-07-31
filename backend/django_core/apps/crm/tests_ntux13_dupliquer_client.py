"""NTUX13 — Duplication d'une fiche Client (POST clients/<id>/dupliquer/).

Le duplicata ajoute le suffixe « (copie) » au nom et VIDE les identifiants
uniques (email/ICE) pour forcer une saisie explicite (jamais un doublon
silencieux sur la contrainte (company, email) ou un ICE recopié).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.crm.services import dupliquer_client

User = get_user_model()


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestDupliquerClient(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='ntux13-client-co', defaults={'nom': 'NTUX13 Client Co'})[0]
        self.user = User.objects.create_user(
            username='ntux13_client_u', password='x', role_legacy='responsable',
            company=self.co)
        self.source = Client.objects.create(
            company=self.co, nom='Acme', prenom='Sarl',
            email='acme@example.com', telephone='0600000000',
            type_client=Client.TypeClient.ENTREPRISE, ice='001234567000012',
            adresse='Casablanca')

    def test_service_clears_unique_identifiers(self):
        copie = dupliquer_client(self.source, user=self.user)
        self.assertNotEqual(copie.pk, self.source.pk)
        self.assertEqual(copie.nom, 'Acme (copie)')
        self.assertIsNone(copie.email)
        self.assertIsNone(copie.ice)
        self.assertEqual(copie.telephone, self.source.telephone)
        self.assertEqual(copie.adresse, self.source.adresse)
        self.assertEqual(copie.type_client, self.source.type_client)
        # La source n'est jamais modifiée.
        self.source.refresh_from_db()
        self.assertEqual(self.source.nom, 'Acme')
        self.assertEqual(self.source.email, 'acme@example.com')

    def test_endpoint_dupliquer(self):
        api = _auth(self.user)
        resp = api.post(f'/api/django/crm/clients/{self.source.pk}/dupliquer/')
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertEqual(data['nom'], 'Acme (copie)')
        self.assertIsNone(data.get('email'))
        self.assertIsNone(data.get('ice'))
