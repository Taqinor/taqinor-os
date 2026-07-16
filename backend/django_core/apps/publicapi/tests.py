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
from apps.ventes.models import Devis, LigneDevis, Facture, Paiement
from apps.installations.models import Installation, Intervention
from apps.sav.models import Ticket
from apps.stock.models import Produit, Categorie

from .constants import (
    SCOPE_READ_LEADS, SCOPE_READ_DEVIS, SCOPE_READ_FACTURES,
    SCOPE_READ_CHANTIERS, SCOPE_READ_STOCK, EVENT_LEAD_CREATED,
    EVENT_FACTURE_PAID,
    EVENT_LEAD_LOST, EVENT_LEAD_STAGE_CHANGED, EVENT_DEVIS_SENT,
    EVENT_FACTURE_CREATED, EVENT_PAIEMENT_RECORDED,
    EVENT_INTERVENTION_COMPLETED, EVENT_TICKET_CREATED, EVENT_TICKET_RESOLVED,
    EVENT_STOCK_SEUIL_ATTEINT, EVENT_LIVRAISON_LIVREE,
    SCOPE_WRITE_LEADS, SCOPE_WRITE_ACTIVITIES,
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
        # XSTK23 a ajouté /produits/ (5ᵉ endpoint : leads/devis/factures/
        # chantiers/produits).
        self.assertEqual(len(data['endpoints']), 5)
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
        # YAPIC8 — l'émission passe désormais par la tâche Celery
        # `deliver_webhook.delay`. En test (broker présent mais aucun worker),
        # on exécute les tâches EN LIGNE (eager) pour exercer la livraison
        # réelle dans le processus de test. Portée limitée à cette classe.
        from erp_agentique.celery import app as celery_app
        self._prev_eager = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = False

        def _restore():
            celery_app.conf.task_always_eager = self._prev_eager
        self.addCleanup(_restore)

    def test_signature_is_correct_hmac(self):
        payload = {'event': EVENT_LEAD_CREATED, 'id': 1}
        captured = {}

        def fake_post(url, content=None, headers=None, timeout=None):
            captured['headers'] = headers
            captured['content'] = content
            return mock.Mock(status_code=200)

        with mock.patch.object(delivery.httpx, 'post', side_effect=fake_post):
            delivery.dispatch_event(self.co.id, EVENT_LEAD_CREATED, payload)

        # YAPIC8 — la signature couvre `timestamp.body` (le corps réellement
        # envoyé porte aussi l'event_id injecté par dispatch_event).
        sent_sig = captured['headers'][delivery.SIGNATURE_HEADER]
        ts = captured['headers'][delivery.TIMESTAMP_HEADER]
        body = captured['content']
        expected = hmac.new(
            b's3cr3t', f'{ts}.'.encode('utf-8') + body,
            hashlib.sha256).hexdigest()
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
        # httpx lève → la livraison ne propage jamais et journalise un échec
        # (best-effort). Testé via _deliver_one (chemin synchrone du replay).
        with mock.patch.object(delivery.httpx, 'post',
                               side_effect=RuntimeError('boom')):
            delivery._deliver_one(self.hook, EVENT_LEAD_CREATED,
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


class ExtraEventTriggerTests(TestCase):
    """FG103 — nouveaux évènements webhook (devis.sent, lead.lost/stage_changed,
    facture.created, intervention.completed, ticket.created/resolved,
    paiement.recorded)."""
    def setUp(self):
        self.co = make_company('pa-ev', 'PA EV')
        self.client_obj = Client.objects.create(company=self.co, nom='Cli')

    def _events(self, dispatch_mock):
        return [c.args[1] for c in dispatch_mock.call_args_list]

    def test_devis_sent_transition_dispatches(self):
        devis = Devis.objects.create(
            company=self.co, reference='DV-1', client=self.client_obj,
            statut=Devis.Statut.BROUILLON)
        with mock.patch('apps.publicapi.signals.delivery.dispatch_event') as d:
            devis.statut = Devis.Statut.ENVOYE
            devis.save()
        self.assertIn(EVENT_DEVIS_SENT, self._events(d))

    def test_lead_lost_dispatches(self):
        lead = Lead.objects.create(company=self.co, nom='Perdu')
        with mock.patch('apps.publicapi.signals.delivery.dispatch_event') as d:
            lead.perdu = True
            lead.motif_perte = 'budget'
            lead.save()
        self.assertIn(EVENT_LEAD_LOST, self._events(d))

    def test_lead_stage_changed_dispatches(self):
        from apps.crm.stages import STAGES, NEW
        # Première étape canonique ≠ NEW (sans hardcoder de nom d'étape).
        next_stage = next(s for s in STAGES if s != NEW)
        lead = Lead.objects.create(company=self.co, nom='Étape')
        with mock.patch('apps.publicapi.signals.delivery.dispatch_event') as d:
            lead.stage = next_stage
            lead.save()
        self.assertIn(EVENT_LEAD_STAGE_CHANGED, self._events(d))

    def test_facture_created_dispatches(self):
        with mock.patch('apps.publicapi.signals.delivery.dispatch_event') as d:
            Facture.objects.create(
                company=self.co, reference='FA-EV', client=self.client_obj,
                statut=Facture.Statut.EMISE)
        self.assertIn(EVENT_FACTURE_CREATED, self._events(d))

    def test_paiement_recorded_dispatches(self):
        import datetime
        facture = Facture.objects.create(
            company=self.co, reference='FA-PAY', client=self.client_obj,
            statut=Facture.Statut.EMISE)
        with mock.patch('apps.publicapi.signals.delivery.dispatch_event') as d:
            Paiement.objects.create(
                company=self.co, facture=facture, montant=100,
                date_paiement=datetime.date(2026, 1, 1))
        self.assertIn(EVENT_PAIEMENT_RECORDED, self._events(d))

    def test_intervention_completed_dispatches(self):
        inst = Installation.objects.create(
            company=self.co, reference='CH-EV', client=self.client_obj)
        interv = Intervention.objects.create(
            company=self.co, installation=inst,
            type_intervention=Intervention.Type.POSE,
            statut=Intervention.Statut.SUR_SITE)
        with mock.patch('apps.publicapi.signals.delivery.dispatch_event') as d:
            interv.statut = Intervention.Statut.TERMINEE
            interv.save()
        self.assertIn(EVENT_INTERVENTION_COMPLETED, self._events(d))

    def test_ticket_created_and_resolved_dispatch(self):
        with mock.patch('apps.publicapi.signals.delivery.dispatch_event') as d:
            ticket = Ticket.objects.create(
                company=self.co, reference='TK-1', client=self.client_obj,
                statut=Ticket.Statut.NOUVEAU)
        self.assertIn(EVENT_TICKET_CREATED, self._events(d))
        with mock.patch('apps.publicapi.signals.delivery.dispatch_event') as d:
            ticket.statut = Ticket.Statut.RESOLU
            ticket.save()
        self.assertIn(EVENT_TICKET_RESOLVED, self._events(d))


class WebhookSSRFGuardTests(TestCase):
    """ERR46 — la livraison ne POST jamais vers un hôte interne, même si une
    URL dangereuse a été stockée (bypass serializer) ou si le DNS a été
    ré-pointé depuis. Le validateur lui-même rejette schéma + hôtes internes."""

    def setUp(self):
        self.co = make_company('pa-ssrf', 'PA SSRF')
        # dispatch_event passe par la tâche Celery deliver_webhook : en test
        # (broker sans worker) on l'exécute EN LIGNE (eager) pour journaliser
        # réellement la tentative bloquée (SSRF) dans WebhookDelivery.
        from erp_agentique.celery import app as celery_app
        _prev_eager = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = False
        self.addCleanup(
            lambda: setattr(celery_app.conf, 'task_always_eager', _prev_eager))

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
        # YAPIC8 pose un event_id stable dans le payload (rejoué à l'identique) :
        # le corps envoyé porte donc lead_id + event_id.
        self.assertEqual(sent_body['lead_id'], 42)
        self.assertIn('event_id', sent_body)

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


# ── FG106 — Passerelle OCR → lead / brouillon de devis ──────────────────────

class OcrToCrmBridgeTests(TestCase):
    """POST publicapi/ocr-to-crm/ — création company-scoped via services cibles."""

    def setUp(self):
        self.co = make_company('ocr', 'OCR')
        self.admin = make_user(self.co, 'ocr-admin', 'admin')
        self.normal = make_user(self.co, 'ocr-normal', 'normal')
        self.fields = {
            'fournisseur': 'Panneaux du Sud SARL',
            'numero': 'FAC-2026-001',
            'montant_ht': '12000',
            'montant_ttc': '14400',
            'date': '2026-06-30',
        }

    def test_creates_draft_lead(self):
        from apps.crm.models import Lead
        api = session_auth(self.admin)
        resp = api.post('/api/django/publicapi/ocr-to-crm/',
                        {'mode': 'lead', 'fields': self.fields}, format='json')
        self.assertEqual(resp.status_code, 201)
        lead = Lead.objects.get(id=resp.data['lead_id'])
        self.assertEqual(lead.company, self.co)
        self.assertEqual(lead.nom, 'Panneaux du Sud SARL')
        # Le lead reste à l'étape par défaut (le service ne fait pas avancer le funnel).
        self.assertEqual(lead.stage, Lead._meta.get_field('stage').default)

    def test_creates_draft_lead_and_devis(self):
        from apps.ventes.models import Devis
        api = session_auth(self.admin)
        resp = api.post('/api/django/publicapi/ocr-to-crm/',
                        {'mode': 'devis', 'fields': self.fields}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('lead_id', resp.data)
        devis = Devis.objects.get(id=resp.data['devis_id'])
        self.assertEqual(devis.company, self.co)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        # Le client est résolu depuis le lead (jamais null sur un devis).
        self.assertIsNotNone(devis.client_id)
        self.assertEqual(devis.lead_id, resp.data['lead_id'])
        # Montants extraits consignés dans la note pour la saisie.
        self.assertIn('14400', devis.note)

    def test_unknown_mode_is_400(self):
        api = session_auth(self.admin)
        resp = api.post('/api/django/publicapi/ocr-to-crm/',
                        {'mode': 'facture', 'fields': self.fields}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_empty_fields_is_400(self):
        # Aucun nom exploitable → 400 (jamais un lead anonyme).
        api = session_auth(self.admin)
        resp = api.post('/api/django/publicapi/ocr-to-crm/',
                        {'mode': 'lead', 'fields': {}}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_non_admin_forbidden(self):
        api = session_auth(self.normal)
        resp = api.post('/api/django/publicapi/ocr-to-crm/',
                        {'mode': 'lead', 'fields': self.fields}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_company_comes_from_user_not_body(self):
        from apps.crm.models import Lead
        other = make_company('ocr-b', 'OCR B')
        api = session_auth(self.admin)
        # Une « company » dans le corps est ignorée : la société vient du user.
        resp = api.post('/api/django/publicapi/ocr-to-crm/',
                        {'mode': 'lead', 'fields': self.fields,
                         'company': other.id}, format='json')
        self.assertEqual(resp.status_code, 201)
        lead = Lead.objects.get(id=resp.data['lead_id'])
        self.assertEqual(lead.company, self.co)


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


# ── XSTK23 — API publique stock + webhooks inventaire ───────────────────────

class PublicStockScopeTests(TestCase):
    """`read:stock` lit la disponibilité produit — jamais de coût, jamais
    cross-tenant, les autres clés → 403."""

    def setUp(self):
        self.co_a = make_company('pa-stk-a', 'PA STK A')
        self.co_b = make_company('pa-stk-b', 'PA STK B')
        self.categorie = Categorie.objects.create(company=self.co_a, nom='Panneaux')
        self.produit_a = Produit.objects.create(
            company=self.co_a, nom='Panneau 450W', sku='PAN-450',
            marque='Huawei', categorie=self.categorie,
            prix_vente=1200, prix_achat=800, quantite_stock=50,
            seuil_alerte=10,
        )
        self.produit_archive = Produit.objects.create(
            company=self.co_a, nom='Ancien modèle', sku='OLD-1',
            prix_vente=100, prix_achat=50, quantite_stock=5,
            is_archived=True,
        )
        self.produit_b = Produit.objects.create(
            company=self.co_b, nom='Onduleur B', sku='OND-B',
            prix_vente=3000, prix_achat=2000, quantite_stock=20,
        )
        self.key_stock, self.raw_stock = ApiKey.issue(
            company=self.co_a, label='stock', scopes=[SCOPE_READ_STOCK])
        self.key_leads, self.raw_leads = ApiKey.issue(
            company=self.co_a, label='leads', scopes=[SCOPE_READ_LEADS])

    def test_scoped_key_reads_products(self):
        resp = key_client(self.raw_stock).get('/api/public/produits/')
        self.assertEqual(resp.status_code, 200)
        skus = [r['sku'] for r in rows(resp)]
        self.assertIn('PAN-450', skus)

    def test_other_scope_key_is_403(self):
        resp = key_client(self.raw_leads).get('/api/public/produits/')
        self.assertEqual(resp.status_code, 403)

    def test_no_cost_field_ever_leaks(self):
        resp = key_client(self.raw_stock).get('/api/public/produits/')
        payload = json.dumps(rows(resp))
        self.assertNotIn('prix_achat', payload)
        self.assertNotIn('prix_vente', payload)
        row = rows(resp)[0]
        expected_fields = {
            'id', 'sku', 'nom', 'marque', 'categorie', 'quantite_disponible',
        }
        self.assertEqual(set(row.keys()), expected_fields)

    def test_categorie_exposed_as_label(self):
        resp = key_client(self.raw_stock).get('/api/public/produits/')
        row = next(r for r in rows(resp) if r['sku'] == 'PAN-450')
        self.assertEqual(row['categorie'], 'Panneaux')

    def test_archived_product_not_exposed(self):
        resp = key_client(self.raw_stock).get('/api/public/produits/')
        skus = [r['sku'] for r in rows(resp)]
        self.assertNotIn('OLD-1', skus)

    def test_cross_tenant_isolation(self):
        resp = key_client(self.raw_stock).get('/api/public/produits/')
        skus = [r['sku'] for r in rows(resp)]
        self.assertNotIn('OND-B', skus)

    def test_filter_by_sku(self):
        resp = key_client(self.raw_stock).get('/api/public/produits/?sku=PAN-450')
        skus = [r['sku'] for r in rows(resp)]
        self.assertEqual(skus, ['PAN-450'])

    def test_unknown_filter_is_400(self):
        resp = key_client(self.raw_stock).get('/api/public/produits/?prix_achat=1')
        self.assertEqual(resp.status_code, 400)


class StockThresholdWebhookTests(TestCase):
    """`stock.seuil_atteint` : émis UNE SEULE FOIS au franchissement à la
    baisse ; jamais redéclenché si déjà sous le seuil ; jamais à la remontée."""

    def setUp(self):
        self.co = make_company('pa-stk-wh', 'PA STK WH')
        self.produit = Produit.objects.create(
            company=self.co, nom='Onduleur 5kW', sku='OND-5K',
            prix_vente=5000, prix_achat=3000,
            quantite_stock=20, seuil_alerte=10,
        )
        self.hook = Webhook.objects.create(
            company=self.co, target_url='https://example.com/hook',
            secret='s3cret', events=[EVENT_STOCK_SEUIL_ATTEINT], enabled=True)

    def _mouvement(self, avant, apres):
        from apps.stock.services import record_stock_movement, mouvement_type_sortie
        return record_stock_movement(
            company=self.co, produit=self.produit,
            type_mouvement=mouvement_type_sortie(),
            quantite=avant - apres, quantite_avant=avant, quantite_apres=apres,
            reference='TEST', note='', created_by=None,
        )

    def test_crossing_below_threshold_dispatches_once(self):
        with mock.patch.object(delivery, 'dispatch_event') as m:
            self._mouvement(20, 8)  # 20 > 10 (seuil) ; 8 <= 10 → franchissement
        m.assert_called_once()
        args, _kwargs = m.call_args
        self.assertEqual(args[0], self.co.id)
        self.assertEqual(args[1], EVENT_STOCK_SEUIL_ATTEINT)
        self.assertEqual(args[2]['sku'], 'OND-5K')
        self.assertNotIn('prix_achat', args[2])
        self.assertNotIn('prix_vente', args[2])

    def test_already_below_threshold_does_not_redispatch(self):
        self.produit.quantite_stock = 8
        self.produit.save(update_fields=['quantite_stock'])
        with mock.patch.object(delivery, 'dispatch_event') as m:
            self._mouvement(8, 5)  # déjà sous le seuil avant ce mouvement
        m.assert_not_called()

    def test_restock_above_threshold_does_not_dispatch(self):
        with mock.patch.object(delivery, 'dispatch_event') as m:
            self._mouvement(5, 25)  # remontée, pas une baisse
        m.assert_not_called()

    def test_zero_threshold_disables_alert(self):
        self.produit.seuil_alerte = 0
        self.produit.save(update_fields=['seuil_alerte'])
        with mock.patch.object(delivery, 'dispatch_event') as m:
            self._mouvement(20, 0)
        m.assert_not_called()


class LivraisonLivreeWebhookTests(TestCase):
    """`livraison.livree` : POST /livraisons/{id}/livrer/ émet le webhook
    (best-effort) — company résolue serveur, jamais du body."""

    def setUp(self):
        from apps.crm.models import Client as CrmClient
        from apps.installations.models import Installation
        from apps.installations.models_livraison import Livraison

        self.co = make_company('pa-liv-wh', 'PA LIV WH')
        self.admin = make_user(self.co, 'liv-admin', role='admin')
        self.client_obj = CrmClient.objects.create(company=self.co, nom='Cli')
        self.installation = Installation.objects.create(
            company=self.co, reference='CH-LIV', client=self.client_obj)
        self.livraison = Livraison.objects.create(
            company=self.co, reference='LIV-1', installation=self.installation,
            numero_suivi='TRACK-1',
        )
        self.hook = Webhook.objects.create(
            company=self.co, target_url='https://example.com/hook',
            secret='s3cret', events=[EVENT_LIVRAISON_LIVREE], enabled=True)

    def test_livrer_dispatches_webhook(self):
        api = session_auth(self.admin)
        with mock.patch.object(delivery, 'dispatch_event') as m:
            resp = api.post(f'/api/django/installations/livraisons/{self.livraison.id}/livrer/')
        self.assertEqual(resp.status_code, 200)
        m.assert_any_call(
            self.co.id, EVENT_LIVRAISON_LIVREE,
            mock.ANY,
        )
        # Vérifie le contenu de l'appel dédié à livraison.livree (parmi
        # d'éventuels autres évènements XSTK22/notification déclenchés).
        matching = [c for c in m.call_args_list if c.args[1] == EVENT_LIVRAISON_LIVREE]
        self.assertEqual(len(matching), 1)
        payload = matching[0].args[2]
        self.assertEqual(payload['reference'], 'LIV-1')
        self.assertEqual(payload['numero_suivi'], 'TRACK-1')


# ── XPLT5 — API publique en ÉCRITURE (scopes write) + idempotence ───────────

class PublicWriteScopeTests(TestCase):
    """Une clé `leads:write` crée un lead ; une clé read-only → 403 ; jamais
    de fuite cross-tenant sur PATCH/activité."""

    def setUp(self):
        self.co_a = make_company('pa-w-a', 'PA W A')
        self.co_b = make_company('pa-w-b', 'PA W B')
        self.lead_a = Lead.objects.create(company=self.co_a, nom='Existant A')
        self.lead_b = Lead.objects.create(company=self.co_b, nom='Existant B')
        self.key_write, self.raw_write = ApiKey.issue(
            company=self.co_a, label='write',
            scopes=[SCOPE_WRITE_LEADS, SCOPE_WRITE_ACTIVITIES])
        self.key_ro, self.raw_ro = ApiKey.issue(
            company=self.co_a, label='ro', scopes=[SCOPE_READ_LEADS])

    def test_write_scoped_key_creates_lead(self):
        resp = key_client(self.raw_write).post(
            '/api/public/leads-write/', {'nom': 'Nouveau Lead'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['nom'], 'Nouveau Lead')
        self.assertTrue(
            Lead.objects.filter(company=self.co_a, nom='Nouveau Lead').exists())

    def test_read_only_key_is_403_on_write(self):
        resp = key_client(self.raw_ro).post(
            '/api/public/leads-write/', {'nom': 'Refusé'}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Lead.objects.filter(nom='Refusé').exists())

    def test_company_forced_from_key_not_body(self):
        # Même si le corps tentait de préciser une autre société, elle est
        # ignorée : `create_lead_from_public_api` ne lit jamais `company` du
        # payload — la vue le force depuis la clé.
        resp = key_client(self.raw_write).post(
            '/api/public/leads-write/',
            {'nom': 'Forcé', 'company': self.co_b.id}, format='json')
        self.assertEqual(resp.status_code, 201)
        lead = Lead.objects.get(nom='Forcé')
        self.assertEqual(lead.company_id, self.co_a.id)

    def test_missing_nom_is_400(self):
        resp = key_client(self.raw_write).post(
            '/api/public/leads-write/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_invalid_stage_is_400(self):
        resp = key_client(self.raw_write).post(
            '/api/public/leads-write/',
            {'nom': 'Mauvais stage', 'stage': 'NOT_A_STAGE'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_stage_from_stages_py_accepted(self):
        resp = key_client(self.raw_write).post(
            '/api/public/leads-write/',
            {'nom': 'Contacté direct', 'stage': 'CONTACTED'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['stage'], 'CONTACTED')

    def test_update_own_lead(self):
        resp = key_client(self.raw_write).patch(
            f'/api/public/leads-write/{self.lead_a.id}/',
            {'ville': 'Marrakech'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.lead_a.refresh_from_db()
        self.assertEqual(self.lead_a.ville, 'Marrakech')

    def test_update_cross_tenant_lead_is_404(self):
        resp = key_client(self.raw_write).patch(
            f'/api/public/leads-write/{self.lead_b.id}/',
            {'ville': 'Ailleurs'}, format='json')
        self.assertEqual(resp.status_code, 404)
        self.lead_b.refresh_from_db()
        self.assertNotEqual(self.lead_b.ville, 'Ailleurs')

    def test_create_activity_on_own_lead(self):
        resp = key_client(self.raw_write).post(
            f'/api/public/leads-write/{self.lead_a.id}/activites/',
            {'body': 'Appelé, intéressé.'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(
            self.lead_a.activites.filter(body='Appelé, intéressé.').exists())

    def test_create_activity_on_cross_tenant_lead_is_404(self):
        resp = key_client(self.raw_write).post(
            f'/api/public/leads-write/{self.lead_b.id}/activites/',
            {'body': 'Ne devrait pas passer.'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_create_activity_read_only_key_is_403(self):
        resp = key_client(self.raw_ro).post(
            f'/api/public/leads-write/{self.lead_a.id}/activites/',
            {'body': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_leads_write_scope_does_not_grant_activities_write(self):
        # Une clé qui n'a QUE leads:write ne peut pas créer d'activité.
        key_leads_only, raw_leads_only = ApiKey.issue(
            company=self.co_a, label='leads-only', scopes=[SCOPE_WRITE_LEADS])
        resp = key_client(raw_leads_only).post(
            f'/api/public/leads-write/{self.lead_a.id}/activites/',
            {'body': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)


class PublicWriteIdempotencyTests(TestCase):
    """`Idempotency-Key` : rejeu identique → même réponse, pas de doublon ;
    corps différent sous la même clé → 409 ; sans en-tête → comportement
    normal (toujours une nouvelle création)."""

    def setUp(self):
        self.co = make_company('pa-idem', 'PA IDEM')
        self.key, self.raw = ApiKey.issue(
            company=self.co, label='idem', scopes=[SCOPE_WRITE_LEADS])

    def _post(self, body, idem_key=None):
        api = key_client(self.raw)
        headers = {}
        if idem_key is not None:
            headers['HTTP_IDEMPOTENCY_KEY'] = idem_key
        return api.post('/api/public/leads-write/', body, format='json', **headers)

    def test_replay_same_key_same_body_no_duplicate(self):
        resp1 = self._post({'nom': 'Idem Lead'}, idem_key='abc-123')
        self.assertEqual(resp1.status_code, 201)
        resp2 = self._post({'nom': 'Idem Lead'}, idem_key='abc-123')
        self.assertEqual(resp2.status_code, 201)
        self.assertEqual(resp1.data['id'], resp2.data['id'])
        self.assertEqual(
            Lead.objects.filter(company=self.co, nom='Idem Lead').count(), 1)

    def test_replay_different_body_is_409(self):
        resp1 = self._post({'nom': 'Original'}, idem_key='dup-1')
        self.assertEqual(resp1.status_code, 201)
        resp2 = self._post({'nom': 'Différent'}, idem_key='dup-1')
        self.assertEqual(resp2.status_code, 409)
        self.assertFalse(Lead.objects.filter(nom='Différent').exists())

    def test_without_header_always_creates(self):
        resp1 = self._post({'nom': 'Sans Idem'})
        resp2 = self._post({'nom': 'Sans Idem'})
        self.assertEqual(resp1.status_code, 201)
        self.assertEqual(resp2.status_code, 201)
        self.assertNotEqual(resp1.data['id'], resp2.data['id'])
        self.assertEqual(
            Lead.objects.filter(company=self.co, nom='Sans Idem').count(), 2)

    def test_idempotency_scoped_per_key_not_global(self):
        # Une AUTRE clé de la même société avec la même Idempotency-Key crée
        # bien un second lead (l'idempotence est scopée par clé, pas globale).
        other_key, other_raw = ApiKey.issue(
            company=self.co, label='autre', scopes=[SCOPE_WRITE_LEADS])
        resp1 = self._post({'nom': 'Partagé'}, idem_key='shared-key')
        resp2 = key_client(other_raw).post(
            '/api/public/leads-write/', {'nom': 'Partagé'}, format='json',
            HTTP_IDEMPOTENCY_KEY='shared-key')
        self.assertEqual(resp1.status_code, 201)
        self.assertEqual(resp2.status_code, 201)
        self.assertNotEqual(resp1.data['id'], resp2.data['id'])
