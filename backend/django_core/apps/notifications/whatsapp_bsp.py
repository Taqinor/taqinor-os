"""QJ23 — Abstraction fournisseur WhatsApp (flag-gated, défaut manuel wa.me).

ARCHITECTURE:
  ManualWaMeProvider  — comportement ACTUEL : construit un lien wa.me pre-rempli
                        que le commercial appuie lui-meme sur Envoyer. ZERO appel
                        reseau. Comportement par defaut si WHATSAPP_BSP_ENABLED
                        n'est pas positionne a '1' OU si les credentials manquent.

  BspProvider         — SCAFFOLD uniquement : le chemin live vers l'API Meta Cloud
                        (envoi automatique de l'API WhatsApp Business) est BLOQUE
                        sur un compte BSP + numero verifie Meta que le fondateur
                        doit provisionner. La classe est construite uniquement quand
                        WHATSAPP_BSP_ENABLED=1 ET les trois credentials sont presents
                        (WHATSAPP_BSP_BASE_URL, WHATSAPP_BSP_TOKEN,
                        WHATSAPP_BSP_PHONE_NUMBER_ID). En leur absence, `get_wa_url`
                        tombe en repli sur le manuel - AUCUN crash, AUCUN appel reseau.

`get_whatsapp_provider()` - factory qui lit l'env et renvoie le bon provider.

Regle de securite : le prix d'achat et la marge ne doivent JAMAIS apparaitre dans
un message envoye via ce module.
"""
import logging
import os
from urllib.parse import quote

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers partages
# ---------------------------------------------------------------------------

def _normalize_phone(phone_raw):
    """Delegue a la normalisation existante (ex. +2126xxxxxxxx -> 2126xxxxxxxx)."""
    try:
        from apps.ventes.utils.phone import normalize_ma_phone
        return normalize_ma_phone(phone_raw)
    except Exception as exc:  # pragma: no cover - defensif
        logger.warning("normalize_ma_phone indisponible : %s", exc)
        return None


# ---------------------------------------------------------------------------
# Interface abstraite
# ---------------------------------------------------------------------------

class WhatsAppProvider:
    """Interface commune : chaque implementation doit fournir `get_wa_url`."""

    def get_wa_url(self, phone_raw, message):
        """Renvoie un dict avec au moins `url` (str|None) et `provider` (str).

        - `url`      : lien wa.me OU None si numero invalide / provider non actif.
        - `provider` : 'manual' | 'bsp'.
        Les erreurs NE DOIVENT JAMAIS remonter a l'appelant.
        """
        raise NotImplementedError  # pragma: no cover


# ---------------------------------------------------------------------------
# Implementation 1 : comportement actuel (wa.me, aucun appel reseau)
# ---------------------------------------------------------------------------

class ManualWaMeProvider(WhatsAppProvider):
    """Construit un lien wa.me pre-rempli - AUCUN appel reseau.

    C'est le comportement actuel de tout l'ERP (crm/ventes). Ce provider est
    le defaut absolu et ne change pas le comportement existant d'un bit."""

    def get_wa_url(self, phone_raw, message):
        try:
            from apps.ventes.utils.whatsapp import build_wa_url
            url = build_wa_url(phone_raw, message)
        except Exception as exc:  # pragma: no cover - defensif
            logger.warning("build_wa_url echoue : %s", exc)
            url = self._fallback_url(phone_raw, message)
        return {"url": url, "provider": "manual"}

    @staticmethod
    def _fallback_url(phone_raw, message):
        """Fallback si build_wa_url est inaccessible (ne devrait pas arriver)."""
        number = _normalize_phone(phone_raw)
        if not number:
            return None
        return "https://wa.me/" + number + "?text=" + quote(message)


# ---------------------------------------------------------------------------
# Implementation 2 : BSP (Meta Cloud API) - SCAFFOLD, live gated
# ---------------------------------------------------------------------------

