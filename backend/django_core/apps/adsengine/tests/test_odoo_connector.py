"""ADSENG-ODOO — Tests mockés du connecteur Odoo LECTURE SEULE (aucun réseau).

Couvre : no-op propre quand non configuré ; parsing des leads / sale.orders ;
normalisation téléphone IDENTIQUE à celle du CRM (QW10) ; forme de
``signed_deals`` (montant préféré = sale.order, repli = lead gagné) ; maths de
``odoo_cost_per_signature`` (dont 0 signature sans crash) ; et un test NÉGATIF
prouvant que le client n'émet JAMAIS create/write/unlink (règle #1).

Le transport JSON-RPC est simulé avec ``httpx.MockTransport`` (comme les tests de
``meta_client``). Les tests purs → ``SimpleTestCase`` ; les maths société →
``TestCase`` (Company + miroirs + snapshots + lead CRM).
"""
import json
import os
from decimal import Decimal
from unittest import mock

import httpx
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.crm import services as crm_services
from apps.crm.models import Lead
from apps.crm.selectors import normalize_phone_key

from apps.adsengine import odoo_client, odoo_selectors
from apps.adsengine.models import AdCampaignMirror, InsightSnapshot
from apps.adsengine.odoo_metrics import odoo_cost_per_signature

UID = 7

# ── Fixtures Odoo (dicts bruts tels que renvoyés par search_read) ─────────────
LEADS = [
    {  # gagné (probability 100) + commande confirmée liée → montant = commande
        'id': 1, 'name': 'DAZZLEMEDAI-TAQINOR FORM-26/03/2026',
        'phone': '+212 612-345-678', 'mobile': False,
        'expected_revenue': 50000, 'probability': 100,
        'stage_id': [5, 'Won'], 'user_id': [3, 'Commercial A'],
        'partner_id': [11, 'Client A'], 'date_closed': '2026-03-27 10:00:00',
        'active': True, 'create_date': '2026-03-20 09:00:00',
    },
    {  # gagné (date_closed + actif) SANS commande → repli expected_revenue
        'id': 2, 'name': 'TAQINOR FORM-4.0',
        'phone': '+212655667788', 'mobile': False,
        'expected_revenue': 30000, 'probability': 60,
        'stage_id': [4, 'preliminary quote sent'], 'user_id': [9, 'Commercial B'],
        'partner_id': [12, 'Client B'], 'date_closed': '2026-04-02 08:00:00',
        'active': True, 'create_date': '2026-03-28 09:00:00',
    },
    {  # NON gagné → jamais un deal signé
        'id': 3, 'name': 'TAQINOR OLD LEAD - froid',
        'phone': '+212600000000', 'mobile': False,
        'expected_revenue': 0, 'probability': 15,
        'stage_id': [1, 'New'], 'user_id': [3, 'Commercial A'],
        'partner_id': [13, 'Client C'], 'date_closed': False,
        'active': True, 'create_date': '2026-02-01 09:00:00',
    },
]

ORDERS = [
    {  # confirmé, lié au lead 1 → montant préféré 48000 (≠ expected_revenue)
        'id': 100, 'name': 'S00100', 'state': 'sale', 'amount_total': '48000.00',
        'date_order': '2026-03-27 12:00:00', 'partner_id': [11, 'Client A'],
        'opportunity_id': [1, 'DAZZLEMEDAI-TAQINOR FORM-26/03/2026'],
        'create_date': '2026-03-27 11:00:00',
    },
    {  # confirmé (done) SANS opportunité → téléphone résolu via res.partner
        'id': 101, 'name': 'S00101', 'state': 'done', 'amount_total': '12000.00',
        'date_order': '2026-04-01 09:00:00', 'partner_id': [20, 'Walk-in'],
        'opportunity_id': False, 'create_date': '2026-04-01 08:00:00',
    },
    {  # brouillon → PAS signé
        'id': 102, 'name': 'S00102', 'state': 'draft', 'amount_total': '9999.00',
        'date_order': False, 'partner_id': [21, 'Prospect'],
        'opportunity_id': False, 'create_date': '2026-04-03 08:00:00',
    },
]

PARTNERS = [
    {'id': 20, 'phone': '+212611223344', 'mobile': False, 'name': 'Walk-in'},
]


def make_handler(*, leads=LEADS, orders=ORDERS, partners=PARTNERS, uid=UID,
                 calls=None, auth_uid=None):
    """Fabrique un handler ``httpx.MockTransport`` qui simule le JSON-RPC Odoo.

    ``calls`` (liste) enregistre chaque ``(service, method, orm_method)`` pour les
    assertions read-only. ``auth_uid`` force la valeur renvoyée par authenticate
    (ex. ``False`` pour simuler un refus)."""
    def handler(request):
        payload = json.loads(request.content.decode('utf-8'))
        params = payload['params']
        service, method, args = (
            params['service'], params['method'], params['args'])
        if service == 'common' and method == 'authenticate':
            if calls is not None:
                calls.append((service, method, None))
            result = auth_uid if auth_uid is not None else uid
            return httpx.Response(200, json={'result': result})
        if service == 'object' and method == 'execute_kw':
            model, orm_method = args[3], args[4]
            if calls is not None:
                calls.append((service, method, orm_method))
            if orm_method == 'search_read':
                data = {'crm.lead': leads, 'sale.order': orders,
                        'res.partner': partners}.get(model, [])
                return httpx.Response(200, json={'result': data})
            return httpx.Response(200, json={'result': []})
        return httpx.Response(200, json={'result': None})
    return handler


