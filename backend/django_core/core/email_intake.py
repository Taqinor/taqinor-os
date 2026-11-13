"""FG373 — Email entrant IMAP → leads/tickets (fondation branchable).

Interroge une boîte IMAP partagée et convertit les emails entrants en
leads/tickets — MAIS ``core`` est la couche de FONDATION et NE DOIT PAS importer
les apps métier (crm/sav) qui matérialisent ces leads/tickets (contrat
import-linter ``core-foundation-is-a-base-layer``).

Découplage par REGISTRE de HANDLERS
-----------------------------------

* ``core`` fait le travail GÉNÉRIQUE : se connecter en IMAP, récupérer les
  nouveaux messages, les parser en ``InboundMessage`` (objet pur), gérer le
  threading (Message-ID / In-Reply-To / References).
* Les apps métier (crm, sav) S'ABONNENT en enregistrant un handler via
  ``register_handler(fn)`` (typiquement dans leur ``apps.py ready()``).
* ``poll_mailbox(company)`` récupère les messages et les passe à chaque handler
  enregistré ; chaque handler décide s'il crée un lead/ticket. ``core`` ne sait
  RIEN de ce que fait le handler.

⚠ AUTH : la connexion réelle exige des identifiants de boîte (hôte + user +
mot de passe) que seul le fondateur provisionne. Hôte via
``IntegrationConfig.settings`` (host/user/folder), mot de passe via
``secret_ref`` (variable d'environnement). Sans config → no-op propre (aucune
connexion).
"""
from __future__ import annotations

from .integrations import TYPE_EMAIL_IN, resolve_secret

import logging

logger = logging.getLogger(__name__)

# Handlers enregistrés par les apps métier (callables(InboundMessage, company)).
_HANDLERS: list = []


class InboundMessage:
    """Message entrant parsé, PUR (aucune dépendance domaine)."""

    def __init__(self, *, message_id='', in_reply_to='', references='',
                 subject='', from_email='', from_name='', body='',
                 received_at=None, raw_headers=None):
        self.message_id = message_id
        self.in_reply_to = in_reply_to
        self.references = references
        self.subject = subject
        self.from_email = from_email
        self.from_name = from_name
        self.body = body
        self.received_at = received_at
        self.raw_headers = dict(raw_headers or {})

    @property
    def thread_root(self) -> str:
        """Identifiant de fil : 1er References, sinon In-Reply-To, sinon self."""
        if self.references:
            return self.references.split()[0]
        return self.in_reply_to or self.message_id

    def as_dict(self) -> dict:
        return {
            'message_id': self.message_id,
            'in_reply_to': self.in_reply_to,
            'references': self.references,
            'subject': self.subject,
            'from_email': self.from_email,
            'from_name': self.from_name,
            'body': self.body,
            'thread_root': self.thread_root,
        }


def register_handler(fn):
    """Enregistre un handler de message entrant (idempotent par identité)."""
    if fn not in _HANDLERS:
        _HANDLERS.append(fn)
    return fn


def _dispatch(messages, company, traites=None):
    """Passe chaque message à chaque handler ; un handler qui lève n'arrête pas
    les autres (robustesse). Retourne le nombre de (message, handler) traités.
    ACEL17 — ``traites`` (liste) reçoit les messages qu'AUCUN handler n'a fait lever."""
    handled = 0
    for msg in messages:
        intact = True
        for handler in list(_HANDLERS):
            try:
                handler(msg, company)
                handled += 1
            except Exception:  # noqa: BLE001 — un handler défaillant n'arrête rien (D-ENF22-BLE001)
                intact = False
                logger.warning("dispatch : échec ignoré, comportement dégradé", exc_info=True)
                continue
        if intact and traites is not None:
            traites.append(msg)
    return handled


def _active_imap_config(company):
    from .models import IntegrationConfig
    return (IntegrationConfig.objects
            .filter(company=company, integration_type=TYPE_EMAIL_IN, actif=True)
            .order_by('id')
            .first())


