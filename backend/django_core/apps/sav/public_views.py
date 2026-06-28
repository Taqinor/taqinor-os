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

from .models import Ticket


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