def make_client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return odoo_client.OdooClient(
        url='https://taqinor-solutions.odoo.com', db='taqinor-solutions',
        username='founder', api_key='secret-key', http_client=http_client,
        max_retries=0, backoff_base=0, **kwargs)


class UnconfiguredNoOpTests(SimpleTestCase):
    """Sans les 4 variables ODOO_*, tout no-ope (aucun appel réseau, aucun 500)."""

    def test_from_env_and_selectors_are_empty_when_unconfigured(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for key in ('ODOO_URL', 'ODOO_DB', 'ODOO_USERNAME', 'ODOO_API_KEY'):
                os.environ.pop(key, None)
            self.assertFalse(odoo_client.is_configured())
            self.assertIsNone(odoo_client.OdooClient.from_env())
            self.assertEqual(odoo_selectors.signed_deals(), [])
            self.assertEqual(odoo_selectors.signed_count(), 0)
            self.assertEqual(odoo_selectors.lead_stage_counts(), {})


class ParsingTests(SimpleTestCase):
    def test_authenticate_returns_uid_and_reuses_it(self):
        calls = []
        client = make_client(make_handler(calls=calls))
        self.assertEqual(client.authenticate(), UID)
        self.assertEqual(client.authenticate(), UID)  # mémoïsé
        self.assertEqual(
            [c for c in calls if c[1] == 'authenticate'].__len__(), 1)

    def test_authenticate_refused_raises_auth_error(self):
        client = make_client(make_handler(auth_uid=False))
        with self.assertRaises(odoo_client.OdooAuthError):
            client.authenticate()

    def test_read_leads_and_orders_parse_raw_dicts(self):
        client = make_client(make_handler())
        leads = client.read_leads()
        self.assertEqual(len(leads), 3)
        self.assertEqual(leads[0]['name'],
                         'DAZZLEMEDAI-TAQINOR FORM-26/03/2026')
        orders = client.read_sale_orders()
        self.assertEqual([o['state'] for o in orders],
                         ['sale', 'done', 'draft'])

    def test_api_key_travels_in_body_never_in_url(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'result': UID})

        make_client(handler).authenticate()
        req = captured['request']
        self.assertNotIn('secret-key', str(req.url))
        self.assertIn('secret-key', req.content.decode('utf-8'))


class PhoneNormalizationTests(SimpleTestCase):
    def test_phone_norm_matches_crm_qw10(self):
        # La clé exposée délègue EXACTEMENT à crm.services.normalize_phone (QW10).
        for raw in ('+212 612-345-678', '0612345678', '00212612345678'):
            self.assertEqual(
                normalize_phone_key(raw), crm_services.normalize_phone(raw))
        # Un numéro Odoo produit la même clé qu'un lead Meta de l'ERP.
        self.assertEqual(normalize_phone_key('+212 612-345-678'), '612345678')


class SignedDealsShapeTests(SimpleTestCase):
    def test_signed_deals_shape_and_amount_preference(self):
        client = make_client(make_handler())
        deals = odoo_selectors.signed_deals(client=client)
        # 3 deals : ordre A (lead 1), ordre C (partner), repli lead 2. Lead 3
        # (non gagné) et l'ordre brouillon sont exclus.
        self.assertEqual(len(deals), 3)
        for deal in deals:
            self.assertEqual(set(deal), {
                'phone_norm', 'amount_mad', 'date', 'source_name', 'origin',
                'lead_id'})
            self.assertIsInstance(deal['amount_mad'], Decimal)

        by_phone = {d['phone_norm']: d for d in deals}
        # Lead 1 : montant préféré = sale.order (48000), pas expected_revenue.
        d1 = by_phone['612345678']
        self.assertEqual(d1['amount_mad'], Decimal('48000.00'))
        self.assertEqual(d1['origin'], 'sale_order')
        self.assertEqual(d1['lead_id'], 1)
        # Ordre sans opportunité : téléphone résolu via res.partner.
        self.assertIn('611223344', by_phone)
        self.assertEqual(by_phone['611223344']['origin'], 'sale_order')
        # Lead 2 gagné sans commande : repli expected_revenue (30000).
        d2 = by_phone['655667788']
        self.assertEqual(d2['amount_mad'], Decimal('30000'))
        self.assertEqual(d2['origin'], 'won_lead')

    def test_signed_count_matches(self):
        client = make_client(make_handler())
        self.assertEqual(odoo_selectors.signed_count(client=client), 3)

    def test_lead_stage_counts(self):
        client = make_client(make_handler())
        counts = odoo_selectors.lead_stage_counts(client=client)
        self.assertEqual(counts.get('Won'), 1)
        self.assertEqual(counts.get('New'), 1)


