"""QJ23 — Webhook BSP WhatsApp (Meta Cloud API, flag-gated).

Deux endpoints publics (pas de session / JWT) :
  GET  /api/django/notifications/whatsapp/webhook/
       Handshake de vérification Meta : hub.mode=subscribe +
       hub.verify_token + hub.challenge. Renvoie hub.challenge si le
       verify_token correspond à WHATSAPP_BSP_VERIFY_TOKEN (env).
       Retourne 403 si non configuré ou token incorrect.

  POST /api/django/notifications/whatsapp/webhook/
       Reçoit les callbacks de statut (delivered / read) et les met à
       jour dans WhatsAppMessageLog (via external_id). Valide la
       signature X-Hub-Signature-256 contre WHATSAPP_BSP_APP_SECRET (env).
       Retourne 200 même si la signature est absente MAIS que
       WHATSAPP_BSP_APP_SECRET n'est pas configuré (mode non sécurisé
       explicite) — log d'avertissement.
       Retourne 403 si la signature est présente et incorrecte.
       Retourne 403 si WHATSAPP_BSP_APP_SECRET est configuré et la
       signature absente.

SÉCURITÉ :
  - Si WHATSAPP_BSP_VERIFY_TOKEN n'est pas défini → GET renvoie 403/404.
  - Si WHATSAPP_BSP_APP_SECRET n'est pas défini → POST accepte sans
    signature (scaffold non sécurisé ; avertissement dans les logs).
  - Aucun appel réseau sortant depuis ce module.
  - Aucune session / authentification JWT (webhook public).
"""
import hashlib
import hmac
import json
import logging
import os

from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de sécurité
# ---------------------------------------------------------------------------

def _verify_token():
    """Renvoie WHATSAPP_BSP_VERIFY_TOKEN ou '' si non défini."""
    return os.getenv("WHATSAPP_BSP_VERIFY_TOKEN", "").strip()


def _app_secret():
    """Renvoie WHATSAPP_BSP_APP_SECRET ou '' si non défini."""
    return os.getenv("WHATSAPP_BSP_APP_SECRET", "").strip()


def _check_signature(request, secret):
    """Vérifie X-Hub-Signature-256 de la requête POST.

    Retourne True si la signature est valide, False sinon.
    Retourne None si la signature est absente ET que secret est non vide
    (ce qui doit bloquer la requête).
    """
    sig_header = request.META.get("HTTP_X_HUB_SIGNATURE_256", "")
    if not sig_header:
        return None  # signature absente
    if not sig_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), request.body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(sig_header, expected)


# ---------------------------------------------------------------------------
# Vue principale
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name="dispatch")
class WhatsAppBspWebhookView(View):
    """Webhook Meta pour les statuts de livraison WhatsApp BSP."""

    # ---- GET : handshake de vérification Meta ----

    def get(self, request):
        verify_token = _verify_token()
        if not verify_token:
            # Pas configuré → refuse toute vérification.
            return HttpResponse("Non configuré.", status=403)

        mode = request.GET.get("hub.mode", "")
        token = request.GET.get("hub.verify_token", "")
        challenge = request.GET.get("hub.challenge", "")

        if mode != "subscribe":
            return HttpResponse("Mode invalide.", status=403)
        if not hmac.compare_digest(token, verify_token):
            return HttpResponse("Verify token incorrect.", status=403)
        # Renvoie le challenge en texte brut (Meta l'exige).
        return HttpResponse(challenge, content_type="text/plain", status=200)

    # ---- POST : reception des callbacks de statut ----

    def post(self, request):
        secret = _app_secret()

        if secret:
            sig_ok = _check_signature(request, secret)
            if sig_ok is None:
                # Secret configuré mais signature absente.
                logger.warning(
                    "Webhook BSP WhatsApp : signature absente (app_secret configuré)."
                )
                return HttpResponse("Signature manquante.", status=403)
            if not sig_ok:
                logger.warning(
                    "Webhook BSP WhatsApp : signature invalide."
                )
                return HttpResponse("Signature invalide.", status=403)
        else:
            # Secret non configuré : on accepte mais on avertit.
            logger.warning(
                "Webhook BSP WhatsApp : WHATSAPP_BSP_APP_SECRET non configuré — "
                "webhook accepté sans vérification de signature (scaffold non sécurisé)."
            )

        try:
            payload = json.loads(request.body or b"{}")
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"detail": "JSON invalide."}, status=400)

        self._process_statuses(payload)
        # Meta exige un 200 OK dans tous les cas pour ne pas rejouer.
        return JsonResponse({"ok": True}, status=200)

    # ---- Traitement interne des statuts ----

    @staticmethod
    def _process_statuses(payload):
        """Parse les callbacks de statut Meta et met a jour WhatsAppMessageLog.

        Structure Meta (simplifiée) :
          { "entry": [{ "changes": [{ "value": {
              "statuses": [{ "id": "wamid.xxx", "status": "delivered"|"read",
                             "timestamp": "...", "recipient_id": "..." }]
          }}]}]}

        Erreurs absorbées (best-effort) : un webhook mal formé ne doit jamais
        planter le serveur.
        """
        from .models import WhatsAppMessageLog

        try:
            entries = payload.get("entry") or []
            for entry in entries:
                for change in (entry.get("changes") or []):
                    value = change.get("value") or {}
                    for status_obj in (value.get("statuses") or []):
                        external_id = (status_obj.get("id") or "").strip()
                        raw_status = (status_obj.get("status") or "").lower()
                        if not external_id or not raw_status:
                            continue
                        # Mapper le statut Meta vers notre enum.
                        status_map = {
                            "sent": WhatsAppMessageLog.Status.SENT,
                            "delivered": WhatsAppMessageLog.Status.DELIVERED,
                            "read": WhatsAppMessageLog.Status.READ,
                            "failed": WhatsAppMessageLog.Status.FAILED,
                        }
                        new_status = status_map.get(raw_status)
                        if new_status is None:
                            continue
                        updated = WhatsAppMessageLog.objects.filter(
                            external_id=external_id
                        ).update(status=new_status)
                        if updated:
                            logger.debug(
                                "WhatsApp BSP : statut '%s' applique a %s log(s) "
                                "(external_id=%s).",
                                new_status, updated, external_id,
                            )
        except Exception as exc:  # pragma: no cover - defensif
            logger.warning("Webhook BSP WhatsApp : traitement des statuts echoue : %s", exc)