class BspProvider(WhatsAppProvider):
    """Scaffold de l'envoi via API WhatsApp Business (Meta Cloud API / BSP).

    SEAM - la methode `_send_via_api` est prevue pour le vrai POST Meta, mais
    elle N'EST PAS IMPLEMENTEE : cela exige un compte BSP provisionne et un
    numero de telephone verifie Meta (a faire avec le fondateur). Sans ces
    credentials, `get_wa_url` tombe en repli sur ManualWaMeProvider - AUCUN
    crash, AUCUN appel reseau.

    Ne jamais exposer prix_achat / marge dans le corps d'un message.
    """

    def __init__(self, base_url, token, phone_number_id):
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._phone_number_id = phone_number_id
        self._manual = ManualWaMeProvider()

    def get_wa_url(self, phone_raw, message):
        """Tente l'envoi BSP ; si credentials incomplets -> repli manuel.

        En production, quand tous les credentials sont presents, cette methode
        appellera `_send_via_api` (a implementer avec le fondateur). Pour l'instant
        elle tombe TOUJOURS en repli manuel.
        """
        if not self._token or not self._phone_number_id or not self._base_url:
            return self._manual.get_wa_url(phone_raw, message)
        # TODO (fondateur) : decommenter quand le compte BSP est provisionne.
        # result = self._send_via_api(phone_raw, message)
        # if result is not None:
        #     return {"url": None, "provider": "bsp", "bsp_message_id": result}
        # Repli manuel si l'envoi BSP echoue.
        return self._manual.get_wa_url(phone_raw, message)

    def _send_via_api(self, phone_raw, message):  # pragma: no cover
        """POST vers l'API Meta Cloud - NON ACTIF (gated sur compte BSP fondateur).

        Signature prevue : renvoie l'ID du message ou None en cas d'echec.
        NE PAS ACTIVER avant d'avoir le compte BSP + numero verifie Meta.
        """
        number = _normalize_phone(phone_raw)
        if not number:
            return None
        import json
        import urllib.request
        payload = json.dumps({
            "messaging_product": "whatsapp",
            "to": number,
            "type": "text",
            "text": {"body": message},
        }).encode()
        url = (
            self._base_url
            + "/"
            + self._phone_number_id
            + "/messages"
        )
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": "Bearer " + self._token,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            import urllib.error
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                return data.get("messages", [{}])[0].get("id")
        except Exception as exc:
            logger.warning("Envoi BSP WhatsApp echoue : %s", exc)
            return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_whatsapp_provider():
    """Renvoie le provider adapte selon l'environnement.

    Logique :
      1. Si WHATSAPP_BSP_ENABLED != '1' -> ManualWaMeProvider (defaut).
      2. Si WHATSAPP_BSP_ENABLED == '1' mais credentials incomplets
         -> ManualWaMeProvider (repli silencieux, aucun crash).
      3. Si WHATSAPP_BSP_ENABLED == '1' ET tous les credentials presents
         -> BspProvider (scaffold ; tombe quand meme en repli manuel jusqu'a ce
           que _send_via_api soit active par le fondateur).

    Env vars lus (noms seulement) :
      WHATSAPP_BSP_ENABLED        ('1' pour activer)
      WHATSAPP_BSP_BASE_URL       (ex. https://graph.facebook.com/v19.0)
      WHATSAPP_BSP_TOKEN          (Bearer token Meta)
      WHATSAPP_BSP_PHONE_NUMBER_ID (ID du numero Meta verifie)
    """
    if os.getenv("WHATSAPP_BSP_ENABLED", "0") != "1":
        return ManualWaMeProvider()

    base_url = os.getenv("WHATSAPP_BSP_BASE_URL", "").strip()
    token = os.getenv("WHATSAPP_BSP_TOKEN", "").strip()
    phone_number_id = os.getenv("WHATSAPP_BSP_PHONE_NUMBER_ID", "").strip()

    if not (base_url and token and phone_number_id):
        # Credentials manquants -> repli silencieux sur manuel.
        logger.info(
            "WHATSAPP_BSP_ENABLED=1 mais credentials incomplets - "
            "repli sur ManualWaMeProvider."
        )
        return ManualWaMeProvider()

    return BspProvider(base_url=base_url, token=token, phone_number_id=phone_number_id)
