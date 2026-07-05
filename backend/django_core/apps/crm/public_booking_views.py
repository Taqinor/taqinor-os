"""XSAL17 — Réservation de visite PUBLIQUE, tokenisée par lead, expirante.

Endpoints PUBLICS (sans login) pour le prospect qui a reçu un message
contenant le placeholder ``{lien_rdv}`` : voir la fenêtre disponible (aucune
donnée interne — jamais de prix d'achat/marge) et réserver un créneau. Le
booking atterrit TOUJOURS sur le lead d'origine (booking-to-lead, comme
QJ20) — jamais un autre lead, jamais choisi par le visiteur. Même modèle de
confiance que ``public_chat_views.py`` : jeton long/imprévisible (comme
``ShareLink``), jamais de login, jamais de fuite d'un jeton invalide (404
générique).
"""
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .services import (
    BookingLinkUnavailable,
    resolve_booking_link,
    reserver_creneau_public,
)


class PublicBookingRateThrottle(SimpleRateThrottle):
    """Débit limité par IP + jeton — décourage l'abus sans jamais bloquer un
    visiteur légitime (même patron que ``PublicChatRateThrottle``)."""

    scope = 'public_booking'
    rate = '20/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '') if view else ''
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{ident}:{token}',
        }


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicBookingRateThrottle])
def public_booking_status(request, token):
    """XSAL17 — Vérifie qu'un lien de réservation est valide (ni expiré, ni
    déjà utilisé) avant d'afficher le sélecteur de créneau. Ne renvoie AUCUNE
    donnée interne du lead (jamais de prix d'achat/marge, jamais d'autres
    leads) — juste un prénom d'accueil best-effort."""
    try:
        link = resolve_booking_link(token)
    except BookingLinkUnavailable as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    return Response({
        'valid': True,
        'prenom': (link.lead.prenom or '').strip(),
        'expires_at': link.expires_at.isoformat(),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicBookingRateThrottle])
def public_booking_reserve(request, token):
    """XSAL17 — Réserve un créneau via un lien de réservation PUBLIC.

    Corps : ``scheduled_at`` (ISO 8601, requis), ``notes`` (optionnel). Un
    jeton invalide/expiré/déjà utilisé renvoie une réponse honnête (404 pour
    invalide, 410 pour expiré/déjà utilisé) — jamais un faux succès."""
    from django.utils.dateparse import parse_datetime

    raw = request.data.get('scheduled_at')
    scheduled_at = parse_datetime(str(raw)) if raw else None
    if scheduled_at is None:
        return Response(
            {'detail': 'Date/heure de créneau invalide ou manquante.'},
            status=status.HTTP_400_BAD_REQUEST)
    notes = str(request.data.get('notes') or '')[:2000]

    try:
        # Distingue jeton INTROUVABLE (404) de jeton expiré/déjà utilisé (410)
        # — un message honnête, jamais un faux succès générique.
        link = resolve_booking_link(token)
    except BookingLinkUnavailable as exc:
        from .models import BookingLink
        gone = BookingLink.objects.filter(token=token).exists()
        return Response(
            {'detail': str(exc)},
            status=(status.HTTP_410_GONE if gone
                    else status.HTTP_404_NOT_FOUND))

    try:
        appointment = reserver_creneau_public(
            token, scheduled_at=scheduled_at, notes=notes)
    except BookingLinkUnavailable as exc:
        return Response(
            {'detail': str(exc)}, status=status.HTTP_410_GONE)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'detail': 'Rendez-vous réservé.',
        'appointment_id': appointment.pk,
        'lead_id': link.lead_id,
    }, status=status.HTTP_201_CREATED)
