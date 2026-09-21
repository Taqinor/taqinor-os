"""QJ23 — Webhook BSP WhatsApp (Meta Cloud API, flag-gated).

Deux endpoints publics (pas de session / JWT) :
  GET  /api/django/notifications/whatsapp/webhook/
       Handshake de vérification Meta : hub.mode=subscribe +
       hub.verify_token + hub.challenge. Renvoie hub.challenge si le
       verify_token correspond à WHATSAPP_BSP_VERIFY_TOKEN (env).
       Retourne 403 si non configuré ou token incorrect.

  POST /api/django/notifications/whatsapp/webhook/
       Reçoit les callbacks de statut (delivered / read) ET les messages
       ENTRANTS (XSAV26). Les statuts mettent à jour WhatsAppMessageLog (via
       external_id). Les messages entrants sont routés vers un ticket SAV
       quand l'expéditeur matche un `crm.Client` existant
       (`apps.sav.services.router_whatsapp_entrant_vers_ticket`). Valide la
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

SOLMVP19 — la capture des messages entrants vers COMPTA (FG207, lead
  pré-qualifié `compta.services.capturer_message_whatsapp`) et la
  conversation Discuss dédiée (`chat.services`) sont retirées : compta ET
  chat sont sortis du produit (apps parquées, voir `core/parked.py`) — toute
  référence à ces labels casse le boot (`scripts/check_parked_apps.py`).
  Le ROUTAGE VERS LE SAV (XSAV26,
  `apps.sav.services.router_whatsapp_entrant_vers_ticket`) reste : `apps.sav`
  n'est PAS parquée. Un expéditeur reconnu comme `crm.Client` existant route
  vers un ticket SAV (créé ou noté) ; un numéro inconnu du SAV est un NO-OP
  strict (le chemin lead XKB33 disparaît avec compta/chat). Le toggle
  générique WHATSAPP_ENABLED/WHATSAPP_ACCESS_TOKEN (ex-`compta.services.
  whatsapp_actif()`) est réimplémenté localement (`_whatsapp_actif()`) pour
  ne dépendre d'aucune app parquée. La résolution de la société cible se
  fait via `WHATSAPP_BSP_COMPANY_ID` (env, id opaque) — scaffold
  mono-société tant qu'aucun routage multi-société par numéro Meta n'est
  fourni.
"""
import hashlib
import hmac
import json
import logging
import os

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


def _whatsapp_actif():
    """Toggle générique WhatsApp Business Cloud (Meta). OFF par défaut.

    SOLMVP19 — remplace `compta.services.whatsapp_actif()` (compta est
    parquée, cf. module docstring) : même contrat exact, vérification
    directe des settings, sans dépendance vers une app parquée. Le founder
    l'active en posant `WHATSAPP_ENABLED = True` + un jeton
    `WHATSAPP_ACCESS_TOKEN` (settings/env). Tant que c'est faux/sans jeton,
    le traitement des messages entrants (XSAV26) est un NO-OP.
    """
    return bool(getattr(settings, "WHATSAPP_ENABLED", False)
                and getattr(settings, "WHATSAPP_ACCESS_TOKEN", ""))


