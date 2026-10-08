"""APAR22 - webhook WhatsApp BSP entrant idempotent (wamid unique, statut monotone)."""
import hashlib
import hmac
import json
import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client as HttpClient
from django.test import TestCase, override_settings

from authentication.models import Company

from .models import WhatsAppInboundMessage, WhatsAppMessageLog

SECRET = "apar22-secret"
URL = "/api/django/notifications/whatsapp/webhook/"


def _post(client, payload):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post(URL, data=body, content_type="application/json",
                       HTTP_X_HUB_SIGNATURE_256=sig)


def _msg_payload(wamid):
    return {"entry": [{"changes": [{"value": {
        "contacts": [{"profile": {"name": "X"}, "wa_id": "212600000001"}],
        "messages": [{"id": wamid, "from": "212600000001",
                      "type": "text", "text": {"body": "Bonjour"}}],
    }}]}]}


def _status_payload(wamid, status):
    return {"entry": [{"changes": [{"value": {
        "statuses": [{"id": wamid, "status": status}]}}]}]}


@override_settings(WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN="tok")
class BspIdempotentTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom="ApAr22Co")
        get_user_model()  # garde: modele utilisateur charge
        self.http = HttpClient()
        env = {"WHATSAPP_BSP_APP_SECRET": SECRET,
               "WHATSAPP_BSP_COMPANY_ID": str(self.company.pk)}
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)

    def test_meme_wamid_route_une_seule_fois(self):
        with mock.patch(
                "apps.sav.services.router_whatsapp_entrant_vers_ticket",
                return_value=(None, None)) as routeur:
            r1 = _post(self.http, _msg_payload("wamid.A"))
            r2 = _post(self.http, _msg_payload("wamid.A"))
        self.assertEqual((r1.status_code, r2.status_code), (200, 200))
        self.assertEqual(routeur.call_count, 1)
        self.assertEqual(WhatsAppInboundMessage.objects.filter(
            company=self.company, wa_message_id="wamid.A").count(), 1)

    def test_wamid_distincts_routes_deux_fois(self):
        with mock.patch(
                "apps.sav.services.router_whatsapp_entrant_vers_ticket",
                return_value=(None, None)) as routeur:
            _post(self.http, _msg_payload("wamid.B1"))
            _post(self.http, _msg_payload("wamid.B2"))
        self.assertEqual(routeur.call_count, 2)

    def test_echec_routage_libere_le_marqueur(self):
        with mock.patch(
                "apps.sav.services.router_whatsapp_entrant_vers_ticket",
                side_effect=RuntimeError("boom")):
            _post(self.http, _msg_payload("wamid.C"))
        self.assertFalse(WhatsAppInboundMessage.objects.filter(
            wa_message_id="wamid.C").exists())

    def test_statut_ne_regresse_jamais(self):
        log = WhatsAppMessageLog.objects.create(
            company=self.company, recipient="212600000001",
            status=WhatsAppMessageLog.Status.SENT,
            provider=WhatsAppMessageLog.Provider.BSP, external_id="wamid.D")
        for statut, attendu in (("read", "read"), ("delivered", "read"),
                                ("sent", "read")):
            _post(self.http, _status_payload("wamid.D", statut))
            log.refresh_from_db()
            self.assertEqual(log.status, attendu)

    def test_failed_est_terminal(self):
        log = WhatsAppMessageLog.objects.create(
            company=self.company, recipient="212600000001",
            status=WhatsAppMessageLog.Status.SENT,
            provider=WhatsAppMessageLog.Provider.BSP, external_id="wamid.E")
        _post(self.http, _status_payload("wamid.E", "failed"))
        _post(self.http, _status_payload("wamid.E", "delivered"))
        log.refresh_from_db()
        self.assertEqual(log.status, "failed")
