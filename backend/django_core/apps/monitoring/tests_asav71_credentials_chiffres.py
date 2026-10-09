"""ASAV71 — identifiants des connecteurs chiffrés au repos
(`EncryptedJSONField` sur `core.crypto_fields`, key-gated).

Run :
    python manage.py test apps.monitoring.tests_asav71_credentials_chiffres -v2
"""
from decimal import Decimal

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import MonitoringConfig
from authentication.models import Company

User = get_user_model()
CLE = Fernet.generate_key().decode()
SECRETS = {'username': 'x', 'password': 'SECRET-PW', 'api_token': 'TOK123'}


class CredentialsChiffresTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav71-co', defaults={'nom': 'ASAV71 Co'})
        user = User.objects.create_user(
            username='asav71_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV71')
        inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV71', client=client,
            puissance_installee_kwc=Decimal('5.00'))
        self.config = MonitoringConfig.objects.create(
            company=self.company, installation=inst)

    def _colonne_brute(self):
        with connection.cursor() as c:
            c.execute(
                'SELECT credentials FROM monitoring_monitoringconfig '
                'WHERE id = %s', [self.config.pk])
            return c.fetchone()[0]

    @override_settings(FIELD_ENCRYPTION_KEY=CLE)
    def test_colonne_brute_chiffree(self):
        r = self.api.patch(
            f'/api/django/monitoring/configs/{self.config.pk}/',
            {'credentials': SECRETS}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        brut = str(self._colonne_brute())
        self.assertNotIn('SECRET-PW', brut)
        self.assertNotIn('TOK123', brut)
        self.assertTrue(brut.startswith('enc:'))

    @override_settings(FIELD_ENCRYPTION_KEY=CLE)
    def test_connecteur_relit(self):
        MonitoringConfig.objects.filter(pk=self.config.pk).update(
            credentials=SECRETS)
        config = MonitoringConfig.objects.get(pk=self.config.pk)
        self.assertEqual(config.credentials, SECRETS)
        self.assertTrue(config.credentials['password'])

    @override_settings(FIELD_ENCRYPTION_KEY=CLE)
    def test_reponse_masquee(self):
        self.api.patch(
            f'/api/django/monitoring/configs/{self.config.pk}/',
            {'credentials': SECRETS}, format='json')
        r = self.api.get(
            f'/api/django/monitoring/configs/{self.config.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('credentials', r.data)
        self.assertTrue(r.data['has_credentials'])
        self.assertNotIn('SECRET-PW', str(r.data))

    @override_settings(FIELD_ENCRYPTION_KEY='')
    def test_sans_cle_comportement_key_gated(self):
        """Sans clé configurée : comportement de ``EncryptedTextField`` —
        JSON en clair, aucune exception, l'application relit le même dict."""
        MonitoringConfig.objects.filter(pk=self.config.pk).update(
            credentials=SECRETS)
        self.assertIn('SECRET-PW', str(self._colonne_brute()))
        config = MonitoringConfig.objects.get(pk=self.config.pk)
        self.assertEqual(config.credentials, SECRETS)
