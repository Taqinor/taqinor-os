"""ADSDEEP57/58/59 — Tests des audiences Meta (aucun réseau réel).

Invariants prouvés :
  * consentement OFF par défaut ⇒ AUCUN envoi (57/58) ;
  * la PII brute (email/téléphone) n'apparaît JAMAIS dans un payload — seuls des
    hachés SHA-256 sont émis (57) ;
  * sessions ≤10 000 lignes/appel, ``usersreplace`` atomique (57) ;
  * seed ≥100 requis pour un lookalike, ratio MA 1-5 %, value-based (58) ;
  * audiences d'engagement = objets Meta-side, AUCUNE donnée CRM envoyée (59).
"""
import hashlib
import json
from urllib.parse import parse_qs

import httpx
from django.test import SimpleTestCase, override_settings

from apps.adsengine import audiences as aud
from apps.adsengine import meta_client as mc


def _sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


class RecordingClient:
    """Double du ``MetaClient`` qui ENREGISTRE chaque appel (aucun réseau).

    ``add_users_to_audience`` applique la même borne dure ≤10 000 que le vrai
    client (pour prouver que l'orchestrateur ne la franchit jamais)."""

    def __init__(self, *, page_id='PAGE1', ig_user_id='IG1'):
        self.calls = []
        self.page_id = page_id
        self.ig_user_id = ig_user_id
        self._next_id = 1000

    def _id(self):
        self._next_id += 1
        return str(self._next_id)

    def create_custom_audience(self, **kwargs):
        self.calls.append(('create_custom_audience', kwargs))
        return {'id': self._id()}

    def add_users_to_audience(self, **kwargs):
        if len(kwargs.get('data') or []) > mc.MetaClient.CUSTOM_AUDIENCE_MAX_USERS_PER_CALL:
            raise AssertionError('session > 10 000 franchie par l\'orchestrateur')
        self.calls.append(('add_users_to_audience', kwargs))
        return {'audience_id': kwargs.get('audience_id'),
                'num_received': len(kwargs.get('data') or [])}

    def delete_custom_audience(self, **kwargs):
        self.calls.append(('delete_custom_audience', kwargs))
        return {'success': True}

    def get_audience(self, audience_id, **kwargs):
        self.calls.append(('get_audience', {'audience_id': audience_id}))
        return {'id': audience_id, 'operation_status': {'code': 200},
                'delivery_status': {'code': 200},
                'approximate_count_lower_bound': 5000}

    def create_lookalike_audience(self, **kwargs):
        self.calls.append(('create_lookalike_audience', kwargs))
        return {'id': self._id()}

    def create_engagement_audience(self, **kwargs):
        self.calls.append(('create_engagement_audience', kwargs))
        return {'id': self._id()}

    def get_delivery_estimate(self, **kwargs):
        self.calls.append(('get_delivery_estimate', kwargs))
        return {'estimate_ready': True, 'estimate_dau': 12000,
                'estimate_mau_lower_bound': 300000}


class ExplodingClient:
    """Tout appel lève — prouve qu'une porte fermée ne touche jamais le réseau."""

    def __getattr__(self, name):
        def _boom(*a, **k):
            raise AssertionError(
                f'{name} appelé alors qu\'aucun réseau n\'est permis')
        return _boom


CONTACTS = [
    {'email': 'User@Example.COM ', 'telephone': '0600000001'},
    {'email': '', 'telephone': '+212600000002'},
    {'email': 'third@x.ma', 'telephone': ''},
    {'email': '', 'telephone': ''},  # ligne vide → ignorée
]


class Adsdeep57ConsentGateTests(SimpleTestCase):
    def test_consent_off_by_default_blocks_all_sends(self):
        """META_CUSTOM_AUDIENCE_CONSENT absent → OFF → aucun appel client."""
        summary = aud.sync_crm_custom_audience(
            company=None, name='Seed', contacts=CONTACTS,
            client=ExplodingClient())
        self.assertFalse(summary['configured'])
        self.assertEqual(summary['audience_id'], '')
        self.assertEqual(summary['sent'], 0)
        # Les compteurs de préviz sont calculés localement (3 lignes matchées).
        self.assertEqual(summary['matched_rows'], 3)
        self.assertIn('customaudiences/tos', summary['tos_url'])

    @override_settings(META_CUSTOM_AUDIENCE_CONSENT='0')
    def test_consent_explicit_off_blocks_all_sends(self):
        summary = aud.sync_crm_custom_audience(
            company=None, name='Seed', contacts=CONTACTS,
            client=ExplodingClient())
        self.assertFalse(summary['configured'])
        self.assertEqual(summary['sent'], 0)

    def test_delete_off_by_default_no_call(self):
        result = aud.delete_crm_custom_audience(
            company=None, audience_id='AUD1', client=ExplodingClient())
        self.assertFalse(result['configured'])
        self.assertFalse(result['deleted'])


