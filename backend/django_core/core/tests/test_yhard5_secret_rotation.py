"""Tests YHARD5 — gouvernance des secrets & suivi de rotation.

Couvre : calcul d'échéance (``secrets_due_for_rotation``), scoping société,
non-exposition de la valeur du secret (jamais dans la sortie), et la garde
admin-only de l'endpoint ``core/secrets/rotation/``.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import integrations as integrations_infra
from core.models import IntegrationConfig
from core.views import secrets_rotation_due

User = get_user_model()


class SecretsDueForRotationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='YHARD5 Co')
        cls.other = Company.objects.create(nom='YHARD5 Autre')

    def test_no_period_never_due(self):
        IntegrationConfig.objects.create(
            company=self.company, integration_type='sms', provider='infobip',
            secret_ref='SMS_API_KEY')
        due = integrations_infra.secrets_due_for_rotation(self.company)
        self.assertEqual(due, [])

    def test_never_rotated_with_period_is_due(self):
        IntegrationConfig.objects.create(
            company=self.company, integration_type='esign', provider='yousign',
            secret_ref='YOUSIGN_API_KEY', rotation_period_days=90)
        due = integrations_infra.secrets_due_for_rotation(self.company)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]['provider'], 'yousign')

    def test_rotated_recently_not_due(self):
        IntegrationConfig.objects.create(
            company=self.company, integration_type='sms', provider='infobip',
            secret_ref='SMS_API_KEY', rotation_period_days=90,
            secret_last_rotated_at=timezone.now())
        due = integrations_infra.secrets_due_for_rotation(self.company)
        self.assertEqual(due, [])

    def test_rotated_long_ago_is_due(self):
        IntegrationConfig.objects.create(
            company=self.company, integration_type='sms', provider='infobip',
            secret_ref='SMS_API_KEY', rotation_period_days=30,
            secret_last_rotated_at=timezone.now() - timedelta(days=100))
        due = integrations_infra.secrets_due_for_rotation(self.company)
        self.assertEqual(len(due), 1)

    def test_never_exposes_secret_value(self):
        IntegrationConfig.objects.create(
            company=self.company, integration_type='sms', provider='infobip',
            secret_ref='SMS_API_KEY', rotation_period_days=30)
        due = integrations_infra.secrets_due_for_rotation(self.company)
        serialized_keys = set(due[0].keys())
        self.assertNotIn('secret', serialized_keys)
        self.assertNotIn('secret_value', serialized_keys)
        self.assertIn('secret_ref', serialized_keys)

    def test_scoped_by_company(self):
        IntegrationConfig.objects.create(
            company=self.other, integration_type='sms', provider='infobip',
            secret_ref='SMS_API_KEY', rotation_period_days=30)
        due = integrations_infra.secrets_due_for_rotation(self.company)
        self.assertEqual(due, [])


class SecretsRotationEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='YHARD5 EP Co')
        cls.admin = User.objects.create_user(
            username='yhard5_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.plain = User.objects.create_user(
            username='yhard5_plain', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()
        IntegrationConfig.objects.create(
            company=cls.company, integration_type='esign', provider='yousign',
            secret_ref='YOUSIGN_API_KEY', rotation_period_days=30)

    def _get(self, user):
        req = self.factory.get('/secrets/rotation/')
        force_authenticate(req, user=user)
        return secrets_rotation_due(req)

    def test_admin_sees_due_secrets(self):
        resp = self._get(self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        result = resp.data['results'][0]
        self.assertEqual(result['provider'], 'yousign')
        self.assertEqual(result['secret_ref'], 'YOUSIGN_API_KEY')
        self.assertNotIn('secret_value', result)

    def test_non_admin_forbidden(self):
        resp = self._get(self.plain)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
