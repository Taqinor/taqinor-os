"""Tests QJ23 — WhatsApp BSP provider scaffold (flag-gated, defaut manuel wa.me).

Couverture :
  (a) flag OFF (WHATSAPP_BSP_ENABLED absent / != '1') :
      - get_whatsapp_provider() renvoie ManualWaMeProvider.
      - get_wa_url retourne un lien wa.me bien forme et aucun appel reseau.

  (b) flag ON + credentials manquants :
      - BspProvider() tombe en repli manuel, aucun crash, aucun appel reseau.

  (c) flag ON + credentials presents :
      - get_whatsapp_provider() renvoie BspProvider.
      - get_wa_url tombe en repli manuel (live send non active), aucun crash.

  (d) Webhook GET — handshake :
      - 403 si WHATSAPP_BSP_VERIFY_TOKEN non configure.
      - 403 si token incorrect.
      - 200 + challenge si token correct.

  (e) Webhook POST — signature :
      - 403 si WHATSAPP_BSP_APP_SECRET configure et signature absente.
      - 403 si WHATSAPP_BSP_APP_SECRET configure et signature incorrecte.
      - 200 si WHATSAPP_BSP_APP_SECRET configure et signature correcte.
      - 200 (avec warning) si WHATSAPP_BSP_APP_SECRET non configure (scaffold).

  (f) Webhook POST — parsing de statuts :
      - Un payload delivered/read met a jour WhatsAppMessageLog (no live call).

  (g) Modeles WhatsAppTemplate et WhatsAppMessageLog :
      - company forcee cote serveur, jamais du corps.
      - unique_together sur (company, name, language).
      - WhatsAppMessageLog pointe sur template nullable.

Aucun test ne fait d'appel reseau reel.
"""
import hashlib
import hmac
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from authentication.models import Company

from .models import WhatsAppMessageLog, WhatsAppTemplate
from .whatsapp_bsp import (
    BspProvider,
    ManualWaMeProvider,
    get_whatsapp_provider,
)

User = get_user_model()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_company(name="TestCo"):
    return Company.objects.create(nom=name)


def _make_user(company, username="user1"):
    return User.objects.create_user(
        username=username, password="pw", company=company
    )


def _sign_body(body_bytes, secret):
    sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    return "sha256=" + sig


# ---------------------------------------------------------------------------
# (a) Flag OFF — comportement par defaut
# ---------------------------------------------------------------------------

