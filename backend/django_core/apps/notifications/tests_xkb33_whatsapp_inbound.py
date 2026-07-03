"""XKB33 — WhatsApp entrant -> fil de l'enregistrement.

Couverture :
  - sans cle BSP webhook configuree : le webhook se comporte EXACTEMENT
    comme avant (statuts seulement) -- deja couvert par tests_whatsapp_bsp.
  - sans WHATSAPP_ENABLED/WHATSAPP_ACCESS_TOKEN (FG207 gate) : un message
    entrant Meta ne capture RIEN, ne touche AUCUN chatter, ne cree AUCUNE
    conversation Discuss -- NO-OP complet.
  - sans WHATSAPP_BSP_COMPANY_ID : NO-OP complet meme avec FG207 actif.
  - avec les deux cles : un message entrant est capture (FG207), rattache au
    chatter du lead existant (matching par numero) OU du lead cree par la
    capture, ET poste dans la conversation Discuss dediee.
  - toujours 200, jamais de crash sur payload malforme.
"""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from authentication.models import Company

from .models import WhatsAppMessageLog

User = get_user_model()


def _make_company(name="InboundCo"):
    return Company.objects.create(nom=name)


def _post_payload(payload_dict, env_overrides=None):
    from .views_whatsapp_bsp import WhatsAppBspWebhookView
    factory = RequestFactory()
    body = json.dumps(payload_dict).encode()
    request = factory.post(
        "/fake/webhook/", body, content_type="application/json")
    env = env_overrides or {}
    env.setdefault("WHATSAPP_BSP_APP_SECRET", "")
    with mock.patch.dict("os.environ", env, clear=False):
        return WhatsAppBspWebhookView.as_view()(request)


def _inbound_payload(wa_message_id="wamid.in001", from_number="212611111111",
                     name="Client Test", body="Bonjour, un devis svp"):
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{
                        "profile": {"name": name}, "wa_id": from_number,
                    }],
                    "messages": [{
                        "id": wa_message_id,
                        "from": from_number,
                        "type": "text",
                        "text": {"body": body},
                    }],
                }
            }]
        }]
    }


class InboundGatingTests(TestCase):
    """Sans les deux cles (FG207 + societe cible), rien ne change."""

    def setUp(self):
        self.company = _make_company()

    def test_no_op_without_whatsapp_enabled(self):
        """WHATSAPP_ENABLED absent -> aucune capture, toujours 200."""
        with override_settings(WHATSAPP_ENABLED=False):
            resp = _post_payload(
                _inbound_payload(),
                {"WHATSAPP_BSP_COMPANY_ID": str(self.company.pk)})
        self.assertEqual(resp.status_code, 200)
        from apps.compta.models import MessageWhatsAppEntrant
        self.assertEqual(MessageWhatsAppEntrant.objects.count(), 0)

    def test_no_op_without_company_id(self):
        """WHATSAPP_BSP_COMPANY_ID absent -> aucune capture meme avec FG207 actif."""
        with override_settings(
                WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN="tok"):
            resp = _post_payload(
                _inbound_payload(), {"WHATSAPP_BSP_COMPANY_ID": ""})
        self.assertEqual(resp.status_code, 200)
        from apps.compta.models import MessageWhatsAppEntrant
        self.assertEqual(MessageWhatsAppEntrant.objects.count(), 0)

    def test_status_only_payload_unaffected_by_gating(self):
        """Un payload de STATUT (pas de messages) continue de fonctionner
        exactement comme avant, meme avec le gate FG207 OFF."""
        log = WhatsAppMessageLog.objects.create(
            company=self.company, recipient="212600000009",
            status=WhatsAppMessageLog.Status.SENT,
            provider=WhatsAppMessageLog.Provider.BSP,
            external_id="wamid.statusonly")
        payload = {
            "entry": [{"changes": [{"value": {"statuses": [{
                "id": "wamid.statusonly", "status": "delivered",
            }]}}]}]
        }
        with override_settings(WHATSAPP_ENABLED=False):
            resp = _post_payload(payload)
        self.assertEqual(resp.status_code, 200)
        log.refresh_from_db()
        self.assertEqual(log.status, WhatsAppMessageLog.Status.DELIVERED)