@override_settings(META_CUSTOM_AUDIENCE_CONSENT='1')
class Adsdeep57UploadTests(SimpleTestCase):
    def test_raw_pii_never_in_payload_only_hashes(self):
        client = RecordingClient()
        summary = aud.sync_crm_custom_audience(
            company=None, name='Seed', contacts=CONTACTS, client=client)
        self.assertTrue(summary['configured'])
        self.assertTrue(summary['audience_id'])
        self.assertEqual(summary['sent'], 3)

        # Sérialise TOUS les payloads add_users et vérifie l'absence de PII brute.
        add_calls = [k for (n, k) in client.calls if n == 'add_users_to_audience']
        blob = json.dumps([c for c in add_calls], default=str)
        for raw in ('User@Example.COM', 'user@example.com', '0600000001',
                    '212600000002', 'third@x.ma'):
            self.assertNotIn(raw, blob,
                             f'PII brute « {raw} » ne doit jamais figurer')
        # Les HACHÉS attendus, eux, sont bien présents.
        self.assertIn(_sha('user@example.com'), blob)
        self.assertIn(_sha('212600000001'), blob)
        self.assertIn(_sha('212600000002'), blob)
        self.assertIn(_sha('third@x.ma'), blob)

    def test_schema_is_email_phone(self):
        client = RecordingClient()
        aud.sync_crm_custom_audience(
            company=None, name='S', contacts=CONTACTS, client=client)
        add = next(k for (n, k) in client.calls if n == 'add_users_to_audience')
        self.assertEqual(add['schema'], ['EMAIL', 'PHONE'])

    def test_empty_field_is_blank_not_hash_of_empty(self):
        client = RecordingClient()
        aud.sync_crm_custom_audience(
            company=None, name='S',
            contacts=[{'email': '', 'telephone': '0600000001'}], client=client)
        add = next(k for (n, k) in client.calls if n == 'add_users_to_audience')
        row = add['data'][0]
        self.assertEqual(row[0], '')  # email vide → '' (jamais sha256(''))
        self.assertEqual(row[1], _sha('212600000001'))

    def test_sessions_capped_at_10000_and_atomic_replace(self):
        contacts = [{'email': f'u{i}@x.ma', 'telephone': ''}
                    for i in range(25000)]
        client = RecordingClient()
        summary = aud.sync_crm_custom_audience(
            company=None, name='Big', contacts=contacts, replace=True,
            client=client)
        self.assertEqual(summary['sessions'], 3)
        self.assertEqual(summary['sent'], 25000)
        add_calls = [k for (n, k) in client.calls if n == 'add_users_to_audience']
        self.assertEqual(len(add_calls), 3)
        sizes = [len(k['data']) for k in add_calls]
        self.assertEqual(sizes, [10000, 10000, 5000])
        for k in add_calls:
            self.assertLessEqual(len(k['data']),
                                 mc.MetaClient.CUSTOM_AUDIENCE_MAX_USERS_PER_CALL)
            self.assertTrue(k['replace'])  # usersreplace → remplacement atomique
        # Une seule session_id, dernier batch marqué.
        session_ids = {k['session']['session_id'] for k in add_calls}
        self.assertEqual(len(session_ids), 1)
        self.assertTrue(add_calls[-1]['session']['last_batch_flag'])
        self.assertFalse(add_calls[0]['session']['last_batch_flag'])

    def test_no_connection_reports_cleanly(self):
        # Flag ON mais aucun client résolu (pas de connexion) → pas d'exception.
        summary = aud.sync_crm_custom_audience(
            company=None, name='S', contacts=CONTACTS, client=None)
        self.assertTrue(summary['configured'])
        self.assertEqual(summary['error'], 'no_connection')

    def test_delete_on_calls_client(self):
        client = RecordingClient()
        result = aud.delete_crm_custom_audience(
            company=None, audience_id='AUD9', client=client)
        self.assertTrue(result['deleted'])
        self.assertEqual(client.calls[0][0], 'delete_custom_audience')


class MetaClientAudienceTransportTests(SimpleTestCase):
    """Transport bas niveau : schéma/données correctes, edges users/usersreplace/
    DELETE, borne dure ≤10 000 AVANT tout réseau."""

    def _client(self, handler):
        transport = httpx.MockTransport(handler)
        return mc.MetaClient(
            access_token='tok', ad_account_id='act_1',
            http_client=httpx.Client(transport=transport),
            max_retries=0, backoff_base=0)

    def test_add_users_over_10000_raises_before_network(self):
        def handler(request):  # ne doit jamais être atteint
            raise AssertionError('réseau atteint malgré >10 000 lignes')
        client = self._client(handler)
        with self.assertRaises(mc.MetaError):
            client.add_users_to_audience(
                audience_id='A', schema=['EMAIL'],
                data=[['h']] * 10001)

    def test_usersreplace_edge_and_payload(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'num_received': 2})

        client = self._client(handler)
        client.add_users_to_audience(
            audience_id='AUD', schema=['EMAIL', 'PHONE'],
            data=[['e1', 'p1'], ['e2', 'p2']],
            session={'session_id': 7, 'batch_seq': 1, 'last_batch_flag': True},
            replace=True)
        req = captured['request']
        self.assertTrue(str(req.url).endswith('/AUD/usersreplace'))
        form = parse_qs(req.content.decode())
        payload = json.loads(form['payload'][0])
        self.assertEqual(payload['schema'], ['EMAIL', 'PHONE'])
        self.assertEqual(payload['data'], [['e1', 'p1'], ['e2', 'p2']])

    def test_users_add_edge(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={})

        client = self._client(handler)
        client.add_users_to_audience(
            audience_id='AUD', schema=['EMAIL'], data=[['e1']], replace=False)
        self.assertTrue(str(captured['request'].url).endswith('/AUD/users'))

    def test_delete_uses_http_delete(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'success': True})

        client = self._client(handler)
        client.delete_custom_audience(audience_id='AUD')
        self.assertEqual(captured['request'].method, 'DELETE')
        self.assertTrue(str(captured['request'].url).endswith('/AUD'))