class ProviderFlagOffTests(TestCase):
    """Sans WHATSAPP_BSP_ENABLED, le provider est toujours ManualWaMeProvider."""

    def test_factory_returns_manual_when_flag_unset(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            # S'assurer que la cle n'existe pas.
            import os
            os.environ.pop("WHATSAPP_BSP_ENABLED", None)
            provider = get_whatsapp_provider()
        self.assertIsInstance(provider, ManualWaMeProvider)

    @override_settings()
    def test_factory_returns_manual_when_flag_zero(self):
        with mock.patch.dict("os.environ", {"WHATSAPP_BSP_ENABLED": "0"}):
            provider = get_whatsapp_provider()
        self.assertIsInstance(provider, ManualWaMeProvider)

    def test_manual_provider_returns_wa_url_no_network_call(self):
        """ManualWaMeProvider construit un lien wa.me sans aucun appel reseau."""
        provider = ManualWaMeProvider()
        with mock.patch("urllib.request.urlopen") as mock_open:
            result = provider.get_wa_url("+212600000001", "Bonjour")
        mock_open.assert_not_called()
        self.assertEqual(result["provider"], "manual")
        url = result["url"]
        self.assertIsNotNone(url)
        self.assertIn("wa.me", url)
        self.assertIn("Bonjour", url)

    def test_manual_provider_returns_none_for_invalid_phone(self):
        provider = ManualWaMeProvider()
        result = provider.get_wa_url("", "Message")
        self.assertEqual(result["provider"], "manual")
        self.assertIsNone(result["url"])


# ---------------------------------------------------------------------------
# (b) Flag ON + credentials manquants -> repli manuel, aucun crash
# ---------------------------------------------------------------------------

class ProviderFlagOnNoCredsTests(TestCase):
    """Avec WHATSAPP_BSP_ENABLED=1 mais sans credentials, repli sur manuel."""

    def test_factory_returns_manual_when_creds_missing(self):
        with mock.patch.dict("os.environ", {
            "WHATSAPP_BSP_ENABLED": "1",
            "WHATSAPP_BSP_BASE_URL": "",
            "WHATSAPP_BSP_TOKEN": "",
            "WHATSAPP_BSP_PHONE_NUMBER_ID": "",
        }):
            provider = get_whatsapp_provider()
        self.assertIsInstance(provider, ManualWaMeProvider)

    def test_factory_returns_manual_when_partial_creds(self):
        """Meme si une seule credential manque -> repli manuel."""
        with mock.patch.dict("os.environ", {
            "WHATSAPP_BSP_ENABLED": "1",
            "WHATSAPP_BSP_BASE_URL": "https://graph.facebook.com/v19.0",
            "WHATSAPP_BSP_TOKEN": "mytoken",
            "WHATSAPP_BSP_PHONE_NUMBER_ID": "",  # manquant
        }):
            provider = get_whatsapp_provider()
        self.assertIsInstance(provider, ManualWaMeProvider)

    def test_bsp_provider_with_empty_token_falls_back_to_manual(self):
        """BspProvider construit avec token vide -> repli manuel, aucun crash."""
        provider = BspProvider(
            base_url="https://graph.facebook.com/v19.0",
            token="",
            phone_number_id="",
        )
        with mock.patch("urllib.request.urlopen") as mock_open:
            result = provider.get_wa_url("+212600000001", "Bonjour")
        mock_open.assert_not_called()
        self.assertEqual(result["provider"], "manual")


# ---------------------------------------------------------------------------
# (c) Flag ON + credentials complets -> BspProvider (repli manuel jusqu'a live)
# ---------------------------------------------------------------------------

class ProviderFlagOnWithCredsTests(TestCase):
    """Avec WHATSAPP_BSP_ENABLED=1 + tous les credentials -> BspProvider."""

    def test_factory_returns_bsp_provider_when_all_creds_present(self):
        with mock.patch.dict("os.environ", {
            "WHATSAPP_BSP_ENABLED": "1",
            "WHATSAPP_BSP_BASE_URL": "https://graph.facebook.com/v19.0",
            "WHATSAPP_BSP_TOKEN": "mytoken",
            "WHATSAPP_BSP_PHONE_NUMBER_ID": "1234567890",
        }):
            provider = get_whatsapp_provider()
        self.assertIsInstance(provider, BspProvider)

    def test_bsp_provider_falls_back_to_manual_no_network_call(self):
        """Meme avec credentials complets, BspProvider tombe en repli manuel
        (live send non active dans le scaffold) sans aucun appel reseau."""
        provider = BspProvider(
            base_url="https://graph.facebook.com/v19.0",
            token="mytoken",
            phone_number_id="1234567890",
        )
        with mock.patch("urllib.request.urlopen") as mock_open:
            result = provider.get_wa_url("+212600000001", "Test")
        mock_open.assert_not_called()
        # Le scaffold tombe en repli manuel (TODO decommenter _send_via_api).
        self.assertEqual(result["provider"], "manual")


# ---------------------------------------------------------------------------
# (d) Webhook GET — handshake de verification Meta
# ---------------------------------------------------------------------------

class WebhookGetTests(TestCase):
    """Tests du GET verify handshake (Meta hub.mode=subscribe)."""

    def setUp(self):
        self.factory = RequestFactory()

    def _get(self, params):
        from .views_whatsapp_bsp import WhatsAppBspWebhookView
        request = self.factory.get("/fake/webhook/", params)
        return WhatsAppBspWebhookView.as_view()(request)

    def test_get_returns_403_when_verify_token_not_configured(self):
        with mock.patch.dict("os.environ", {"WHATSAPP_BSP_VERIFY_TOKEN": ""}):
            resp = self._get({
                "hub.mode": "subscribe",
                "hub.verify_token": "anything",
                "hub.challenge": "abc123",
            })
        self.assertEqual(resp.status_code, 403)

    def test_get_returns_403_when_wrong_token(self):
        with mock.patch.dict("os.environ", {"WHATSAPP_BSP_VERIFY_TOKEN": "secret123"}):
            resp = self._get({
                "hub.mode": "subscribe",
                "hub.verify_token": "wrongtoken",
                "hub.challenge": "abc123",
            })
        self.assertEqual(resp.status_code, 403)

    def test_get_returns_403_when_mode_not_subscribe(self):
        with mock.patch.dict("os.environ", {"WHATSAPP_BSP_VERIFY_TOKEN": "secret123"}):
            resp = self._get({
                "hub.mode": "unsubscribe",
                "hub.verify_token": "secret123",
                "hub.challenge": "abc123",
            })
        self.assertEqual(resp.status_code, 403)

    def test_get_returns_challenge_on_valid_token(self):
        with mock.patch.dict("os.environ", {"WHATSAPP_BSP_VERIFY_TOKEN": "secret123"}):
            resp = self._get({
                "hub.mode": "subscribe",
                "hub.verify_token": "secret123",
                "hub.challenge": "mychallenge",
            })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"mychallenge")


