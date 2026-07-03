"""Endpoint PUBLIC (sans login) pour le suivi client d'un ticket SAV (FG86).

Accès uniquement via le jeton share_token du ticket.  La réponse ne retourne
que trois champs non-sensibles : référence, statut, date_modification.

Données jamais exposées : cout, chatter (TicketActivity), informations client,
prix d'achat, marge, ou tout autre champ interne.

Protections : X-Robots-Tag noindex sur chaque réponse publique ; throttle
cache-based par IP (30 req/min) sans dépendance externe.
"""
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import Ticket, TicketSatisfaction


# ── Throttle ─────────────────────────────────────────────────────────────────

class SavPublicThrottle(SimpleRateThrottle):
    """Limite le débit des liens publics SAV par IP (cache-based, sans dépendance)."""
    scope = 'sav_public_link'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _noindex(response):
    """Marque une réponse publique comme non-indexable par les moteurs."""
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


def _not_found():
    return _noindex(Response(
        {'detail': "Ce lien de suivi est invalide ou n'existe pas."},
        status=status.HTTP_404_NOT_FOUND,
    ))


# ── Vue publique ──────────────────────────────────────────────────────────────

# Champs publics autorisés — liste exhaustive (défense en profondeur).
# Tout ajout doit être délibéré ; cout et chatter sont EXCLUS par conception.
_PUBLIC_FIELDS = ('reference', 'statut', 'date_modification')


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([SavPublicThrottle])
def ticket_public_status(request, token):
    """FG86 — Statut public d'un ticket SAV (lecture seule, sans login).

    Résout le ticket par son share_token uniquement (pas de company depuis la
    requête).  Renvoie UNIQUEMENT : reference, statut, date_modification.
    Jamais : cout, chatter, informations client, ou tout champ interne.
    Un token inconnu ou absent retourne 404 sans fuite de données.
    """
    if not token:
        return _not_found()
    try:
        ticket = Ticket.objects.only(
            'share_token', *_PUBLIC_FIELDS,
        ).get(share_token=token)
    except Ticket.DoesNotExist:
        return _not_found()

    payload = {field: getattr(ticket, field) for field in _PUBLIC_FIELDS}
    # Statut human-readable (label FR) en complément du code machine.
    payload['statut_display'] = ticket.get_statut_display()
    return _noindex(Response(payload))


# ── XSAV10 — Enquête de satisfaction (CSAT) publique ───────────────────────────

_CLOTURE_STATUTS = (Ticket.Statut.RESOLU, Ticket.Statut.CLOTURE)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([SavPublicThrottle])
def ticket_public_satisfaction(request, token):
    """XSAV10 — Enregistre la satisfaction (CSAT) via le lien client public.

    Résout le ticket par son ``share_token`` uniquement. Refuse : token
    inconnu (404, sans fuite), ticket pas encore résolu/clôturé (400), une
    seconde réponse pour le même ticket (409 — une seule réponse par ticket).
    Aucune donnée interne (chatter, coût, informations client) n'est jamais
    exposée ou requise par cet endpoint — seuls ``note`` (1-5) et
    ``commentaire`` (optionnel) sont acceptés."""
    if not token:
        return _not_found()
    try:
        ticket = Ticket.objects.only(
            'id', 'company_id', 'statut', 'share_token').get(share_token=token)
    except Ticket.DoesNotExist:
        return _not_found()

    if ticket.statut not in _CLOTURE_STATUTS:
        return _noindex(Response(
            {'detail': "Ce ticket n'est pas encore résolu — "
                       "l'enquête de satisfaction n'est pas disponible."},
            status=status.HTTP_400_BAD_REQUEST))

    if TicketSatisfaction.objects.filter(ticket=ticket).exists():
        return _noindex(Response(
            {'detail': 'Une réponse a déjà été enregistrée pour ce ticket.'},
            status=status.HTTP_409_CONFLICT))

    try:
        note = int(request.data.get('note'))
    except (TypeError, ValueError):
        return _noindex(Response(
            {'detail': 'Note invalide (entier de 1 à 5 attendu).'},
            status=status.HTTP_400_BAD_REQUEST))
    if note < 1 or note > 5:
        return _noindex(Response(
            {'detail': 'Note invalide (entier de 1 à 5 attendu).'},
            status=status.HTTP_400_BAD_REQUEST))
    commentaire = (request.data.get('commentaire') or '').strip()[:4000]

    try:
        satisfaction = TicketSatisfaction.objects.create(
            company_id=ticket.company_id,
            ticket=ticket, note=note, commentaire=commentaire)
    except Exception:  # noqa: BLE001 — filet de course (OneToOne race)
        return _noindex(Response(
            {'detail': 'Une réponse a déjà été enregistrée pour ce ticket.'},
            status=status.HTTP_409_CONFLICT))

    return _noindex(Response(
        {'note': satisfaction.note, 'commentaire': satisfaction.commentaire},
        status=status.HTTP_201_CREATED))