def _parse_email_message(raw_bytes) -> InboundMessage:
    """Parse un message brut (RFC 822) en ``InboundMessage`` (lib std uniquement)."""
    import email
    from email.utils import parseaddr

    msg = email.message_from_bytes(raw_bytes)
    from_name, from_email = parseaddr(msg.get('From', ''))
    body = ''
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode(
                        part.get_content_charset() or 'utf-8', 'replace')
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(msg.get_content_charset() or 'utf-8',
                                  'replace')
    return InboundMessage(
        message_id=msg.get('Message-ID', '').strip('<> '),
        in_reply_to=msg.get('In-Reply-To', '').strip('<> '),
        references=msg.get('References', ''),
        subject=msg.get('Subject', ''),
        from_email=from_email,
        from_name=from_name,
        body=body,
        raw_headers={k: v for k, v in msg.items()},
    )


IMAP_TIMEOUT = 30  # ACEL17 — un serveur muet ne bloque plus la file `scheduled`


def _imap(config_obj):
    """Connexion IMAP ouverte (login + dossier) ou ``None`` si non configuré."""
    import imaplib

    settings = config_obj.settings or {}
    host, user = settings.get('host'), settings.get('user')
    password = resolve_secret(getattr(config_obj, 'secret_ref', '') or None)
    if not host or not user or not password:
        return None
    conn = imaplib.IMAP4_SSL(host, timeout=IMAP_TIMEOUT)
    conn.login(user, password)
    conn.select(settings.get('folder', 'INBOX'))
    return conn


def fetch_messages(config_obj):
    """Récupère les messages NON LUS via IMAP (no-op propre si non configuré).

    ACEL17 — relève en ``BODY.PEEK[]`` : le message reste NON LU sur le serveur
    tant que ``poll_mailbox`` ne l'a pas marqué après son traitement.

    Identifiants : host/user/folder via ``settings`` ; mot de passe via
    ``secret_ref`` (variable d'environnement). Renvoie une liste de
    ``InboundMessage`` (vide si non configuré ou si la lib/serveur est
    indisponible — jamais d'exception remontée).
    """
    out = []
    try:
        conn = _imap(config_obj)
        if conn is None:
            return []  # non configuré → no-op propre.
        typ, data = conn.search(None, 'UNSEEN')
        if typ == 'OK':
            for num in data[0].split():
                t, msg_data = conn.fetch(num, '(BODY.PEEK[])')
                if t == 'OK' and msg_data and msg_data[0]:
                    msg = _parse_email_message(msg_data[0][1])
                    msg.imap_num = num
                    out.append(msg)
        conn.logout()
    except Exception:  # noqa: BLE001 — réseau/auth : dégrade en vide (D-ENF22-BLE001)
        logger.warning("fetch messages : échec ignoré, comportement dégradé", exc_info=True)
        return out
    return out


def poll_mailbox(company):
    """Interroge la boîte de la société et dispatche aux handlers enregistrés.

    Multi-tenant : la société est imposée par l'appelant. Aucune config → 0
    message, 0 dispatch (no-op propre). Retourne un récap
    ``{"fetched", "handled"}``.
    """
    cfg = _active_imap_config(company)
    if cfg is None:
        return {'fetched': 0, 'handled': 0}
    messages = fetch_messages(cfg)
    traites = []
    handled = _dispatch(messages, company, traites)
    nums = [m.imap_num for m in traites if getattr(m, 'imap_num', None)]
    if nums:  # ACEL17 — `\\Seen` posé APRÈS le traitement, sur ceux-là seuls
        try:
            conn = _imap(cfg)
            for num in nums:
                conn.store(num, '+FLAGS', '\\Seen')
            conn.logout()
        except Exception:  # noqa: BLE001 — non marqué = re-relevé, jamais perdu (D-ENF22-BLE001)
            logger.warning('poll_mailbox : marquage lu en échec', exc_info=True)
    return {'fetched': len(messages), 'handled': handled}
