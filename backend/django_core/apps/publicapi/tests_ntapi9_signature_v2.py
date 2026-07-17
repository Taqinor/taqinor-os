"""NTAPI9 — signature webhook horodatée anti-rejeu façon Stripe
(``X-Taqinor-Signature-V2: t=<epoch>,v1=<hex>``), EN PLUS du format legacy.

Couvre : présence des DEUX en-têtes sur chaque livraison, le `v1` du V2 est
identique au HMAC legacy, la vérification V2 rejette un `t` hors tolérance
(anti-rejeu) et accepte un `t` dans la fenêtre, et le format legacy reste
vérifiable À L'IDENTIQUE (non-régression, cf. `tests_yapic8_delivery.py`).
"""
import hashlib
import hmac
import json
from unittest import mock

from django.test import TestCase

from authentication.models import Company

from . import delivery
from .constants import EVENT_LEAD_CREATED
from .models import Webhook


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


class Ntapi9SignatureV2Tests(TestCase):
    def setUp(self):
        self.co = _company('ntapi9', 'NTAPI9')
        self.hook = Webhook.objects.create(
            company=self.co, target_url='https://example.test/hook',
            secret='s3cr3t', events=[EVENT_LEAD_CREATED], enabled=True)
        p = mock.patch(
            'apps.publicapi.delivery.validate_webhook_target_url',
            side_effect=lambda u: u)
        p.start()
        self.addCleanup(p.stop)

    def _capture_post(self, status_code=200):
        captured = {}

        def fake_post(url, content=None, headers=None, timeout=None):
            captured['headers'] = headers
            captured['content'] = content
            return mock.Mock(status_code=status_code)

        return captured, fake_post

    def test_both_signature_headers_present_and_legacy_unchanged(self):
        captured, fake_post = self._capture_post(200)
        with mock.patch.object(delivery.httpx, 'post', side_effect=fake_post):
            delivery._deliver_one(self.hook, EVENT_LEAD_CREATED, {'id': 1})
        headers = captured['headers']
        self.assertIn(delivery.SIGNATURE_HEADER, headers)
        self.assertIn(delivery.SIGNATURE_HEADER_V2, headers)
        ts = headers[delivery.TIMESTAMP_HEADER]
        body = captured['content']
        legacy_expected = hmac.new(
            b's3cr3t', f'{ts}.'.encode('utf-8') + body, hashlib.sha256
        ).hexdigest()
        self.assertEqual(headers[delivery.SIGNATURE_HEADER], legacy_expected)

    def test_v2_header_format_and_hex_matches_legacy(self):
        captured, fake_post = self._capture_post(200)
        with mock.patch.object(delivery.httpx, 'post', side_effect=fake_post):
            delivery._deliver_one(self.hook, EVENT_LEAD_CREATED, {'id': 1})
        headers = captured['headers']
        v2 = headers[delivery.SIGNATURE_HEADER_V2]
        self.assertRegex(v2, r'^t=\d+,v1=[0-9a-f]{64}$')
        t_part, v1_part = v2.split(',')
        self.assertEqual(f't={headers[delivery.TIMESTAMP_HEADER]}', t_part)
        self.assertEqual(f'v1={headers[delivery.SIGNATURE_HEADER]}', v1_part)

    def test_verify_signature_v2_accepts_within_tolerance(self):
        body = json.dumps({'id': 1}, sort_keys=True).encode('utf-8')
        header = delivery.build_signature_v2('s3cr3t', body, '1000')
        self.assertTrue(
            delivery.verify_signature_v2(
                's3cr3t', body, header, tolerance_seconds=300, now=1200))

    def test_verify_signature_v2_rejects_replay_outside_tolerance(self):
        body = json.dumps({'id': 1}, sort_keys=True).encode('utf-8')
        header = delivery.build_signature_v2('s3cr3t', body, '1000')
        # 301 s plus tard : hors fenêtre de tolérance (défaut 300 s) — rejeu
        # rejetable côté client, comme documenté.
        self.assertFalse(
            delivery.verify_signature_v2(
                's3cr3t', body, header, tolerance_seconds=300, now=1301))

    def test_verify_signature_v2_rejects_wrong_secret(self):
        body = b'{"id": 1}'
        header = delivery.build_signature_v2('s3cr3t', body, '1000')
        self.assertFalse(
            delivery.verify_signature_v2(
                'wrong-secret', body, header, now=1000))

    def test_verify_signature_v2_rejects_malformed_header(self):
        body = b'{"id": 1}'
        self.assertFalse(
            delivery.verify_signature_v2('s3cr3t', body, 'not-a-valid-header'))