class InboundCaptureAndRoutingTests(TestCase):
    """Avec les deux cles : capture FG207 + chatter + conversation Discuss."""

    def setUp(self):
        self.company = _make_company("RoutingCo")
        self.manager = User.objects.create_user(
            username="mgr1", password="pw", company=self.company,
            role_legacy="admin")

    def _env(self):
        return {"WHATSAPP_BSP_COMPANY_ID": str(self.company.pk)}

    def test_inbound_message_captured_via_fg207(self):
        from apps.compta.models import MessageWhatsAppEntrant
        with override_settings(
                WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN="tok"):
            resp = _post_payload(
                _inbound_payload(wa_message_id="wamid.cap001"), self._env())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            MessageWhatsAppEntrant.objects.filter(
                wa_message_id="wamid.cap001").count(), 1)

    def test_inbound_message_idempotent_by_wa_message_id(self):
        from apps.compta.models import MessageWhatsAppEntrant
        with override_settings(
                WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN="tok"):
            _post_payload(
                _inbound_payload(wa_message_id="wamid.idem001"), self._env())
            _post_payload(
                _inbound_payload(wa_message_id="wamid.idem001"), self._env())
        self.assertEqual(
            MessageWhatsAppEntrant.objects.filter(
                wa_message_id="wamid.idem001").count(), 1)

    def test_inbound_message_appears_on_existing_lead_chatter(self):
        """Un numero deja connu d'un lead existant rattache le message a SON
        chatter (matching par numero) plutot que de creer un doublon."""
        from apps.crm.models import Lead, LeadActivity

        lead = Lead.objects.create(
            company=self.company, nom="Client Existant",
            telephone="212622222222")
        with override_settings(
                WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN="tok"):
            resp = _post_payload(
                _inbound_payload(
                    wa_message_id="wamid.existing001",
                    from_number="212622222222",
                    body="Toujours interesse"),
                self._env())
        self.assertEqual(resp.status_code, 200)
        notes = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE)
        self.assertTrue(
            any("Toujours interesse" in (n.body or '') for n in notes))

    def test_inbound_message_posted_to_dedicated_conversation(self):
        from apps.chat.models import Conversation, Message

        with override_settings(
                WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN="tok"):
            resp = _post_payload(
                _inbound_payload(
                    wa_message_id="wamid.conv001",
                    from_number="212633333333",
                    name="Contact Discuss",
                    body="Salut equipe"),
                self._env())
        self.assertEqual(resp.status_code, 200)
        conv = Conversation.objects.filter(
            company=self.company, name__icontains="Contact Discuss").first()
        self.assertIsNotNone(conv)
        self.assertTrue(
            Message.objects.filter(
                conversation=conv, body__icontains="Salut equipe").exists())
        # Le manager de la societe est membre du canal (equipe voit le fil).
        self.assertTrue(
            conv.members.filter(user=self.manager).exists())

    def test_second_message_reuses_same_conversation(self):
        from apps.chat.models import Conversation

        with override_settings(
                WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN="tok"):
            _post_payload(
                _inbound_payload(
                    wa_message_id="wamid.dup001", from_number="212644444444",
                    name="Meme Contact", body="Premier message"),
                self._env())
            _post_payload(
                _inbound_payload(
                    wa_message_id="wamid.dup002", from_number="212644444444",
                    name="Meme Contact", body="Deuxieme message"),
                self._env())
        convs = Conversation.objects.filter(
            company=self.company, name__icontains="Meme Contact")
        self.assertEqual(convs.count(), 1)
        self.assertEqual(convs.first().messages.count(), 2)

    def test_malformed_inbound_payload_never_crashes(self):
        with override_settings(
                WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN="tok"):
            resp = _post_payload(
                {"entry": [{"changes": [{"value": {"messages": [{}]}}]}]},
                self._env())
        self.assertEqual(resp.status_code, 200)
