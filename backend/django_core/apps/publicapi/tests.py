"""Tests de l'API publique (N89).

Couvre : authentification par clé (succès, clé invalide, clé désactivée),
scoping par société (A ne voit jamais B), gating par scope (read:leads ≠
read:devis), absence de prix d'achat dans toute charge utile, gestion des clés/
webhooks réservée à l'admin, signature HMAC d'un webhook et livraison
best-effort (échec non bloquant + journalisé).
"""
import hashlib
import hmac
import json
import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis, Facture
from apps.installations.models import Installation
from apps.stock.models import Produit

from .constants import (
    SCOPE_READ_LEADS, SCOPE_READ_DEVIS, SCOPE_READ_FACTURES,
    SCOPE_READ_CHANTIERS, EVENT_LEAD_CREATED, EVENT_FACTURE_PAID,
)
from .models import ApiKey, Webhook, WebhookDelivery, hash_key
from . import delivery

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def session_auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class ApiKeyAuthTests(TestCase):
    def setUp(self):
        self.co_a = make_company('pa-a', 'PA A')
        self.co_b = make_company('pa-b', 'PA B')
        self.lead_a = Lead.objects.create(company=self.co_a, nom='Alpha')
        self.lead_b = Lead.objects.create(company=self.co_b, nom='Beta')
        self.key_a, self.raw_a = ApiKey.issue(
            company=self.co_a, label='A',
            scopes=[SCOPE_READ_LEADS, SCOPE_READ_DEVIS])

    def test_valid_key_reads_leads(self):
        resp = key_client(self.raw_a).get('/api/public/leads/')
        self.assertEqual(resp.status_code, 200)
        names = [r['nom'] for r in rows(resp)]
        self.assertEqual(names, ['Alpha'])

    def test_no_key_is_rejected(self):
        resp = APIClient().get('/api/public/leads/')
        self.assertIn(resp.status_code, (401, 403))

    def test_bad_key_is_rejected(self):
        resp = key_client('tqk_does_not_exist').get('/api/public/leads/')
        self.assertEqual(resp.status_code, 401)

    def test_disabled_key_is_rejected(self):
        self.key_a.enabled = False
        self.key_a.save(update_fields=['enabled'])
        resp = key_client(self.raw_a).get('/api/public/leads/')
        self.assertEqual(resp.status_code, 401)

    def test_company_scoping_no_cross_tenant(self):
        # La clé A ne voit JAMAIS le lead de la société B.
        resp = key_client(self.raw_a).get('/api/public/leads/')
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.lead_a.id, ids)
        self.assertNotIn(self.lead_b.id, ids)

    def test_scope_gating(self):
        # Clé sans read:factures → 403 sur /factures/, 200 sur /leads/.
        self.assertEqual(
            key_client(self.raw_a).get('/api/public/leads/').status_code, 200)
        self.assertEqual(
            key_client(self.raw_a).get('/api/public/factures/').status_code, 403)

    def test_last_used_at_updated(self):
        self.assertIsNone(self.key_a.last_used_at)
        key_client(self.raw_a).get('/api/public/leads/')
        self.key_a.refresh_from_db()
        self.assertIsNotNone(self.key_a.last_used_at)

    def test_only_hash_stored_never_raw(self):
        # Le hash stocké correspond bien à la clé ; la clé brute n'est nulle part.
        self.assertEqual(self.key_a.key_hash, hash_key(self.raw_a))
        self.assertNotEqual(self.key_a.key_hash, self.raw_a)


class NoBuyPriceTests(TestCase):
    def setUp(self):
        self.co = make_company('pa-np', 'PA NP')
        self.client_obj = Client.objects.create(company=self.co, nom='Cli')
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau', prix_achat=500, prix_vente=900)
        self.devis = Devis.objects.create(
            company=self.co, reference='DV-1', client=self.client_obj)
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Panneau',
            quantite=2, prix_unitaire=900)
        self.key, self.raw = ApiKey.issue(
            company=self.co, label='K',
            scopes=[SCOPE_READ_DEVIS])

    def test_no_prix_achat_in_devis_payload(self):
        resp = key_client(self.raw).get('/api/public/devis/')
        self.assertEqual(resp.status_code, 200)
        blob = json.dumps(resp.data)
        # Jamais de prix d'achat / marge ; le prix de vente (900) est OK.
        self.assertNotIn('prix_achat', blob)
        self.assertIn('900', blob)
        # On retire les littéraux d'horodatage ISO avant le contrôle de valeur :
        # « 500 » (prix d'achat) peut surgir PAR HASARD dans les microsecondes
        # d'un `date_creation` (ex. ...T18:57:04.850057Z), ce qui rendait ce test
        # flaky. Après ce nettoyage, un vrai 500 sérialisé reste détecté.
        blob_sans_dates = re.sub(r'\d{4}-\d{2}-\d{2}T[0-9:.]+Z?', '', blob)
        self.assertNotIn('500', blob_sans_dates)