def _target_company():
    """Société cible pour le routage des messages entrants (XSAV26), ou None.

    Scaffold mono-société : `WHATSAPP_BSP_COMPANY_ID` (env, id opaque). Sans
    cette variable, le routage entrant reste un NO-OP complet (aucune
    société résolue → rien n'est traité), même si le webhook de statut
    continue de fonctionner normalement."""
    raw = os.getenv("WHATSAPP_BSP_COMPANY_ID", "").strip()
    if not raw:
        return None
    try:
        from authentication.models import Company
        return Company.objects.filter(pk=int(raw)).first()
    except (ValueError, TypeError):
        return None
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning("Webhook BSP WhatsApp : résolution société échouée : %s", exc)
        return None


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
    # QJR413 (a) — COMPARER EN BYTES. ``compare_digest(str, str)`` lève un
    # ``TypeError`` non intercepté dès qu'un opérande porte un caractère
    # non-ASCII : un seul octet hostile dans ``X-Hub-Signature-256`` rendait
    # un HTTP 500 NON AUTHENTIFIÉ, dont la trame d'erreur portait la valeur
    # ATTENDUE en clair. Même patron que ``ventes.domain.cycle_vie``.
    return hmac.compare_digest(str(sig_header).encode("utf-8"),
                               expected.encode("utf-8"))


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
        # QJR413 (a) — comparaison en BYTES (voir ``_check_signature``) : un
        # ``hub.verify_token`` non-ASCII rendait un 500 public.
        if not hmac.compare_digest(str(token).encode("utf-8"),
                                   verify_token.encode("utf-8")):
            return HttpResponse("Verify token incorrect.", status=403)
        # Renvoie le challenge en texte brut (Meta l'exige).
        return HttpResponse(challenge, content_type="text/plain", status=200)

    # ---- POST : reception des callbacks de statut ----

    def post(self, request):
        secret = _app_secret()

        # ── QJR414 (DÉCISION FONDATEUR DR3) — FAIL-CLOSED. Ce webhook portait
        # le motif IDENTIQUE à son jumeau Meta Lead Ads (apps/crm/webhooks.py) :
        # secret absent ⇒ avertissement PUIS traitement du payload. Comme
        # ``WHATSAPP_BSP_APP_SECRET`` n'était documenté dans AUCUN
        # ``.env.example``, le déploiement par défaut était OUVERT *et*
        # SILENCIEUX. DR3 tranche — secret absent ⇒ requête REFUSÉE (403),
        # jamais traitée, AVANT tout effet de bord.
        # CONSÉQUENCE VOULUE ET ACCEPTÉE : la synchronisation entrante reste EN
        # PAUSE tant que le secret n'est pas posé au deploy.
        if not secret:
            logger.error(
                "Webhook BSP WhatsApp : WHATSAPP_BSP_APP_SECRET non configuré "
                "— requête REFUSÉE (DR3, fail-closed). La synchronisation "
                "entrante reste en pause tant que le secret n'est pas posé."
            )
            return HttpResponse("Signature requise.", status=403)

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

        try:
            payload = json.loads(request.body or b"{}")
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"detail": "JSON invalide."}, status=400)

        self._process_statuses(payload)
        self._process_messages(payload)
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

    # ---- Traitement interne des messages entrants (XSAV26) ----

    @staticmethod
    def _process_messages(payload):
        """Parse les messages ENTRANTS Meta et les route vers le SAV (XSAV26).

        Structure Meta (simplifiee) :
          { "entry": [{ "changes": [{ "value": {
              "contacts": [{ "profile": { "name": "..." }, "wa_id": "..." }],
              "messages": [{ "id": "wamid.xxx", "from": "2126...",
                             "type": "text", "text": {"body": "..."} }]
          }}]}]}

        GATED : sans societe cible resolue (`_target_company`) OU sans
        `_whatsapp_actif()` (WHATSAPP_ENABLED + WHATSAPP_ACCESS_TOKEN), c'est
        un NO-OP complet — rien n'est traite, rien ne change. SOLMVP19 — la
        capture compta (FG207) et la conversation Discuss dediee sont
        retirees (apps compta/chat parquees, cf. docstring du module) ; seul
        le routage SAV (XSAV26) subsiste. Erreurs absorbees (best-effort) :
        un webhook mal forme ne doit jamais planter le serveur.
        """
        try:
            if not _whatsapp_actif():
                return
            company = _target_company()
            if company is None:
                return

            entries = payload.get("entry") or []
            for entry in entries:
                for change in (entry.get("changes") or []):
                    value = change.get("value") or {}
                    messages = value.get("messages") or []
                    if not messages:
                        continue
                    contacts = value.get("contacts") or []
                    profile_names = {
                        (c.get("wa_id") or "").strip():
                            (c.get("profile") or {}).get("name", "")
                        for c in contacts
                    }
                    for msg in messages:
                        wa_message_id = (msg.get("id") or "").strip()
                        expediteur = (msg.get("from") or "").strip()
                        if not wa_message_id or not expediteur:
                            continue
                        texte = ((msg.get("text") or {}).get("body", "") or "")
                        nom_profil = profile_names.get(expediteur, "")
                        WhatsAppBspWebhookView._capture_and_route(
                            company, wa_message_id=wa_message_id,
                            expediteur=expediteur, nom_profil=nom_profil,
                            texte=texte)
        except Exception as exc:  # pragma: no cover - defensif
            logger.warning(
                "Webhook BSP WhatsApp : traitement des messages entrants echoue : %s",
                exc)

    @staticmethod
    def _capture_and_route(company, *, wa_message_id, expediteur, nom_profil, texte):
        """Route un message WhatsApp entrant vers un ticket SAV (XSAV26).

        SOLMVP19 — la capture compta (FG207, lead pré-qualifié) et la
        conversation Discuss dédiée sont retirées (apps compta/chat
        parquées) : seul le routage SAV subsiste ci-dessous. Un expéditeur
        reconnu comme `crm.Client` existant route vers un ticket (créé ou
        note sur le ticket ouvert le plus récent) ; un numéro inconnu du SAV
        est un NO-OP strict (le chemin lead XKB33 disparaît avec compta/chat).
        Best-effort : un échec de routage ne doit jamais planter le webhook.
        """
        try:
            from apps.sav.services import router_whatsapp_entrant_vers_ticket
            router_whatsapp_entrant_vers_ticket(
                company=company, expediteur=expediteur, texte=texte)
        except Exception as exc:  # pragma: no cover - defensif
            logger.warning(
                "Webhook BSP WhatsApp : routage SAV echoue : %s", exc)
