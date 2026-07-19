"""PUB20 — Mort du token = alerte, jamais le silence.

Prouve qu'un ``MetaAuthError`` (code 190 Meta) survenu pendant une synchro :
  - n'est plus AVALÉ silencieusement (le beat continue mais laisse une trace) ;
  - pose l'état « token mort » sur la ``MetaConnection`` (bandeau front) ;
  - émet une ``EngineAlert`` ``token_invalide`` CRITIQUE, dédupliquée par
    connexion (pas de spam à chaque beat) ;
  - est levé dès qu'une synchro réussit à nouveau ;
  - est exposé au client via le serializer (lecture seule, pour le bandeau).
"""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.meta_client import MetaAuthError
from apps.adsengine.models import EngineAlert, MetaConnection
from apps.adsengine.tasks import sync_insights_daily

User = get_user_model()


class _AuthFailClient:
    """Client Meta mocké : lève un ``MetaAuthError`` (190) dès la 1re lecture."""

    def get_account(self, **kw):
        return {'currency': 'USD'}

    def get_campaigns(self, **kw):
        raise MetaAuthError('Token Meta expiré ou invalide', code=190)


class _OkClient:
    def get_account(self, **kw):
        return {'currency': 'USD'}

    def get_campaigns(self, **kw):
        return [{'id': 'c1', 'name': 'C', 'status': 'PAUSED',
                 'objective': 'OUTCOME_LEADS'}]

    def get_adsets(self, **kw):
        return []

    def get_ads(self, **kw):
        return []

    def get_insights(self, meta_id, **kw):
        return []


class TokenDeathAlertingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Tok Co', slug='tok-co')
        self.conn = MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'tok-73951'}, ad_account_id='act_1')

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_auth_error_raises_alert_and_marks_connection(self, mock_cls):
        mock_cls.from_connection.return_value = _AuthFailClient()
        # Le beat NE plante PAS (isolation par société), mais ne synchronise rien.
        result = sync_insights_daily()
        self.assertEqual(result, {'companies_synced': 0})

        alerts = EngineAlert.objects.filter(
            company=self.company, alert_type='token_invalide')
        self.assertEqual(alerts.count(), 1)
        alert = alerts.first()
        self.assertEqual(alert.severity, EngineAlert.Severity.CRITIQUE)
        self.assertEqual(alert.entity_key, f'connection:{self.conn.pk}')

        self.conn.refresh_from_db()
        self.assertTrue(self.conn.token_invalid)
        self.assertIsNotNone(self.conn.token_invalid_at)

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_auth_error_is_deduped_across_beats(self, mock_cls):
        mock_cls.from_connection.return_value = _AuthFailClient()
        sync_insights_daily()
        sync_insights_daily()  # token toujours mort
        # Une seule alerte non acquittée (pas de spam).
        self.assertEqual(
            EngineAlert.objects.filter(
                company=self.company, alert_type='token_invalide',
                acknowledged=False).count(),
            1)

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_successful_sync_clears_token_invalid(self, mock_cls):
        # 1er cycle : token mort → état posé.
        mock_cls.from_connection.return_value = _AuthFailClient()
        sync_insights_daily()
        self.conn.refresh_from_db()
        self.assertTrue(self.conn.token_invalid)

        # 2e cycle : le token refonctionne → état levé.
        mock_cls.from_connection.return_value = _OkClient()
        sync_insights_daily()
        self.conn.refresh_from_db()
        self.assertFalse(self.conn.token_invalid)
        self.assertIsNone(self.conn.token_invalid_at)


class TokenHealthSerializerTests(TestCase):
    BASE = '/api/django/adsengine/connexions/'

    def setUp(self):
        self.company = Company.objects.create(nom='Ser Co', slug='ser-co')
        role = Role.objects.create(
            company=self.company, nom='r',
            permissions=['adsengine_view', 'adsengine_manage'])
        self.user = User.objects.create_user(
            username='u', password='x', company=self.company,
            role_legacy='normal', role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_token_state_is_readonly_and_exposed(self):
        resp = self.api.post(self.BASE, {
            'enabled': True, 'ad_account_id': 'act_1',
            'credentials': {'access_token': 'x', 'expires_at': 4102444800},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        # État exposé au client (pour le bandeau), token_invalid faux à la création.
        self.assertFalse(resp.data['token_invalid'])
        self.assertIsNotNone(resp.data['token_expires_at'])
        # Le secret ne fuit jamais.
        self.assertNotIn('access_token', json.dumps(resp.data))

    def test_reconnect_clears_prior_token_invalid(self):
        conn = MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'old'}, ad_account_id='act_1',
            token_invalid=True)
        from django.utils import timezone
        conn.token_invalid_at = timezone.now()
        conn.save(update_fields=['token_invalid_at'])
        # Le client ne peut pas écrire token_invalid directement (read-only), mais
        # fournir de nouveaux identifiants doit lever l'état côté serveur.
        resp = self.api.patch(f'{self.BASE}{conn.pk}/', {
            'credentials': {'access_token': 'fresh'},
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        conn.refresh_from_db()
        self.assertFalse(conn.token_invalid)
        self.assertIsNone(conn.token_invalid_at)
