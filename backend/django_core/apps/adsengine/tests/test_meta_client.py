"""ENG4 — Tests mockés du client Meta Marketing API (aucun réseau).

Couvre l'invariant de sécurité : toute création naît PAUSED (aucun kwarg
``status`` accepté — ``TypeError``), aucune méthode d'activation n'existe, le
token voyage en en-tête (jamais dans l'URL), + parsing des insights et erreur
token expiré. Tests purs → ``SimpleTestCase`` (pas de base de données).
"""
from urllib.parse import parse_qs

import httpx
from django.test import SimpleTestCase

from apps.adsengine import meta_client as mc
from apps.adsengine.models import MetaConnection

TOKEN = 'tok-73951'


def make_client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1', http_client=http_client,
        max_retries=0, backoff_base=0, **kwargs)


def body_of(request):
    return parse_qs(request.content.decode('utf-8'))


class CreateForcesPausedTests(SimpleTestCase):
    def test_create_campaign_is_always_paused(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'id': '123'})

        client = make_client(handler)
        result = client.create_campaign(name='Solar', objective='OUTCOME_LEADS')
        self.assertEqual(result, {'id': '123'})
        form = body_of(captured['request'])
        self.assertEqual(form['status'], ['PAUSED'])
        self.assertNotIn('ACTIVE', captured['request'].content.decode('utf-8'))

    def test_status_kwarg_raises_typeerror(self):
        client = make_client(lambda r: httpx.Response(200, json={'id': '1'}))
        # Aucune signature de création n'accepte ``status`` — le langage lève.
        with self.assertRaises(TypeError):
            client.create_campaign(
                name='X', objective='OUTCOME_LEADS', status='ACTIVE')
        with self.assertRaises(TypeError):
            client.create_adset(name='X', campaign_id='1', status='ACTIVE')
        with self.assertRaises(TypeError):
            client.create_ad(name='X', adset_id='1', status='ACTIVE')

    def test_status_smuggled_via_extra_fields_is_forced_paused(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'id': '9'})

        client = make_client(handler)
        client.create_campaign(
            name='X', objective='OUTCOME_LEADS',
            extra_fields={'status': 'ACTIVE', 'daily_budget': 5000})
        form = body_of(captured['request'])
        self.assertEqual(form['status'], ['PAUSED'])
        self.assertEqual(form['daily_budget'], ['5000'])

    def test_create_adset_and_ad_are_paused(self):
        captured = []

        def handler(request):
            captured.append(request)
            return httpx.Response(200, json={'id': 'x'})

        client = make_client(handler)
        client.create_adset(name='AS', campaign_id='c1')
        client.create_ad(name='AD', adset_id='a1')
        for req in captured:
            self.assertEqual(body_of(req)['status'], ['PAUSED'])

    def test_no_activation_method_exists(self):
        client = make_client(lambda r: httpx.Response(200, json={}))
        for forbidden in (
            'activate', 'activate_campaign', 'unpause', 'resume', 'enable',
            'enable_campaign', 'set_active', 'set_status',
        ):
            self.assertFalse(
                hasattr(client, forbidden),
                f'Le client ne doit exposer aucune méthode « {forbidden} ».')


class TransportTests(SimpleTestCase):
    def test_token_travels_in_header_never_in_url(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'data': []})

        make_client(handler).get_campaigns()
        req = captured['request']
        self.assertEqual(req.headers.get('Authorization'), f'Bearer {TOKEN}')
        self.assertNotIn(TOKEN, str(req.url))

    def test_reads_request_metadata_fields_by_default(self):
        """Régression ENG5 : sans ``fields`` explicite, un edge Graph ne renvoie
        que ``id`` — d'où des miroirs sans nom/statut/objectif/budget (colonnes
        vides). Les lectures de synchro demandent donc par défaut les champs que
        ``sync.py`` exploite à chaque niveau."""
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'data': []})

        client = make_client(handler)
        cases = [
            (client.get_campaigns, ('name', 'status', 'objective',
                                    'daily_budget')),
            (client.get_adsets, ('name', 'status', 'campaign_id',
                                 'daily_budget')),
            (client.get_ads, ('name', 'status', 'adset_id')),
        ]
        for read, expected in cases:
            read()
            fields = (captured['request'].url.params.get('fields') or '')
            got = fields.split(',')
            for f in expected:
                self.assertIn(f, got, f'{read.__name__} doit demander « {f} »')

    def test_insights_parsing(self):
        rows = [
            {'spend': '12.50', 'impressions': '100', 'clicks': '4',
             'frequency': '1.3'},
            {'spend': '3.00', 'impressions': '20', 'clicks': '1'},
        ]

        def handler(request):
            return httpx.Response(200, json={'data': rows})

        client = make_client(handler)
        parsed = client.get_insights('act_1', fields=['spend', 'impressions'])
        self.assertEqual(parsed, rows)
        self.assertEqual(parsed[0]['spend'], '12.50')

    def test_expired_token_raises_meta_auth_error(self):
        def handler(request):
            return httpx.Response(400, json={'error': {
                'code': 190,
                'message': 'Error validating access token: Session has expired',
            }})

        client = make_client(handler)
        with self.assertRaises(mc.MetaAuthError):
            client.get_campaigns()

    def test_rate_limit_raises_rate_limit_error(self):
        def handler(request):
            return httpx.Response(429, json={'error': {
                'code': 17, 'message': 'User request limit reached'}})

        client = make_client(handler)  # max_retries=0 → lève tout de suite
        with self.assertRaises(mc.MetaRateLimitError):
            client.get_campaigns()


class FromConnectionTests(SimpleTestCase):
    def test_from_connection_reads_token(self):
        conn = MetaConnection(
            ad_account_id='act_9', credentials={'access_token': 'tok-abc'})
        client = mc.MetaClient.from_connection(
            conn, http_client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(200, json={}))),
            max_retries=0, backoff_base=0)
        self.assertEqual(client._token, 'tok-abc')
        self.assertEqual(client.ad_account_id, 'act_9')

    def test_missing_token_raises(self):
        with self.assertRaises(mc.MetaAuthError):
            mc.MetaClient(access_token='')
        conn = MetaConnection(ad_account_id='act_9', credentials={})
        with self.assertRaises(mc.MetaAuthError):
            mc.MetaClient.from_connection(conn)
