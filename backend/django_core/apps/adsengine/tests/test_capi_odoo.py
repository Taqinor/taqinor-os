"""ADSDEEP27 — Tests de l'émetteur CAPI « signatures » vers le CRM Dataset Meta.

Prouve : le payload ``signed_contract`` (action_source system_generated, value +
currency MAD, event_source/lead_event_source), le match ``lead_id`` via
``MetaLeadMirror`` sinon ``ph`` SHA-256 du téléphone E.164 (jamais de PII en
clair), le NO-OP propre sans dataset/token, l'émission via un transport injecté,
et l'IDEMPOTENCE persistée (un deal n'est POSTé qu'une fois — rejeu du beat sans
doublon).
"""
import hashlib
import os
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import capi_odoo
from apps.adsengine.models import CapiOdooEvent, MetaLeadMirror

_ENV_ON = {
    'CAPI_CRM_DATASET_ID': 'ds-777',
    'META_CAPI_ACCESS_TOKEN': 'tok-abc',
}


def _deal(**kw):
    d = dict(
        phone_norm='612345678', amount_mad=Decimal('42000'),
        date='2026-07-16 10:00:00', source_name='FORM-TAQINOR',
        origin='sale_order', lead_id=None)
    d.update(kw)
    return d


class BuildSignedEventTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CAPI Odoo', slug='capi-odoo')

    def test_payload_shape_and_value(self):
        ev = capi_odoo.build_signed_event(
            self.company, _deal(), now=1_752_600_000)['event']
        self.assertEqual(ev['event_name'], 'signed_contract')
        self.assertEqual(ev['action_source'], 'system_generated')
        cd = ev['custom_data']
        self.assertEqual(cd['event_source'], 'crm')
        self.assertEqual(cd['lead_event_source'], 'ERP')
        self.assertEqual(cd['currency'], 'MAD')
        self.assertEqual(cd['value'], 42000.0)

    def test_lead_id_match_via_mirror_not_hashed(self):
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='9988',
            phone_key='612345678')
        built = capi_odoo.build_signed_event(self.company, _deal())
        ud = built['event']['user_data']
        # leadgen_id (clé de match préférée) — NON haché, pas de ``ph``.
        self.assertEqual(ud['lead_id'], '9988')
        self.assertNotIn('ph', ud)

    def test_phone_hashed_e164_when_no_mirror(self):
        built = capi_odoo.build_signed_event(
            self.company, _deal(phone_norm='698765432'))
        ud = built['event']['user_data']
        self.assertNotIn('lead_id', ud)
        expected = hashlib.sha256('212698765432'.encode()).hexdigest()
        self.assertEqual(ud['ph'], [expected])
        # jamais de PII en clair dans le hash.
        self.assertNotIn('698765432', ud['ph'][0])

    def test_no_match_key_not_eligible(self):
        built = capi_odoo.build_signed_event(
            self.company, _deal(phone_norm=''))
        self.assertFalse(built['eligible'])
        self.assertEqual(built['reason'], 'no_match_key')

    def test_event_key_stable_per_deal(self):
        a = capi_odoo.build_signed_event(
            self.company, _deal(lead_id=55), now=1)['event_key']
        b = capi_odoo.build_signed_event(
            self.company, _deal(lead_id=55), now=999)['event_key']
        self.assertEqual(a, b)
        self.assertEqual(a, 'odoo_signed:55')

    def test_old_event_time_clamped_to_now(self):
        # deal signé il y a > 7 j → event_time rabattu sur ``now`` (contrainte Meta).
        now = 1_800_000_000
        ev = capi_odoo.build_signed_event(
            self.company, _deal(date='2020-01-01 00:00:00'), now=now)['event']
        self.assertEqual(ev['event_time'], now)


class EmitSignedDealsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Emit Co', slug='emit-odoo')

    def test_no_op_without_config(self):
        sent = []
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('CAPI_CRM_DATASET_ID', None)
            os.environ.pop('META_CAPI_ACCESS_TOKEN', None)
            os.environ.pop('CAPI_CRM_ACCESS_TOKEN', None)
            res = capi_odoo.emit_signed_deals(
                self.company,
                transport=lambda u, p: sent.append((u, p)) or (200, 'ok'))
        self.assertEqual(res['reason'], 'not_configured')
        self.assertEqual(res['emitted'], 0)
        self.assertEqual(sent, [])

    def test_sends_via_transport_to_dataset(self):
        sent = []

        def _transport(url, payload):
            sent.append((url, payload))
            return 200, '{"events_received":1}'

        with mock.patch.dict(os.environ, _ENV_ON), \
                mock.patch.object(
                    capi_odoo, 'odoo_signed_deals', lambda **k: [_deal()]):
            res = capi_odoo.emit_signed_deals(self.company, transport=_transport)
        self.assertEqual(res['emitted'], 1)
        self.assertEqual(len(sent), 1)
        url, payload = sent[0]
        self.assertIn('/ds-777/events', url)
        self.assertIn(b'signed_contract', payload)
        self.assertIn(b'system_generated', payload)

    def test_idempotent_second_run_skips(self):
        calls = []

        def _transport(url, payload):
            calls.append(payload)
            return 200, 'ok'

        with mock.patch.dict(os.environ, _ENV_ON), \
                mock.patch.object(
                    capi_odoo, 'odoo_signed_deals',
                    lambda **k: [_deal(lead_id=7)]):
            first = capi_odoo.emit_signed_deals(
                self.company, transport=_transport)
            second = capi_odoo.emit_signed_deals(
                self.company, transport=_transport)
        self.assertEqual(first['emitted'], 1)
        self.assertEqual(second['emitted'], 0)
        self.assertEqual(second['skipped'], 1)
        # UN seul POST réseau malgré deux passages du beat.
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            CapiOdooEvent.objects.filter(
                company=self.company, event_key='odoo_signed:7').count(), 1)

    def test_http_failure_leaves_no_marker(self):
        def _failing(url, payload):
            raise RuntimeError('boom')

        with mock.patch.dict(os.environ, _ENV_ON), \
                mock.patch.object(
                    capi_odoo, 'odoo_signed_deals',
                    lambda **k: [_deal(lead_id=9)]):
            res = capi_odoo.emit_signed_deals(self.company, transport=_failing)
        self.assertEqual(res['emitted'], 0)
        # pas de marqueur → l'événement repartira au prochain passage.
        self.assertFalse(CapiOdooEvent.objects.filter(
            company=self.company, event_key='odoo_signed:9').exists())


class LeadReceivedTests(TestCase):
    """ADSDEEP28 — événement amont ``lead_received`` par MetaLeadMirror."""

    def setUp(self):
        self.company = Company.objects.create(nom='Recv Co', slug='recv-co')

    def test_build_uses_lead_id_and_hashed_phone(self):
        mirror = MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='L1', phone_key='612345678')
        built = capi_odoo.build_received_event(self.company, mirror, now=1000)
        ev = built['event']
        self.assertEqual(ev['event_name'], 'lead_received')
        self.assertEqual(ev['action_source'], 'system_generated')
        self.assertEqual(ev['user_data']['lead_id'], 'L1')
        expected = hashlib.sha256('212612345678'.encode()).hexdigest()
        self.assertEqual(ev['user_data']['ph'], [expected])
        self.assertEqual(ev['event_id'], 'lead_received:L1')

    def test_emit_idempotent(self):
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='L2', phone_key='')
        calls = []
        with mock.patch.dict(os.environ, _ENV_ON):
            first = capi_odoo.emit_lead_received(
                self.company,
                transport=lambda u, p: calls.append(p) or (200, 'ok'))
            second = capi_odoo.emit_lead_received(
                self.company,
                transport=lambda u, p: calls.append(p) or (200, 'ok'))
        self.assertEqual(first['emitted'], 1)
        self.assertEqual(second['emitted'], 0)
        self.assertEqual(len(calls), 1)

    def test_no_op_without_config(self):
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='L3', phone_key='')
        sent = []
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in ('CAPI_CRM_DATASET_ID', 'META_CAPI_ACCESS_TOKEN',
                      'CAPI_CRM_ACCESS_TOKEN'):
                os.environ.pop(k, None)
            res = capi_odoo.emit_lead_received(
                self.company,
                transport=lambda u, p: sent.append(p) or (200, 'ok'))
        self.assertEqual(res['reason'], 'not_configured')
        self.assertEqual(sent, [])


class TwoStepPerLeadTests(TestCase):
    """ADSDEEP28 — un lead signé porte bien DEUX étapes (Meta exige ≥ 2 par
    lead_id) : ``lead_received`` (amont) + ``signed_contract`` (issue)."""

    def test_signed_lead_gets_received_and_signed(self):
        company = Company.objects.create(nom='2step Co', slug='2step-co')
        MetaLeadMirror.objects.create(
            company=company, leadgen_id='LX', phone_key='612345678')
        posted = []

        def _transport(url, payload):
            posted.append(payload)
            return 200, 'ok'

        with mock.patch.dict(os.environ, _ENV_ON), \
                mock.patch.object(
                    capi_odoo, 'odoo_signed_deals',
                    lambda **k: [_deal(phone_norm='612345678', lead_id=1)]):
            recv = capi_odoo.emit_lead_received(company, transport=_transport)
            sign = capi_odoo.emit_signed_deals(company, transport=_transport)

        self.assertEqual(recv['emitted'], 1)
        self.assertEqual(sign['emitted'], 1)
        # deux marqueurs distincts pour ce lead : réception + signature.
        keys = set(CapiOdooEvent.objects.filter(
            company=company).values_list('event_key', flat=True))
        self.assertEqual(keys, {'lead_received:LX', 'odoo_signed:1'})
        # les DEUX événements portent le MÊME lead_id Meta (LX) — matché via
        # MetaLeadMirror côté signature.
        blob = b''.join(posted)
        self.assertEqual(blob.count(b'"lead_id": "LX"'), 2)
        self.assertIn(b'lead_received', blob)
        self.assertIn(b'signed_contract', blob)