class ReadOnlyGuaranteeTests(SimpleTestCase):
    """Règle #1 : le client ne peut, par construction, QUE lire Odoo."""

    def test_only_read_methods_hit_the_transport(self):
        calls = []
        client = make_client(make_handler(calls=calls))
        odoo_selectors.signed_deals(client=client)
        orm_methods = {m for (_s, meth, m) in calls
                       if meth == 'execute_kw'}
        # Toutes les méthodes ORM émises sont dans l'allowlist LECTURE.
        self.assertTrue(orm_methods)
        self.assertTrue(orm_methods.issubset(odoo_client._READ_METHODS))
        # AUCUNE mutation n'a été émise.
        for forbidden in ('create', 'write', 'unlink', 'copy'):
            self.assertNotIn(forbidden, orm_methods)

    def test_execute_kw_refuses_write_methods(self):
        client = make_client(make_handler())
        for forbidden in ('write', 'create', 'unlink', 'copy',
                          'action_confirm'):
            with self.assertRaises(odoo_client.OdooError):
                client._execute_kw('crm.lead', forbidden, [[1], {'x': 1}])

    def test_client_exposes_no_write_helpers(self):
        client = make_client(make_handler())
        for forbidden in ('create', 'write', 'unlink', 'create_lead',
                          'update', 'save'):
            self.assertFalse(
                hasattr(client, forbidden),
                f'Le client ne doit exposer aucune méthode « {forbidden} ».')


class OdooCostPerSignatureMathTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Odoo Co', slug='odoo-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='CAMP123', name='Solaire Casa',
            status='PAUSED')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)
        import datetime
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=self.camp.pk,
            date=datetime.date(2026, 3, 27), spend=Decimal('9000.00'), results=3)
        # Lead Meta capturé par l'ERP : même téléphone que le deal Odoo du lead 1,
        # campagne CAMP123 → l'attribution par campagne doit le rapprocher.
        Lead.objects.create(
            company=self.company, nom='Prospect Meta',
            telephone='+212612345678', meta_campaign_id='CAMP123',
            utm_campaign='Solaire Casa')

    def test_total_cost_per_signature_math(self):
        client = make_client(make_handler())
        result = odoo_cost_per_signature(self.company, client=client)
        self.assertEqual(result['signatures'], 3)
        self.assertEqual(result['total_spend'], '9000.00')
        # 9000 / 3 signatures = 3000.
        self.assertEqual(Decimal(result['cost_per_signature']), Decimal('3000'))
        self.assertEqual(len(result['signed_deals']), 3)
        self.assertIn('note', result['attribution'])

    def test_per_campaign_attribution_by_phone(self):
        client = make_client(make_handler())
        result = odoo_cost_per_signature(self.company, client=client)
        # 1 deal (612345678) match le lead Meta CAMP123 ; 2 restent non attribués.
        self.assertEqual(result['attribution']['attributed'], 1)
        self.assertEqual(result['attribution']['unattributed'], 2)
        camps = {c['campaign_key']: c for c in result['per_campaign']}
        self.assertIn('CAMP123', camps)
        self.assertEqual(camps['CAMP123']['signatures'], 1)
        # Dépense de la campagne (9000) rattachée par meta_id → coût 9000/1.
        self.assertEqual(camps['CAMP123']['spend'], '9000.00')
        self.assertEqual(
            Decimal(camps['CAMP123']['cost_per_signature']), Decimal('9000'))

    def test_zero_signatures_no_crash(self):
        # Aucun lead gagné, aucune commande confirmée → 0 signature.
        empty_handler = make_handler(leads=[], orders=[], partners=[])
        client = make_client(empty_handler)
        result = odoo_cost_per_signature(self.company, client=client)
        self.assertEqual(result['signatures'], 0)
        self.assertIsNone(result['cost_per_signature'])
        self.assertEqual(result['total_spend'], '9000.00')  # dépense conservée
        self.assertEqual(result['signed_deals'], [])
        self.assertNotIn('odoo_error', result)  # chemin succès : forme inchangée

    def test_odoo_read_failure_degrades_instead_of_500(self):
        # CONTRAT DE LA VUE : une lecture Odoo qui échoue (ici auth refusée, mais
        # aussi bien réseau/DB/login erronés en prod) ne doit JAMAIS lever — on
        # dégrade en signatures=0 + ``odoo_error`` explicite, la dépense Meta
        # locale restant servie. Régression : sans le try/except la vue renvoyait
        # un 500 dès que le connecteur était configuré mais l'appel Odoo échouait.
        client = make_client(make_handler(auth_uid=False))  # authenticate refusé
        result = odoo_cost_per_signature(self.company, client=client)
        self.assertEqual(result['signatures'], 0)
        self.assertIsNone(result['cost_per_signature'])
        self.assertEqual(result['total_spend'], '9000.00')  # dépense conservée
        self.assertEqual(result['signed_deals'], [])
        self.assertIn('odoo_error', result)
        self.assertIn('OdooAuthError', result['odoo_error'])
