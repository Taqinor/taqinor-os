"""ASEC40 — le connecteur Odoo global du processus appartient à UNE société
déclarée (``ODOO_COMPANY_ID``).

Constat C-ASEC-010 (latent) : ``signed_deals()`` et la vue métriques
servaient les deals Odoo à l'utilisateur ``adsengine_view`` de N'IMPORTE
QUELLE société ; les commandes retombaient sur « la première société ».

Odoo est simulé AU NIVEAU HTTP par un petit serveur JSON-RPC local (thread) :
aucune fonction interne n'est mockée, et le serveur compte les appels reçus.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.adsengine import odoo_client
from authentication.models import Company

User = get_user_model()
URL = '/api/django/adsengine/metrics/leads/'

LEAD_GAGNE = {
    'id': 7, 'name': 'Client Odoo Signé', 'phone': '+212600000777',
    'mobile': False, 'contact_name': 'Client Odoo Signé',
    'partner_name': False, 'email_from': False, 'expected_revenue': 5000,
    'probability': 100, 'stage_id': [4, 'Won'], 'user_id': False,
    'partner_id': False, 'date_closed': '2026-10-01 10:00:00',
    'active': True, 'create_date': '2026-09-01 10:00:00',
}


class _OdooFactice(BaseHTTPRequestHandler):
    appels = []

    def log_message(self, *args):  # silence
        pass

    def do_POST(self):
        longueur = int(self.headers.get('Content-Length') or 0)
        corps = json.loads(self.rfile.read(longueur) or b'{}')
        params = corps.get('params') or {}
        type(self).appels.append(params.get('method'))
        resultat = None
        if params.get('method') == 'authenticate':
            resultat = 1
        elif params.get('method') == 'execute_kw':
            args = params.get('args') or []
            modele, methode = args[3], args[4]
            kwargs = args[6] if len(args) > 6 else {}
            if methode == 'fields_get':
                resultat = {}
            elif methode == 'search_read':
                premiere_page = not kwargs.get('offset')
                resultat = ([dict(LEAD_GAGNE)]
                            if modele == 'crm.lead' and premiere_page else [])
            else:
                resultat = []
        reponse = json.dumps(
            {'jsonrpc': '2.0', 'id': corps.get('id'), 'result': resultat})
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(reponse.encode())


class OdooSocieteTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = HTTPServer(('127.0.0.1', 0), _OdooFactice)
        cls.thread = threading.Thread(
            target=cls.serveur.serve_forever, daemon=True)
        cls.thread.start()
        cls.url_odoo = 'http://127.0.0.1:%d' % cls.serveur.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        cls.serveur.server_close()
        super().tearDownClass()

    def setUp(self):
        _OdooFactice.appels = []
        self.a = Company.objects.create(nom='ASEC40 A', slug='asec40-a')
        self.b = Company.objects.create(nom='ASEC40 B', slug='asec40-b')
        self.user_a = User.objects.create_user(
            username='asec40_a', password='x', role_legacy='admin',
            company=self.a)
        self.user_b = User.objects.create_user(
            username='asec40_b', password='x', role_legacy='admin',
            company=self.b)

    def _reglages(self, company_id='auto'):
        valeurs = {
            'ODOO_URL': self.url_odoo, 'ODOO_DB': 'test',
            'ODOO_USERNAME': 'lecteur', 'ODOO_API_KEY': 'cle-test',
            'ODOO_COMPANY_ID': (str(self.a.pk) if company_id == 'auto'
                                else company_id),
        }
        return override_settings(**valeurs)

    def _get(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api.get(URL, {'metric': 'signature'})

    def _deals_odoo(self, resp):
        return [r for r in resp.data if r.get('source') == 'odoo']

    def test_autre_societe_sans_donnees_ni_appel(self):
        with self._reglages():
            resp = self._get(self.user_b)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self._deals_odoo(resp), [])
        self.assertEqual(_OdooFactice.appels, [])

    def test_societe_proprietaire_ok(self):
        with self._reglages():
            resp = self._get(self.user_a)
        self.assertEqual(resp.status_code, 200, resp.content)
        noms = [d['nom'] for d in self._deals_odoo(resp)]
        self.assertEqual(noms, ['Client Odoo Signé'])
        self.assertIn('authenticate', _OdooFactice.appels)

    def test_sans_company_id_inactif(self):
        with self._reglages(company_id=''):
            self.assertFalse(odoo_client.is_configured())
            self.assertFalse(odoo_client.is_configured(self.a))
            self.assertIsNone(odoo_client.OdooClient.from_env(company=self.a))
            resp = self._get(self.user_a)
        self.assertEqual(self._deals_odoo(resp), [])
        self.assertEqual(_OdooFactice.appels, [])

    def test_commande_exige_company(self):
        with self._reglages():
            for commande in ('odoo_pull', 'odoo_import_notes'):
                with self.subTest(commande=commande):
                    with self.assertRaises(CommandError):
                        call_command(commande, stdout=StringIO())
            # Une société non propriétaire : aucun appel Odoo.
            sortie = StringIO()
            call_command('odoo_pull', '--company', self.b.slug, stdout=sortie)
            self.assertIn('non', sortie.getvalue())
        self.assertEqual(_OdooFactice.appels, [])
