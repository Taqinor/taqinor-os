"""N88 — Capture des emails entrants : rattache une réponse au fil du
client / chantier (devis ou facture) lorsqu'une référence reconnaissable est
présente dans le sujet ou le corps.

Comme l'envoi (N87), la capture entrante est un NO-OP sans configuration : sans
clé/credentials de réception configurés, `is_inbound_configured()` est False et
`capture_inbound_email()` se contente d'enregistrer la trace si on lui passe
explicitement un message (utile en test), sans jamais ouvrir de connexion
réseau. Aucun appel externe n'est fait ici ; le parsing est pur. Les tests
n'exigent aucune clé vivante.
"""
import logging
import re

from django.conf import settings

from .models import Devis, EmailLog, Facture

logger = logging.getLogger(__name__)

# Références documents reconnues : DEV-… (devis) et FAC-… (facture). On accepte
# des séparateurs souples et on normalise en MAJUSCULES. La référence réelle est
# ensuite confirmée par une recherche en base scopée société.
_REF_RE = re.compile(r'\b((?:DEV|FAC)[-_/ ]?[A-Z0-9][A-Z0-9-]{2,})\b', re.I)


def is_inbound_configured():
    """True si une boîte de réception (Brevo inbound / IMAP) est configurée.

    Sans configuration → la capture reste un NO-OP réseau (aucune connexion).
    On considère configuré : un secret de webhook inbound Brevo, OU un hôte
    IMAP. Purement informatif ; ne lève jamais."""
    if getattr(settings, 'BREVO_INBOUND_SECRET', ''):
        return True
    return bool(getattr(settings, 'INBOUND_EMAIL_HOST', ''))


def extract_reference(text):
    """Extrait la première référence document (DEV-…/FAC-…) trouvée, normalisée
    en MAJUSCULES sans espaces parasites. Renvoie '' si rien."""
    if not text:
        return ''
    match = _REF_RE.search(text)
    if not match:
        return ''
    raw = match.group(1).upper()
    # Normalise les séparateurs (DEV 2026 → DEV-2026) sans casser un '-' déjà là.
    raw = re.sub(r'[ _/]+', '-', raw)
    return raw[:80]


def _find_document(reference, company=None):
    """Cherche le devis/facture correspondant à la référence (scopé société si
    fournie). Renvoie (document, kind) ou (None, None). La correspondance est
    insensible à la casse et tolère une référence partielle exacte."""
    if not reference:
        return None, None
    for model, kind in ((Facture, 'facture'), (Devis, 'devis')):
        qs = model.objects.all()
        if company is not None:
            qs = qs.filter(company=company)
        doc = qs.filter(reference__iexact=reference).first()
        if doc is not None:
            return doc, kind
    return None, None


def _find_client_by_email(from_email, company=None):
    from apps.crm.selectors import find_client_by_email
    return find_client_by_email(from_email, company=company)


def capture_inbound_email(from_email='', subject='', body='', company=None,
                          to_email=''):
    """Rattache un email entrant au bon fil et le consigne dans EmailLog.

    Cherche une référence document (DEV-…/FAC-…) dans le sujet puis le corps ;
    si trouvée et résolue, rattache au document (+ son client). Sinon, rattache
    au client identifié par l'adresse expéditrice. Renvoie l'EmailLog créé, ou
    None si rien n'a pu être rattaché (ni document ni client connu) — dans ce
    cas on ne crée pas de bruit. Aucune exception réseau : parsing pur.
    """
    reference = extract_reference(subject) or extract_reference(body)
    document, kind = _find_document(reference, company=company)

    client = None
    devis = facture = None
    if document is not None:
        client = getattr(document, 'client', None)
        if kind == 'facture':
            facture = document
        else:
            devis = document
        if company is None:
            company = getattr(document, 'company', None)
    else:
        client = _find_client_by_email(from_email, company=company)
        if client is not None and company is None:
            company = getattr(client, 'company', None)

    if document is None and client is None:
        # Rien de reconnaissable : on n'enregistre pas de trace orpheline.
        logger.info('Email entrant non rattaché (from=%s, ref=%s)',
                    from_email, reference)
        return None

    log = EmailLog.objects.create(
        company=company,
        direction=EmailLog.Direction.ENTRANT,
        statut=EmailLog.Statut.RECU,
        client=client, devis=devis, facture=facture,
        from_email=(from_email or '')[:254], to_email=(to_email or '')[:254],
        sujet=(subject or '')[:300], corps=body or '',
        reference=reference,
    )
    # QX36 — une réponse rattachée à un DEVIS surface dans son chatter + notifie
    # le vendeur (sinon la réponse client atterrissait dans le vide). Best-
    # effort : jamais bloquant.
    if devis is not None:
        _notify_devis_reply(devis, from_email, subject)
    return log


def _notify_devis_reply(devis, from_email, subject):
    """QX36 — chatter + notification vendeur sur une réponse email à un devis."""
    try:
        from .models import DevisActivity
        DevisActivity.objects.create(
            company=devis.company, devis=devis,
            kind=DevisActivity.Kind.NOTE,
            body=(f'Réponse email reçue de {from_email or "?"} : '
                  f'« {(subject or "").strip()[:120]} »'))
    except Exception:  # noqa: BLE001 — best-effort
        pass
    try:
        from apps.notifications.services import notify
        from apps.notifications.models import EventType
        owner = getattr(devis, 'created_by', None)
        if owner is not None:
            notify(
                owner, EventType.DEVIS_REPLY,
                title=f'Réponse client — devis {devis.reference}',
                body=(subject or '')[:200],
                link=f'/ventes/devis?devis={devis.id}',
                company=devis.company)
    except Exception:  # noqa: BLE001 — best-effort
        pass


def ventes_inbound_handler(message, company):
    """QX36 — handler du bus ``core.email_intake`` : route une réponse email
    portant une référence DEV-…/FAC-… vers ``capture_inbound_email`` (chatter +
    notification sur le devis). ``core`` n'importe jamais ``apps.ventes`` —
    même patron de découplage que le handler SAV. Best-effort : un handler qui
    lève n'arrête pas les autres (le dispatcher core encaisse)."""
    return capture_inbound_email(
        from_email=getattr(message, 'from_email', '') or '',
        subject=getattr(message, 'subject', '') or '',
        body=getattr(message, 'body', '') or '',
        company=company)


def register_ventes_inbound_handler():
    """QX36 — abonne ``ventes_inbound_handler`` au bus e-mail entrant, câblé
    depuis ``VentesConfig.ready()``."""
    from core.email_intake import register_handler
    register_handler(ventes_inbound_handler)