# ---------------------------------------------------------------------------
# (e) Webhook POST — validation de signature
# ---------------------------------------------------------------------------

class WebhookPostSignatureTests(TestCase):
    """Tests de la validation de signature HMAC sur le webhook POST."""

    def setUp(self):
        self.factory = RequestFactory()

    def _post(self, body, extra_headers=None, env_overrides=None):
        from .views_whatsapp_bsp import WhatsAppBspWebhookView
        kwargs = {"content_type": "application/json"}
        if extra_headers:
            kwargs.update(extra_headers)
        request = self.factory.post("/fake/webhook/", body, **kwargs)
        env = env_overrides or {}
        with mock.patch.dict("os.environ", env):
            resp = WhatsAppBspWebhookView.as_view()(request)
        return resp

    def test_post_returns_403_when_secret_set_and_signature_absent(self):
        body = b'{"entry": []}'
        resp = self._post(
            body,
            env_overrides={"WHATSAPP_BSP_APP_SECRET": "mysecret"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_post_returns_403_when_signature_invalid(self):
        body = b'{"entry": []}'
        resp = self._post(
            body,
            extra_headers={"HTTP_X_HUB_SIGNATURE_256": "sha256=badsignature"},
            env_overrides={"WHATSAPP_BSP_APP_SECRET": "mysecret"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_post_returns_200_when_signature_valid(self):
        body = b'{"entry": []}'
        sig = _sign_body(body, "mysecret")
        resp = self._post(
            body,
            extra_headers={"HTTP_X_HUB_SIGNATURE_256": sig},
            env_overrides={"WHATSAPP_BSP_APP_SECRET": "mysecret"},
        )
        self.assertEqual(resp.status_code, 200)

    def test_post_returns_200_when_no_secret_configured(self):
        """Sans WHATSAPP_BSP_APP_SECRET, le webhook accepte (scaffold non securise)."""
        body = b'{"entry": []}'
        resp = self._post(body, env_overrides={"WHATSAPP_BSP_APP_SECRET": ""})
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# (f) Webhook POST — parsing de statuts et mise a jour du log
# ---------------------------------------------------------------------------

class WebhookPostStatusParsingTests(TestCase):
    """Tests du parsing des callbacks de statut et de la mise a jour du log."""

    def setUp(self):
        self.factory = RequestFactory()
        self.company = _make_company("WebhookCo")

    def _post_payload(self, payload_dict, env_overrides=None):
        from .views_whatsapp_bsp import WhatsAppBspWebhookView
        body = json.dumps(payload_dict).encode()
        request = self.factory.post(
            "/fake/webhook/", body, content_type="application/json"
        )
        env = env_overrides or {"WHATSAPP_BSP_APP_SECRET": ""}
        with mock.patch.dict("os.environ", env):
            resp = WhatsAppBspWebhookView.as_view()(request)
        return resp

    def _make_log(self, external_id, status=WhatsAppMessageLog.Status.SENT):
        return WhatsAppMessageLog.objects.create(
            company=self.company,
            recipient="212600000001",
            body="Test message",
            status=status,
            provider=WhatsAppMessageLog.Provider.BSP,
            external_id=external_id,
        )

    def test_delivered_status_updates_log(self):
        log = self._make_log("wamid.testdelivered001")
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "statuses": [{
                            "id": "wamid.testdelivered001",
                            "status": "delivered",
                            "timestamp": "1719000000",
                            "recipient_id": "212600000001",
                        }]
                    }
                }]
            }]
        }
        resp = self._post_payload(payload)
        self.assertEqual(resp.status_code, 200)
        log.refresh_from_db()
        self.assertEqual(log.status, WhatsAppMessageLog.Status.DELIVERED)

    def test_read_status_updates_log(self):
        log = self._make_log("wamid.testread001", WhatsAppMessageLog.Status.DELIVERED)
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "statuses": [{
                            "id": "wamid.testread001",
                            "status": "read",
                            "timestamp": "1719000001",
                            "recipient_id": "212600000001",
                        }]
                    }
                }]
            }]
        }
        resp = self._post_payload(payload)
        self.assertEqual(resp.status_code, 200)
        log.refresh_from_db()
        self.assertEqual(log.status, WhatsAppMessageLog.Status.READ)

    def test_unknown_external_id_ignored_no_crash(self):
        """Un external_id inconnu est simplement ignore (0 update), aucun crash."""
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "statuses": [{
                            "id": "wamid.nonexistent",
                            "status": "delivered",
                            "timestamp": "1719000002",
                        }]
                    }
                }]
            }]
        }
        resp = self._post_payload(payload)
        self.assertEqual(resp.status_code, 200)

    def test_empty_payload_returns_200(self):
        resp = self._post_payload({})
        self.assertEqual(resp.status_code, 200)

    def test_invalid_json_returns_400(self):
        from .views_whatsapp_bsp import WhatsAppBspWebhookView
        request = self.factory.post(
            "/fake/webhook/", b"not-json", content_type="application/json"
        )
        with mock.patch.dict("os.environ", {"WHATSAPP_BSP_APP_SECRET": ""}):
            resp = WhatsAppBspWebhookView.as_view()(request)
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# (g) Modeles WhatsAppTemplate et WhatsAppMessageLog
# ---------------------------------------------------------------------------

