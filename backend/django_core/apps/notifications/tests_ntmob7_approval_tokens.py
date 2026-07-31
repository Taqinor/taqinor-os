"""NTMOB7 — jetons signés d'approbation en un geste (round-trip + payload push)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from freezegun import freeze_time

from authentication.models import Company

from .approval_tokens import make_approval_token, read_approval_token
from .models import EventType, PushSubscription
from .services import notify

User = get_user_model()


def _make_company(name='ApprovalTok Co'):
    return Company.objects.create(nom=name)


def _make_user(company, username='alice'):
    return User.objects.create_user(
        username=username, password='pw', company=company)


class ApprovalTokenRoundTripTests(TestCase):
    def test_round_trip(self):
        token = make_approval_token(7, 'automation', 42, 'approuver')
        data = read_approval_token(token)
        self.assertEqual(
            data, {'u': 7, 's': 'automation', 'i': '42', 'd': 'approuver'})

    def test_tampered_token_rejected(self):
        token = make_approval_token(7, 'automation', 42, 'approuver')
        self.assertIsNone(read_approval_token(token + 'x'))

    def test_garbage_token_rejected(self):
        self.assertIsNone(read_approval_token('not-a-real-token'))

    def test_empty_or_none_token_rejected(self):
        self.assertIsNone(read_approval_token(''))
        self.assertIsNone(read_approval_token(None))

    def test_invalid_decision_rejected_at_creation(self):
        with self.assertRaises(ValueError):
            make_approval_token(7, 'automation', 42, 'peut-etre')

    def test_two_tokens_for_same_item_carry_opposite_decisions(self):
        approve = make_approval_token(7, 'contrats', 3, 'approuver')
        reject = make_approval_token(7, 'contrats', 3, 'refuser')
        self.assertNotEqual(approve, reject)
        self.assertEqual(read_approval_token(approve)['d'], 'approuver')
        self.assertEqual(read_approval_token(reject)['d'], 'refuser')

    def test_expired_token_rejected(self):
        with freeze_time('2026-01-01 00:00:00'):
            token = make_approval_token(7, 'automation', 42, 'approuver')
        # +25h : au-delà des 24h « court-vécu » (MAX_AGE_SECONDS).
        with freeze_time('2026-01-02 01:00:00'):
            self.assertIsNone(read_approval_token(token))

    def test_token_still_valid_within_window(self):
        with freeze_time('2026-01-01 00:00:00'):
            token = make_approval_token(7, 'automation', 42, 'approuver')
        with freeze_time('2026-01-01 12:00:00'):
            self.assertIsNotNone(read_approval_token(token))


class DispatchWebpushApprovalPayloadTests(TestCase):
    """NTMOB7 — `_dispatch_webpush` embarque les actions + jetons quand
    `approval_action` est fourni, sans jamais bloquer l'envoi si ça échoue."""

    def setUp(self):
        self.company = _make_company()
        self.user = _make_user(self.company)
        PushSubscription.objects.create(
            company=self.company, user=self.user,
            endpoint='https://push.example/ntmob7', p256dh='p', auth='a')

    @override_settings(
        VAPID_PUBLIC_KEY='pub', VAPID_PRIVATE_KEY='priv',
        VAPID_ADMIN_EMAIL='admin@x.com')
    def test_notify_with_approval_action_embeds_actions_and_tokens(self):
        import json as json_module
        captured = {}

        def fake_webpush(subscription_info, data, vapid_private_key, vapid_claims):
            captured['data'] = json_module.loads(data)

        with mock.patch('pywebpush.webpush', side_effect=fake_webpush):
            notify(
                self.user, EventType.LEAD_ASSIGNED, 'Étape de contrat',
                approval_action={'source': 'contrats', 'id': 9},
            )
        self.assertIn('actions', captured['data'])
        action_keys = {a['action'] for a in captured['data']['actions']}
        self.assertEqual(action_keys, {'approve', 'reject'})
        self.assertIn('approval', captured['data'])
        self.assertTrue(captured['data']['approval']['approveToken'])
        self.assertTrue(captured['data']['approval']['rejectToken'])
        # Les deux jetons décodent vers la MÊME source/id, décisions opposées.
        approve_data = read_approval_token(
            captured['data']['approval']['approveToken'])
        reject_data = read_approval_token(
            captured['data']['approval']['rejectToken'])
        self.assertEqual(approve_data['s'], 'contrats')
        self.assertEqual(approve_data['i'], '9')
        self.assertEqual(approve_data['d'], 'approuver')
        self.assertEqual(reject_data['d'], 'refuser')

    @override_settings(
        VAPID_PUBLIC_KEY='pub', VAPID_PRIVATE_KEY='priv',
        VAPID_ADMIN_EMAIL='admin@x.com')
    def test_notify_without_approval_action_has_no_actions_key(self):
        import json as json_module
        captured = {}

        def fake_webpush(subscription_info, data, vapid_private_key, vapid_claims):
            captured['data'] = json_module.loads(data)

        with mock.patch('pywebpush.webpush', side_effect=fake_webpush):
            notify(self.user, EventType.LEAD_ASSIGNED, 'Lead assigné')
        self.assertNotIn('actions', captured['data'])
        self.assertNotIn('approval', captured['data'])

    @override_settings(
        VAPID_PUBLIC_KEY='pub', VAPID_PRIVATE_KEY='priv',
        VAPID_ADMIN_EMAIL='admin@x.com')
    def test_approval_token_failure_never_blocks_notify(self):
        # Un échec de fabrication du jeton (mock défensif) ne doit JAMAIS
        # empêcher la notification in-app/push de partir.
        with mock.patch(
                'apps.notifications.approval_tokens.make_approval_token',
                side_effect=RuntimeError('boom')):
            n = notify(
                self.user, EventType.LEAD_ASSIGNED, 'Étape de contrat',
                approval_action={'source': 'contrats', 'id': 9},
            )
        self.assertIsNotNone(n)
