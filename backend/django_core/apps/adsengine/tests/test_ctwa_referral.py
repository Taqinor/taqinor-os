"""ADSDEEP24 — Tests du récepteur webhook WhatsApp Cloud API (CTWA referral).

Prouve : GET verify renvoie hub.challenge ; sans jeton tout no-ope (404) ;
un POST signé avec un objet ``referral`` stocke un ``CtwaReferral`` (ad_id /
ctwa_clid extraits) et rattache le lead CRM par téléphone ; idempotent par
wa_message_id ; signature invalide → 403.

PUB27 — un referral SANS lead préalable auto-crée un Lead minimal (jamais un
referral orphelin qui perd son attribution par ad) ; dédupliqué par téléphone
(jamais de doublon) ; un referral AVEC lead existant reste inchangé.
"""
import hashlib
import hmac
import json

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from apps.adsengine.models import CtwaReferral

SECRET = 'app-secret-xyz'
VTOKEN = 'verify-token-abc'


def _sign(body_bytes, secret=SECRET):
    return 'sha256=' + hmac.new(
        secret.encode(), body_bytes, hashlib.sha256).hexdigest()


def _referral_payload(wa_message_id='wamid.1', phone='212612345678',
                      source_id='ad-777', ctwa_clid='clid-999'):
    return {'object': 'whatsapp_business_account', 'entry': [{'changes': [{
        'field': 'messages', 'value': {'messaging_product': 'whatsapp',
            'messages': [{
                'from': phone, 'id': wa_message_id, 'timestamp': '1690000000',
                'type': 'text', 'text': {'body': 'Bonjour'},
                'referral': {
                    'source_id': source_id, 'source_type': 'ad',
                    'headline': 'Panneaux solaires -30%',
                    'ctwa_clid': ctwa_clid},
            }]}}]}]}


class NoConfigNoOpTests(TestCase):
    """Sans jeton configuré : GET et POST no-opent proprement (404)."""

    def test_get_without_env_is_404(self):
        url = reverse('adsengine-whatsapp-webhook')
        resp = self.client.get(url, {'hub.mode': 'subscribe',
                                     'hub.verify_token': 'x',
                                     'hub.challenge': '123'})
        self.assertEqual(resp.status_code, 404)

    def test_post_without_env_is_404_no_write(self):
        url = reverse('adsengine-whatsapp-webhook')
        body = json.dumps(_referral_payload())
        resp = self.client.post(
            url, data=body, content_type='application/json')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(CtwaReferral.objects.count(), 0)


@override_settings(
    WHATSAPP_CLOUD_VERIFY_TOKEN=VTOKEN, WHATSAPP_CLOUD_APP_SECRET=SECRET)
class WebhookTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CTWA Co', slug='ctwa')

    def _post_signed(self, payload):
        url = reverse('adsengine-whatsapp-webhook')
        body = json.dumps(payload).encode('utf-8')
        return self.client.post(
            url, data=body, content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=_sign(body))

    def test_get_verify_returns_challenge(self):
        url = reverse('adsengine-whatsapp-webhook')
        resp = self.client.get(url, {'hub.mode': 'subscribe',
                                     'hub.verify_token': VTOKEN,
                                     'hub.challenge': 'CHALLENGE-42'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode(), 'CHALLENGE-42')

    def test_get_verify_wrong_token_403(self):
        url = reverse('adsengine-whatsapp-webhook')
        resp = self.client.get(url, {'hub.mode': 'subscribe',
                                     'hub.verify_token': 'wrong',
                                     'hub.challenge': 'x'})
        self.assertEqual(resp.status_code, 403)

    def test_post_stores_referral(self):
        resp = self._post_signed(_referral_payload())
        self.assertEqual(resp.status_code, 200, resp.content)
        ref = CtwaReferral.objects.get(
            company=self.company, wa_message_id='wamid.1')
        self.assertEqual(ref.ad_id, 'ad-777')
        self.assertEqual(ref.ctwa_clid, 'clid-999')
        self.assertEqual(ref.source_type, 'ad')
        self.assertTrue(ref.phone_key)
        self.assertIsNotNone(ref.ts)

    def test_post_attaches_crm_lead_by_phone(self):
        from apps.crm.models import Lead
        lead = Lead.objects.create(
            company=self.company, nom='Bennani', telephone='0612345678')
        resp = self._post_signed(_referral_payload(phone='212612345678'))
        self.assertEqual(resp.status_code, 200, resp.content)
        ref = CtwaReferral.objects.get(
            company=self.company, wa_message_id='wamid.1')
        self.assertEqual(ref.crm_lead_id, lead.id)

    def test_post_idempotent_same_message(self):
        payload = _referral_payload(wa_message_id='wamid.dup')
        self._post_signed(payload)
        self._post_signed(payload)
        self.assertEqual(
            CtwaReferral.objects.filter(
                company=self.company, wa_message_id='wamid.dup').count(), 1)

    def test_post_invalid_signature_403(self):
        url = reverse('adsengine-whatsapp-webhook')
        body = json.dumps(_referral_payload()).encode('utf-8')
        resp = self.client.post(
            url, data=body, content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256='sha256=deadbeef')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(CtwaReferral.objects.count(), 0)

    def test_post_message_without_referral_ignored(self):
        payload = {'entry': [{'changes': [{'value': {'messages': [{
            'from': '212611111111', 'id': 'wamid.noref', 'type': 'text',
            'text': {'body': 'hi'}}]}}]}]}
        resp = self._post_signed(payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(CtwaReferral.objects.count(), 0)

    # ── PUB27 — auto-création d'un Lead minimal quand le referral est orphelin ──

    def test_referral_without_lead_auto_creates_minimal_lead(self):
        from apps.crm.models import Lead

        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)
        resp = self._post_signed(_referral_payload(
            wa_message_id='wamid.pub27a', phone='212699887766',
            source_id='ad-pub27'))
        self.assertEqual(resp.status_code, 200, resp.content)

        ref = CtwaReferral.objects.get(
            company=self.company, wa_message_id='wamid.pub27a')
        self.assertIsNotNone(ref.crm_lead_id)
        lead = Lead.objects.get(pk=ref.crm_lead_id, company=self.company)
        self.assertEqual(lead.canal, Lead.Canal.WHATSAPP_CTWA)
        self.assertEqual(lead.meta_ad_id, 'ad-pub27')
        self.assertTrue(lead.telephone)

    def test_referral_without_lead_never_duplicates_on_replay(self):
        """Deux messages CTWA distincts du MÊME numéro (dédup téléphone,
        jamais un doublon) n'auto-créent qu'UN seul lead."""
        from apps.crm.models import Lead

        self._post_signed(_referral_payload(
            wa_message_id='wamid.pub27b1', phone='212655443322'))
        self._post_signed(_referral_payload(
            wa_message_id='wamid.pub27b2', phone='212655443322'))
        self.assertEqual(
            Lead.objects.filter(
                company=self.company, canal=Lead.Canal.WHATSAPP_CTWA).count(),
            1)
        ref1 = CtwaReferral.objects.get(
            company=self.company, wa_message_id='wamid.pub27b1')
        ref2 = CtwaReferral.objects.get(
            company=self.company, wa_message_id='wamid.pub27b2')
        self.assertEqual(ref1.crm_lead_id, ref2.crm_lead_id)

    def test_referral_with_existing_lead_behaviour_unchanged(self):
        """PUB27 ne touche jamais le chemin « lead déjà trouvé » (rien de
        nouveau écrit sur le lead existant)."""
        from apps.crm.models import Lead

        lead = Lead.objects.create(
            company=self.company, nom='Déjà Connu',
            telephone='0612340000', canal=Lead.Canal.TELEPHONE)
        resp = self._post_signed(_referral_payload(
            wa_message_id='wamid.pub27c', phone='212612340000'))
        self.assertEqual(resp.status_code, 200, resp.content)
        ref = CtwaReferral.objects.get(
            company=self.company, wa_message_id='wamid.pub27c')
        self.assertEqual(ref.crm_lead_id, lead.id)
        lead.refresh_from_db()
        # Canal du lead existant préservé (jamais réécrit par le referral).
        self.assertEqual(lead.canal, Lead.Canal.TELEPHONE)
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), 1)