class CompletenessReadTests(TestCase):
    """Les quatre objets cœur sont lisibles avec le bon scope."""
    def setUp(self):
        self.co = make_company('pa-rd', 'PA RD')
        self.client_obj = Client.objects.create(company=self.co, nom='Cli')
        self.lead = Lead.objects.create(company=self.co, nom='L')
        self.devis = Devis.objects.create(
            company=self.co, reference='DV-9', client=self.client_obj)
        self.facture = Facture.objects.create(
            company=self.co, reference='FA-9', client=self.client_obj)
        self.chantier = Installation.objects.create(
            company=self.co, reference='CH-9', client=self.client_obj)
        self.key, self.raw = ApiKey.issue(
            company=self.co, label='all',
            scopes=[SCOPE_READ_LEADS, SCOPE_READ_DEVIS,
                    SCOPE_READ_FACTURES, SCOPE_READ_CHANTIERS])

    def test_all_endpoints_ok(self):
        for path in ('leads', 'devis', 'factures', 'chantiers'):
            resp = key_client(self.raw).get(f'/api/public/{path}/')
            self.assertEqual(resp.status_code, 200, path)
            self.assertEqual(len(rows(resp)), 1, path)


class ManagementEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company('pa-mg', 'PA MG')
        self.admin = make_user(self.co, 'pa-admin', 'admin')
        self.normal = make_user(self.co, 'pa-normal', 'normal')

    def test_admin_creates_key_returns_raw_once(self):
        api = session_auth(self.admin)
        resp = api.post('/api/django/publicapi/keys/', {
            'label': 'Intégration', 'scopes': [SCOPE_READ_LEADS]}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('key', resp.data)
        # ERR89 — la clé révélée une fois n'est jamais mise en cache.
        self.assertEqual(resp['Cache-Control'], 'no-store')
        self.assertEqual(resp['Pragma'], 'no-cache')
        raw = resp.data['key']
        # La clé en clair fonctionne et est rattachée à la société de l'admin.
        key = ApiKey.objects.get(key_hash=hash_key(raw))
        self.assertEqual(key.company, self.co)
        # La lecture suivante ne ré-expose jamais la clé.
        listing = api.get('/api/django/publicapi/keys/')
        for r in rows(listing):
            self.assertNotIn('key', r)

    def test_non_admin_forbidden(self):
        api = session_auth(self.normal)
        resp = api.get('/api/django/publicapi/keys/')
        self.assertEqual(resp.status_code, 403)

    def test_revoke_disables_key(self):
        api = session_auth(self.admin)
        key, _ = ApiKey.issue(company=self.co, label='x', scopes=[])
        resp = api.post(f'/api/django/publicapi/keys/{key.id}/revoke/')
        self.assertEqual(resp.status_code, 200)
        key.refresh_from_db()
        self.assertFalse(key.enabled)

    def test_create_webhook_returns_secret_once(self):
        api = session_auth(self.admin)
        # ERR46 — la validation anti-SSRF résout le DNS ; on la neutralise ici
        # pour tester le flux de création sans dépendre d'un hôte public réel.
        with mock.patch('apps.publicapi.serializers.validate_webhook_target_url',
                        side_effect=lambda u: u):
            resp = api.post('/api/django/publicapi/webhooks/', {
                'target_url': 'https://example.test/hook',
                'events': [EVENT_LEAD_CREATED]}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('secret', resp.data)
        # ERR89 — le secret révélé une fois n'est jamais mis en cache.
        self.assertEqual(resp['Cache-Control'], 'no-store')
        self.assertEqual(resp['Pragma'], 'no-cache')
        hook = Webhook.objects.get(id=resp.data['id'])
        self.assertEqual(hook.company, self.co)
        # Lecture suivante : pas de secret.
        listing = api.get('/api/django/publicapi/webhooks/')
        for r in rows(listing):
            self.assertNotIn('secret', r)

    def test_create_webhook_rejects_http_scheme(self):
        # ERR46 — un schéma non-https est refusé à l'écriture.
        api = session_auth(self.admin)
        resp = api.post('/api/django/publicapi/webhooks/', {
            'target_url': 'http://example.com/hook',
            'events': [EVENT_LEAD_CREATED]}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('target_url', resp.data)

    def test_create_webhook_rejects_internal_host(self):
        # ERR46 — une cible interne (métadonnées cloud) est refusée.
        api = session_auth(self.admin)
        resp = api.post('/api/django/publicapi/webhooks/', {
            'target_url': 'https://169.254.169.254/latest/meta-data/',
            'events': [EVENT_LEAD_CREATED]}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('target_url', resp.data)

    def test_create_webhook_rejects_loopback_host(self):
        # ERR46 — une cible loopback (127.0.0.1) est refusée.
        api = session_auth(self.admin)
        resp = api.post('/api/django/publicapi/webhooks/', {
            'target_url': 'https://127.0.0.1:9000/',
            'events': [EVENT_LEAD_CREATED]}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('target_url', resp.data)

    def test_catalogue(self):
        api = session_auth(self.admin)
        resp = api.get('/api/django/publicapi/catalogue/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('scopes', resp.data)
        self.assertIn('events', resp.data)

    def test_docs_reference_for_admin(self):
        # FG105 — la référence FR statique est lisible et complète.
        api = session_auth(self.admin)
        resp = api.get('/api/django/publicapi/docs/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        self.assertIn('endpoints', data)
        self.assertEqual(len(data['endpoints']), 4)
        self.assertIn('authentification', data)
        self.assertIn('Api-Key', data['authentification']['entete'])
        self.assertIn('scopes', data)
        # Recette HMAC présente + nom d'en-tête correct.
        verif = data['webhooks']['verification_signature']
        self.assertIn('hmac', verif['exemple_python'].lower())
        self.assertEqual(
            data['webhooks']['entetes']['signature'], 'X-Taqinor-Signature')

    def test_docs_reference_non_admin_forbidden(self):
        api = session_auth(self.normal)
        resp = api.get('/api/django/publicapi/docs/')
        self.assertEqual(resp.status_code, 403)


class WebhookDeliveryTests(TestCase):
    def setUp(self):
        self.co = make_company('pa-wh', 'PA WH')
        self.hook = Webhook.objects.create(
            company=self.co, target_url='https://example.test/hook',
            secret='s3cr3t', events=[EVENT_LEAD_CREATED, EVENT_FACTURE_PAID],
            enabled=True)
        # ERR46 — la garde anti-SSRF de livraison résout le DNS ; l'hôte de test
        # `example.test` n'est pas résolvable, on neutralise donc la résolution
        # ici pour tester le flux de livraison (signature, journalisation…).
        patcher = mock.patch(
            'apps.publicapi.delivery.validate_webhook_target_url',
            side_effect=lambda u: u)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_signature_is_correct_hmac(self):
        payload = {'event': EVENT_LEAD_CREATED, 'id': 1}
        body = json.dumps(payload, default=str, sort_keys=True).encode('utf-8')
        captured = {}

        def fake_post(url, content=None, headers=None, timeout=None):
            captured['headers'] = headers
            captured['content'] = content
            return mock.Mock(status_code=200)

        with mock.patch.object(delivery.httpx, 'post', side_effect=fake_post):
            delivery.dispatch_event(self.co.id, EVENT_LEAD_CREATED, payload)

        sent_sig = captured['headers'][delivery.SIGNATURE_HEADER]
        expected = hmac.new(b's3cr3t', body, hashlib.sha256).hexdigest()
        self.assertEqual(sent_sig, expected)
        self.assertEqual(WebhookDelivery.objects.filter(
            status=WebhookDelivery.Statut.SUCCESS).count(), 1)

    def test_delivery_only_to_subscribed_events(self):
        # Webhook NON abonné à facture.paid ? il l'est ici ; en revanche un
        # évènement non listé n'est jamais livré.
        with mock.patch.object(delivery.httpx, 'post') as m:
            m.return_value = mock.Mock(status_code=200)
            delivery.dispatch_event(self.co.id, 'devis.accepted', {})
        self.assertEqual(WebhookDelivery.objects.count(), 0)

    def test_failed_delivery_is_logged_not_raised(self):
        # httpx lève → la livraison ne propage jamais et journalise un échec.
        with mock.patch.object(delivery.httpx, 'post',
                               side_effect=RuntimeError('boom')):
            delivery.dispatch_event(self.co.id, EVENT_LEAD_CREATED,
                                    {'event': EVENT_LEAD_CREATED})
        d = WebhookDelivery.objects.get()
        self.assertEqual(d.status, WebhookDelivery.Statut.FAILED)
        self.assertIn('boom', d.error)

    def test_disabled_webhook_not_delivered(self):
        self.hook.enabled = False
        self.hook.save(update_fields=['enabled'])
        with mock.patch.object(delivery.httpx, 'post') as m:
            delivery.dispatch_event(self.co.id, EVENT_LEAD_CREATED, {})
        m.assert_not_called()


class SignalTriggerTests(TestCase):
    """Les évènements métier déclenchent dispatch_event (best-effort)."""
    def setUp(self):
        self.co = make_company('pa-sg', 'PA SG')
        self.client_obj = Client.objects.create(company=self.co, nom='Cli')

    def test_lead_creation_dispatches(self):
        with mock.patch('apps.publicapi.signals.delivery.dispatch_event') as d:
            Lead.objects.create(company=self.co, nom='New')
        d.assert_called_once()
        args = d.call_args[0]
        self.assertEqual(args[0], self.co.id)
        self.assertEqual(args[1], EVENT_LEAD_CREATED)

    def test_facture_paid_transition_dispatches(self):
        facture = Facture.objects.create(
            company=self.co, reference='FA-7', client=self.client_obj,
            statut=Facture.Statut.EMISE)
        with mock.patch('apps.publicapi.signals.delivery.dispatch_event') as d:
            facture.statut = Facture.Statut.PAYEE
            facture.save()
        d.assert_called_once()
        self.assertEqual(d.call_args[0][1], EVENT_FACTURE_PAID)

    def test_no_dispatch_when_status_unchanged(self):
        facture = Facture.objects.create(
            company=self.co, reference='FA-8', client=self.client_obj,
            statut=Facture.Statut.PAYEE)
        with mock.patch('apps.publicapi.signals.delivery.dispatch_event') as d:
            facture.note = 'edit'
            facture.save()
        d.assert_not_called()


class WebhookSSRFGuardTests(TestCase):
    """ERR46 — la livraison ne POST jamais vers un hôte interne, même si une
    URL dangereuse a été stockée (bypass serializer) ou si le DNS a été
    ré-pointé depuis. Le validateur lui-même rejette schéma + hôtes internes."""

    def setUp(self):
        self.co = make_company('pa-ssrf', 'PA SSRF')

    def test_delivery_blocks_internal_url_without_posting(self):
        # URL interne stockée directement (contourne la validation serializer).
        hook = Webhook.objects.create(
            company=self.co, target_url='https://127.0.0.1:9000/hook',
            secret='s', events=[EVENT_LEAD_CREATED], enabled=True)
        with mock.patch.object(delivery.httpx, 'post') as m:
            delivery.dispatch_event(
                self.co.id, EVENT_LEAD_CREATED, {'event': EVENT_LEAD_CREATED})
        # Jamais de POST réseau vers la cible interne.
        m.assert_not_called()
        # Échec auditable journalisé.
        d = WebhookDelivery.objects.get(webhook=hook)
        self.assertEqual(d.status, WebhookDelivery.Statut.FAILED)
        self.assertIn('SSRF', d.error)

    def test_validator_accepts_public_https(self):
        from .validators import validate_webhook_target_url
        # 8.8.8.8 est public et littéral (pas de DNS) → accepté.
        self.assertEqual(
            validate_webhook_target_url('https://8.8.8.8/hook'),
            'https://8.8.8.8/hook')

    def test_validator_rejects_http_and_internal(self):
        from .validators import UnsafeWebhookURL, validate_webhook_target_url
        for bad in ('http://8.8.8.8/', 'https://169.254.169.254/',
                    'https://10.0.0.5/', 'https://127.0.0.1/',
                    'ftp://8.8.8.8/'):
            with self.assertRaises(UnsafeWebhookURL):
                validate_webhook_target_url(bad)


# ── FG102 — Historique des livraisons + replay + test (ping) ─────────────────

class DeliveryHistoryTests(TestCase):
    """GET webhooks/{id}/deliveries/ — liste paginée, company-scoped."""

    def setUp(self):
        self.co_a = make_company('fg-a', 'FG A')
        self.co_b = make_company('fg-b', 'FG B')
        self.admin_a = make_user(self.co_a, 'fg-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'fg-admin-b', 'admin')
        self.hook_a = Webhook.objects.create(
            company=self.co_a, target_url='https://example.test/a',
            secret='sec-a', events=[EVENT_LEAD_CREATED], enabled=True)
        self.hook_b = Webhook.objects.create(
            company=self.co_b, target_url='https://example.test/b',
            secret='sec-b', events=[EVENT_LEAD_CREATED], enabled=True)
        # 3 livraisons pour le webhook A
        for i in range(3):
            WebhookDelivery.objects.create(
                company=self.co_a, webhook=self.hook_a,
                event=EVENT_LEAD_CREATED, payload={'i': i},
                status=WebhookDelivery.Statut.SUCCESS)
        # 1 livraison pour le webhook B
        WebhookDelivery.objects.create(
            company=self.co_b, webhook=self.hook_b,
            event=EVENT_LEAD_CREATED, payload={},
            status=WebhookDelivery.Statut.FAILED)

    def test_list_returns_own_deliveries(self):
        api = session_auth(self.admin_a)
        resp = api.get(f'/api/django/publicapi/webhooks/{self.hook_a.id}/deliveries/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 3)
        # Chaque entrée expose le payload (FG102 : inclus pour le replay UI)
        for item in resp.data:
            self.assertIn('payload', item)

    def test_cross_company_webhook_is_404(self):
        # L'admin A ne peut pas lire les livraisons du webhook B.
        api = session_auth(self.admin_a)
        resp = api.get(f'/api/django/publicapi/webhooks/{self.hook_b.id}/deliveries/')
        self.assertEqual(resp.status_code, 404)

    def test_non_admin_forbidden(self):
        normal = make_user(self.co_a, 'fg-normal-a', 'normal')
        api = session_auth(normal)
        resp = api.get(f'/api/django/publicapi/webhooks/{self.hook_a.id}/deliveries/')
        self.assertEqual(resp.status_code, 403)


class DeliveryReplayTests(TestCase):
    """POST webhooks/{id}/deliveries/{delivery_id}/replay/"""

    def setUp(self):
        self.co_a = make_company('rp-a', 'RP A')
        self.co_b = make_company('rp-b', 'RP B')
        self.admin_a = make_user(self.co_a, 'rp-admin-a', 'admin')
        self.hook_a = Webhook.objects.create(
            company=self.co_a, target_url='https://example.test/rp',
            secret='rp-sec', events=[EVENT_LEAD_CREATED], enabled=True)
        self.hook_b = Webhook.objects.create(
            company=self.co_b, target_url='https://example.test/rpb',
            secret='rp-secb', events=[EVENT_LEAD_CREATED], enabled=True)
        self.original = WebhookDelivery.objects.create(
            company=self.co_a, webhook=self.hook_a,
            event=EVENT_LEAD_CREATED, payload={'lead_id': 42},
            status=WebhookDelivery.Statut.FAILED,
            error='HTTP 500')
        # Livraison appartenant à la société B
        self.other_co_delivery = WebhookDelivery.objects.create(
            company=self.co_b, webhook=self.hook_b,
            event=EVENT_LEAD_CREATED, payload={},
            status=WebhookDelivery.Statut.FAILED)
        # Patch SSRF guard + httpx pour éviter les vrais appels réseau
        patcher_ssrf = mock.patch(
            'apps.publicapi.delivery.validate_webhook_target_url',
            side_effect=lambda u: u)
        patcher_ssrf.start()
        self.addCleanup(patcher_ssrf.stop)

    def test_replay_sends_original_payload_and_records_new_attempt(self):
        api = session_auth(self.admin_a)
        url = (f'/api/django/publicapi/webhooks/{self.hook_a.id}'
               f'/deliveries/{self.original.id}/replay/')
        with mock.patch.object(delivery.httpx, 'post') as m:
            m.return_value = mock.Mock(status_code=200)
            resp = api.post(url)
        self.assertEqual(resp.status_code, 201)
        # Un NOUVEL enregistrement a été créé (on en a maintenant 2).
        self.assertEqual(
            WebhookDelivery.objects.filter(webhook=self.hook_a).count(), 2)
        # La réponse décrit la nouvelle tentative (succès).
        self.assertEqual(resp.data['status'], WebhookDelivery.Statut.SUCCESS)
        # L'original n'a pas changé.
        self.original.refresh_from_db()
        self.assertEqual(self.original.status, WebhookDelivery.Statut.FAILED)
        self.assertEqual(self.original.error, 'HTTP 500')
        # httpx.post a été appelé avec le bon payload
        call_kwargs = m.call_args
        sent_body = json.loads(call_kwargs[1]['content'])
        self.assertEqual(sent_body, {'lead_id': 42})

    def test_replay_cross_company_delivery_is_404(self):
        # L'admin A ne peut pas rejouer une livraison de la société B.
        api = session_auth(self.admin_a)
        url = (f'/api/django/publicapi/webhooks/{self.hook_a.id}'
               f'/deliveries/{self.other_co_delivery.id}/replay/')
        resp = api.post(url)
        self.assertEqual(resp.status_code, 404)

    def test_replay_cross_company_webhook_is_404(self):
        # L'admin A ne peut pas accéder au webhook de la société B.
        api = session_auth(self.admin_a)
        url = (f'/api/django/publicapi/webhooks/{self.hook_b.id}'
               f'/deliveries/{self.original.id}/replay/')
        resp = api.post(url)
        self.assertEqual(resp.status_code, 404)

    def test_replay_unknown_delivery_is_404(self):
        api = session_auth(self.admin_a)
        url = (f'/api/django/publicapi/webhooks/{self.hook_a.id}'
               f'/deliveries/999999/replay/')
        resp = api.post(url)
        self.assertEqual(resp.status_code, 404)


# ── FG104 — Filtrage, tri & synchro incrémentale (?updated_since=) ───────────

class PublicApiFilterTests(TestCase):
    """Filtres liste blanche, tri natif et synchro incrémentale, company-scoped."""

    def setUp(self):
        self.co = make_company('flt', 'FLT')
        self.client_obj = Client.objects.create(company=self.co, nom='Cli')
        self.lead_new = Lead.objects.create(
            company=self.co, nom='Neuf', stage='NEW', ville='Casablanca')
        self.lead_signed = Lead.objects.create(
            company=self.co, nom='Signé', stage='SIGNED', ville='Rabat')
        self.facture_emise = Facture.objects.create(
            company=self.co, reference='FA-E', client=self.client_obj,
            statut=Facture.Statut.EMISE)
        self.facture_payee = Facture.objects.create(
            company=self.co, reference='FA-P', client=self.client_obj,
            statut=Facture.Statut.PAYEE)
        self.key, self.raw = ApiKey.issue(
            company=self.co, label='flt',
            scopes=[SCOPE_READ_LEADS, SCOPE_READ_FACTURES, SCOPE_READ_CHANTIERS])

    def test_whitelisted_field_filter(self):
        resp = key_client(self.raw).get('/api/public/leads/?stage=SIGNED')
        self.assertEqual(resp.status_code, 200)
        noms = [r['nom'] for r in rows(resp)]
        self.assertEqual(noms, ['Signé'])

    def test_second_whitelisted_filter(self):
        resp = key_client(self.raw).get(
            '/api/public/factures/?statut=payee')
        self.assertEqual(resp.status_code, 200)
        refs = [r['reference'] for r in rows(resp)]
        self.assertEqual(refs, ['FA-P'])

    def test_unknown_filter_is_400_not_500(self):
        # Un paramètre hors liste blanche est refusé proprement (400).
        resp = key_client(self.raw).get('/api/public/leads/?secret=x')
        self.assertEqual(resp.status_code, 400)

    def test_ordering_whitelisted(self):
        resp = key_client(self.raw).get(
            '/api/public/leads/?ordering=date_creation')
        self.assertEqual(resp.status_code, 200)
        noms = [r['nom'] for r in rows(resp)]
        self.assertEqual(noms, ['Neuf', 'Signé'])

    def test_ordering_non_whitelisted_is_ignored(self):
        # Champ non listé → OrderingFilter natif l'ignore (pas de 500/fuite).
        resp = key_client(self.raw).get('/api/public/leads/?ordering=email')
        self.assertEqual(resp.status_code, 200)

    def test_updated_since_filters_incrementally(self):
        from django.utils import timezone
        from datetime import timedelta
        # Tout est récent : un seuil futur ne renvoie rien.
        future = (timezone.now() + timedelta(days=1)).isoformat()
        resp = key_client(self.raw).get(
            f'/api/public/leads/?updated_since={future}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)
        # Un seuil passé renvoie les deux leads.
        past = (timezone.now() - timedelta(days=1)).isoformat()
        resp2 = key_client(self.raw).get(
            f'/api/public/leads/?updated_since={past}')
        self.assertEqual(len(rows(resp2)), 2)

    def test_updated_since_accepts_plain_date(self):
        resp = key_client(self.raw).get(
            '/api/public/leads/?updated_since=2000-01-01')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 2)

    def test_updated_since_invalid_is_400(self):
        resp = key_client(self.raw).get(
            '/api/public/leads/?updated_since=pas-une-date')
        self.assertEqual(resp.status_code, 400)

    def test_chantier_exposes_date_modification(self):
        Installation.objects.create(
            company=self.co, reference='CH-F', client=self.client_obj)
        resp = key_client(self.raw).get('/api/public/chantiers/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('date_modification', rows(resp)[0])

    def test_filter_stays_company_scoped(self):
        other = make_company('flt-b', 'FLT B')
        Lead.objects.create(company=other, nom='Étranger', stage='SIGNED')
        resp = key_client(self.raw).get('/api/public/leads/?stage=SIGNED')
        noms = [r['nom'] for r in rows(resp)]
        self.assertNotIn('Étranger', noms)


class WebhookTestPingTests(TestCase):
    """POST webhooks/{id}/test/ — ping synthétique."""

    def setUp(self):
        self.co_a = make_company('tp-a', 'TP A')
        self.co_b = make_company('tp-b', 'TP B')
        self.admin_a = make_user(self.co_a, 'tp-admin-a', 'admin')
        self.hook_a = Webhook.objects.create(
            company=self.co_a, target_url='https://example.test/tp',
            secret='tp-sec', events=[EVENT_LEAD_CREATED], enabled=True)
        self.hook_b = Webhook.objects.create(
            company=self.co_b, target_url='https://example.test/tpb',
            secret='tp-secb', events=[EVENT_LEAD_CREATED], enabled=True)
        patcher_ssrf = mock.patch(
            'apps.publicapi.delivery.validate_webhook_target_url',
            side_effect=lambda u: u)
        patcher_ssrf.start()
        self.addCleanup(patcher_ssrf.stop)

    def test_ping_creates_delivery_record(self):
        api = session_auth(self.admin_a)
        url = f'/api/django/publicapi/webhooks/{self.hook_a.id}/test/'
        with mock.patch.object(delivery.httpx, 'post') as m:
            m.return_value = mock.Mock(status_code=200)
            resp = api.post(url)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['event'], 'webhook.test')
        self.assertEqual(resp.data['status'], WebhookDelivery.Statut.SUCCESS)
        d = WebhookDelivery.objects.get(webhook=self.hook_a, event='webhook.test')
        self.assertIn('webhook_id', d.payload)
        self.assertEqual(d.payload['webhook_id'], self.hook_a.id)

    def test_ping_records_failure_when_endpoint_errors(self):
        api = session_auth(self.admin_a)
        url = f'/api/django/publicapi/webhooks/{self.hook_a.id}/test/'
        with mock.patch.object(delivery.httpx, 'post',
                               side_effect=RuntimeError('timeout')):
            resp = api.post(url)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['status'], WebhookDelivery.Statut.FAILED)
        self.assertIn('timeout', resp.data['error'])

    def test_ping_cross_company_webhook_is_404(self):
        # L'admin A ne peut pas envoyer un ping vers le webhook de la société B.
        api = session_auth(self.admin_a)
        url = f'/api/django/publicapi/webhooks/{self.hook_b.id}/test/'
        resp = api.post(url)
        self.assertEqual(resp.status_code, 404)
