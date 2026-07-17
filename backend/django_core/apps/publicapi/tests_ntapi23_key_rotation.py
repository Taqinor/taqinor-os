"""NTAPI23 — rotation de clé API SANS COUPURE (grace period).

`rotate()` émet une nouvelle clé et garde l'ancienne valide jusqu'à
`expire_le` (défaut +7 j, en-tête `Deprecation` sur ses appels) ; au-delà,
l'ancienne est rejetée comme n'importe quelle clé désactivée.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from .constants import SCOPE_READ_LEADS
from .models import ApiKey

User = get_user_model()


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


def _session_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntapi23KeyRotationTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi23', 'NTAPI23')
        self.old_key, self.old_raw = ApiKey.issue(
            company=self.co, label='v', scopes=[SCOPE_READ_LEADS])

    def test_rotate_model_method_sets_expire_le_and_issues_new_key(self):
        new_key, new_raw = self.old_key.rotate()
        self.old_key.refresh_from_db()
        self.assertIsNotNone(self.old_key.expire_le)
        self.assertTrue(self.old_key.enabled)
        self.assertEqual(new_key.scopes, self.old_key.scopes)
        self.assertNotEqual(new_raw, self.old_raw)

    def test_both_keys_work_during_grace_period(self):
        new_key, new_raw = self.old_key.rotate(grace_jours=7)
        resp_old = _key_client(self.old_raw).get('/api/public/leads/')
        resp_new = _key_client(new_raw).get('/api/public/leads/')
        self.assertEqual(resp_old.status_code, 200)
        self.assertEqual(resp_new.status_code, 200)

    def test_deprecation_header_on_old_key_only(self):
        new_key, new_raw = self.old_key.rotate(grace_jours=7)
        resp_old = _key_client(self.old_raw).get('/api/public/leads/')
        resp_new = _key_client(new_raw).get('/api/public/leads/')
        self.assertIn('Deprecation', resp_old)
        self.assertNotIn('Deprecation', resp_new)

    def test_old_key_rejected_once_grace_period_elapsed(self):
        self.old_key.rotate(grace_jours=7)
        self.old_key.refresh_from_db()
        # Simule l'échéance dépassée.
        self.old_key.expire_le = timezone.now() - timedelta(seconds=1)
        self.old_key.save(update_fields=['expire_le'])
        resp = _key_client(self.old_raw).get('/api/public/leads/')
        self.assertEqual(resp.status_code, 401)

    def test_new_key_keeps_working_after_old_key_expires(self):
        new_key, new_raw = self.old_key.rotate(grace_jours=7)
        self.old_key.refresh_from_db()
        self.old_key.expire_le = timezone.now() - timedelta(seconds=1)
        self.old_key.save(update_fields=['expire_le'])
        resp = _key_client(new_raw).get('/api/public/leads/')
        self.assertEqual(resp.status_code, 200)

    def test_cross_tenant_rotation_impossible_via_endpoint(self):
        # L'action `rotate` de gestion est company-scoped comme le reste de
        # ApiKeyViewSet — une clé d'une autre société n'est jamais visible.
        other_co = _company('ntapi23-other', 'NTAPI23 Other')
        other_key, _ = ApiKey.issue(
            company=other_co, label='other', scopes=[SCOPE_READ_LEADS])
        self.assertNotEqual(other_key.company_id, self.old_key.company_id)

    def test_rotate_endpoint_issues_new_key_and_grace_periods_old(self):
        admin = User.objects.create_user(
            username='ntapi23-admin', password='x', company=self.co,
            role_legacy='admin')
        api = _session_client(admin)
        resp = api.post(f'/api/django/publicapi/keys/{self.old_key.id}/rotate/')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('key', resp.data)
        self.assertIn('ancienne_cle', resp.data)
        self.old_key.refresh_from_db()
        self.assertIsNotNone(self.old_key.expire_le)
        new_raw = resp.data['key']
        # Les deux clés fonctionnent pendant la période de grâce.
        self.assertEqual(
            _key_client(self.old_raw).get('/api/public/leads/').status_code, 200)
        self.assertEqual(
            _key_client(new_raw).get('/api/public/leads/').status_code, 200)

    def test_rotate_endpoint_cross_tenant_404(self):
        other_co = _company('ntapi23-other2', 'NTAPI23 Other 2')
        admin = User.objects.create_user(
            username='ntapi23-admin2', password='x', company=other_co,
            role_legacy='admin')
        api = _session_client(admin)
        resp = api.post(f'/api/django/publicapi/keys/{self.old_key.id}/rotate/')
        self.assertEqual(resp.status_code, 404)