class WhatsAppModelsTests(TestCase):
    """Tests des modeles WhatsAppTemplate et WhatsAppMessageLog."""

    def setUp(self):
        self.company = _make_company("ModelCo")
        self.company2 = _make_company("ModelCo2")

    def test_template_created_with_company(self):
        tpl = WhatsAppTemplate.objects.create(
            company=self.company,
            name="devis_envoye_v1",
            body_fr="Bonjour {nom}, voici votre devis.",
            language="fr",
        )
        self.assertEqual(tpl.company, self.company)
        self.assertTrue(tpl.active)

    def test_template_unique_together_company_name_language(self):
        from django.db import IntegrityError
        WhatsAppTemplate.objects.create(
            company=self.company, name="tpl_test", language="fr"
        )
        with self.assertRaises(IntegrityError):
            WhatsAppTemplate.objects.create(
                company=self.company, name="tpl_test", language="fr"
            )

    def test_template_same_name_different_company_allowed(self):
        WhatsAppTemplate.objects.create(
            company=self.company, name="tpl_test", language="fr"
        )
        # Ne doit pas lever d'erreur.
        tpl2 = WhatsAppTemplate.objects.create(
            company=self.company2, name="tpl_test", language="fr"
        )
        self.assertEqual(tpl2.company, self.company2)

    def test_message_log_default_status_manual(self):
        log = WhatsAppMessageLog.objects.create(
            company=self.company,
            recipient="212600000001",
            body="Test",
        )
        self.assertEqual(log.status, WhatsAppMessageLog.Status.MANUAL)
        self.assertEqual(log.provider, WhatsAppMessageLog.Provider.MANUAL)

    def test_message_log_with_bsp_template(self):
        tpl = WhatsAppTemplate.objects.create(
            company=self.company, name="tpl_bsp", language="fr"
        )
        log = WhatsAppMessageLog.objects.create(
            company=self.company,
            recipient="212600000002",
            template=tpl,
            status=WhatsAppMessageLog.Status.SENT,
            provider=WhatsAppMessageLog.Provider.BSP,
            external_id="wamid.xyz",
        )
        self.assertEqual(log.template, tpl)
        self.assertEqual(log.external_id, "wamid.xyz")

    def test_message_log_template_nullable(self):
        """template=None est autorise (messages libres ou manuels)."""
        log = WhatsAppMessageLog.objects.create(
            company=self.company,
            recipient="212600000003",
            template=None,
        )
        self.assertIsNone(log.template)

    def test_message_log_scoped_per_company(self):
        """Les logs d'une societe ne sont pas visibles par une autre."""
        WhatsAppMessageLog.objects.create(
            company=self.company, recipient="212600000004"
        )
        WhatsAppMessageLog.objects.create(
            company=self.company2, recipient="212600000005"
        )
        self.assertEqual(
            WhatsAppMessageLog.objects.filter(company=self.company).count(), 1
        )
        self.assertEqual(
            WhatsAppMessageLog.objects.filter(company=self.company2).count(), 1
        )


# ---------------------------------------------------------------------------
# XMKT25 — Cycle d'approbation Meta des gabarits WhatsApp + variantes langue
# ---------------------------------------------------------------------------

class TemplateApprovalCycleTests(TestCase):
    """Statut par gabarit+langue, sélection restreinte aux approuvés,
    soumission gated (no-op sans jeton BSP)."""

    def setUp(self):
        self.company = _make_company("ApprovalCo")

    def test_default_statut_is_brouillon(self):
        tpl = WhatsAppTemplate.objects.create(
            company=self.company, name="devis_envoye", language="fr")
        self.assertEqual(
            tpl.statut_approbation, WhatsAppTemplate.StatutApprobation.BROUILLON)
        self.assertFalse(tpl.is_approuve)

    def test_language_variants_of_same_name_tracked_independently(self):
        """fr/ar du même nom logique : statuts indépendants par langue."""
        from .services import set_template_approval_status

        fr = WhatsAppTemplate.objects.create(
            company=self.company, name="devis_envoye", language="fr",
            groupe="devis_envoye")
        ar = WhatsAppTemplate.objects.create(
            company=self.company, name="devis_envoye", language="ar",
            groupe="devis_envoye")
        set_template_approval_status(
            fr, WhatsAppTemplate.StatutApprobation.APPROUVE)
        fr.refresh_from_db()
        ar.refresh_from_db()
        self.assertTrue(fr.is_approuve)
        self.assertFalse(ar.is_approuve)

    def test_submit_is_noop_without_bsp_credentials(self):
        """Sans WHATSAPP_BSP_ENABLED/credentials, submit reste fonctionnel
        (statut posé à 'soumis' pour saisie manuelle) mais AUCUN appel réseau."""
        from .services import submit_template_for_approval

        tpl = WhatsAppTemplate.objects.create(
            company=self.company, name="relance_devis", language="fr")
        with mock.patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("WHATSAPP_BSP_ENABLED", None)
            result = submit_template_for_approval(tpl)
        self.assertEqual(
            result.statut_approbation, WhatsAppTemplate.StatutApprobation.SOUMIS)

    def test_submit_idempotent_when_already_decided(self):
        """Un gabarit déjà approuvé/rejeté n'est pas re-soumis."""
        from .services import submit_template_for_approval

        tpl = WhatsAppTemplate.objects.create(
            company=self.company, name="devis_envoye2", language="fr",
            statut_approbation=WhatsAppTemplate.StatutApprobation.APPROUVE)
        result = submit_template_for_approval(tpl)
        self.assertEqual(
            result.statut_approbation, WhatsAppTemplate.StatutApprobation.APPROUVE)

    def test_set_template_approval_status_rejete_records_motif(self):
        from .services import set_template_approval_status

        tpl = WhatsAppTemplate.objects.create(
            company=self.company, name="devis_envoye3", language="fr")
        set_template_approval_status(
            tpl, WhatsAppTemplate.StatutApprobation.REJETE,
            motif_rejet="Corps du message non conforme.")
        tpl.refresh_from_db()
        self.assertEqual(
            tpl.statut_approbation, WhatsAppTemplate.StatutApprobation.REJETE)
        self.assertEqual(tpl.motif_rejet, "Corps du message non conforme.")

    def test_set_template_approval_status_rejects_unknown_statut(self):
        from .services import set_template_approval_status

        tpl = WhatsAppTemplate.objects.create(
            company=self.company, name="devis_envoye4", language="fr")
        result = set_template_approval_status(tpl, "invalide")
        self.assertEqual(
            result.statut_approbation, WhatsAppTemplate.StatutApprobation.BROUILLON)

    def test_approved_templates_for_only_returns_approved_active(self):
        """Une campagne ne peut choisir qu'un gabarit approuvé — le sélecteur
        service ne renvoie QUE statut=approuve ET active=True."""
        from .services import approved_templates_for

        WhatsAppTemplate.objects.create(
            company=self.company, name="draft_tpl", language="fr")
        WhatsAppTemplate.objects.create(
            company=self.company, name="rejected_tpl", language="fr",
            statut_approbation=WhatsAppTemplate.StatutApprobation.REJETE)
        approved = WhatsAppTemplate.objects.create(
            company=self.company, name="approved_tpl", language="fr",
            statut_approbation=WhatsAppTemplate.StatutApprobation.APPROUVE)
        inactive_approved = WhatsAppTemplate.objects.create(
            company=self.company, name="inactive_approved_tpl", language="fr",
            statut_approbation=WhatsAppTemplate.StatutApprobation.APPROUVE,
            active=False)

        selectable = list(approved_templates_for(self.company))
        self.assertIn(approved, selectable)
        self.assertNotIn(inactive_approved, selectable)
        self.assertEqual(len(selectable), 1)

    def test_approved_templates_for_filters_by_groupe(self):
        from .services import approved_templates_for

        fr = WhatsAppTemplate.objects.create(
            company=self.company, name="devis_envoye5", language="fr",
            groupe="devis_envoye5",
            statut_approbation=WhatsAppTemplate.StatutApprobation.APPROUVE)
        WhatsAppTemplate.objects.create(
            company=self.company, name="autre_tpl", language="fr",
            groupe="autre_groupe",
            statut_approbation=WhatsAppTemplate.StatutApprobation.APPROUVE)

        selectable = list(approved_templates_for(
            self.company, event_key="devis_envoye5"))
        self.assertEqual(selectable, [fr])

    def test_approved_templates_scoped_per_company(self):
        from .services import approved_templates_for

        other = _make_company("OtherApprovalCo")
        WhatsAppTemplate.objects.create(
            company=other, name="cross_tenant_tpl", language="fr",
            statut_approbation=WhatsAppTemplate.StatutApprobation.APPROUVE)
        self.assertEqual(list(approved_templates_for(self.company)), [])


class WhatsAppTemplateViewSetApiTests(TestCase):
    """Endpoints submit/decision : gated côté service, admin only en écriture."""

    def setUp(self):
        self.company = _make_company("ApiApprovalCo")
        self.admin = User.objects.create_user(
            username="admin1", password="pw", company=self.company,
            role_legacy="admin")

    def test_submit_action_moves_to_soumis(self):
        from rest_framework.test import APIClient

        tpl = WhatsAppTemplate.objects.create(
            company=self.company, name="api_submit_tpl", language="fr")
        client = APIClient()
        client.force_authenticate(self.admin)
        resp = client.post(
            f"/api/django/notifications/whatsapp-templates/{tpl.pk}/submit/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["statut_approbation"], "soumis")

    def test_decision_action_sets_approved(self):
        from rest_framework.test import APIClient

        tpl = WhatsAppTemplate.objects.create(
            company=self.company, name="api_decision_tpl", language="fr",
            statut_approbation=WhatsAppTemplate.StatutApprobation.SOUMIS)
        client = APIClient()
        client.force_authenticate(self.admin)
        resp = client.post(
            f"/api/django/notifications/whatsapp-templates/{tpl.pk}/decision/",
            {"statut_approbation": "approuve"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["statut_approbation"], "approuve")
