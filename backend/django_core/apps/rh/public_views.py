"""XRH20 — endpoints publics tokenisés de la promesse d'embauche.

Le candidat consulte et signe SA promesse via un lien tokenisé (pattern
liens publics WhatsApp FG79 / ``ventes.public_views``) : jeton long,
imprévisible, expirant (30 j). AUCUNE session, AUCUN login requis. Le PDF
n'est JAMAIS indexé (X-Robots-Tag: noindex) et throttlé contre le brute-force.
"""
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from . import services
from .models import PromesseEmbauche
from .pdf import render_promesse_embauche_pdf


class PromesseLinkRateThrottle(SimpleRateThrottle):
    """Throttle des liens publics de promesse — protège contre le brute-force
    du jeton (même limite que les liens publics ventes)."""
    scope = 'rh_promesse_publique'

    def get_cache_key(self, request, view):
        token = view.kwargs.get('token', '') if hasattr(view, 'kwargs') \
            else request.resolver_match.kwargs.get('token', '')
        ident = f'{self.get_ident(request)}:{token}'
        return self.cache_format % {'scope': self.scope, 'ident': ident}

    def get_rate(self):
        return '30/min'


def _not_found():
    resp = Response(status=status.HTTP_404_NOT_FOUND)
    resp['X-Robots-Tag'] = 'noindex'
    return resp


def _noindex(resp):
    resp['X-Robots-Tag'] = 'noindex'
    return resp


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PromesseLinkRateThrottle])
def public_promesse_detail(request, token):
    """Détail (JSON) de la promesse — pour l'écran de consultation candidat."""
    promesse = (
        PromesseEmbauche.objects.select_related('candidature', 'company')
        .filter(token=token).first())
    if promesse is None or not promesse.is_valid:
        return _not_found()
    return _noindex(Response({
        'candidat_nom': promesse.candidature.nom,
        'poste_propose': promesse.poste_propose,
        'type_contrat': promesse.type_contrat,
        'date_debut_proposee': promesse.date_debut_proposee,
        'salaire_propose': promesse.salaire_propose,
        'statut': promesse.statut,
        'signataire_nom': promesse.signataire_nom,
        'date_signature': promesse.date_signature,
        'expires_at': promesse.expires_at,
    }))


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PromesseLinkRateThrottle])
def public_promesse_pdf(request, token):
    """PDF de la promesse via son jeton (jamais indexé)."""
    promesse = (
        PromesseEmbauche.objects.select_related('candidature', 'company')
        .filter(token=token).first())
    if promesse is None or not promesse.is_valid:
        return _not_found()
    try:
        pdf_bytes = render_promesse_embauche_pdf(promesse)
    except Exception:  # noqa: BLE001 — jamais de fuite de stack au public.
        return _noindex(Response(
            {'detail': 'Document indisponible pour le moment.'},
            status=status.HTTP_404_NOT_FOUND))
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = 'inline; filename="promesse_embauche.pdf"'
    return _noindex(resp)


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        ip = forwarded.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '') or ''
    return ip[:45]


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PromesseLinkRateThrottle])
def public_promesse_signer(request, token):
    """Signature e-sign (loi 53-05, nom tapé) de la promesse via son jeton."""
    promesse = (
        PromesseEmbauche.objects.select_related('candidature', 'company')
        .filter(token=token).first())
    if promesse is None:
        return _not_found()
    nom = (request.data.get('signataire_nom') or '').strip()
    try:
        services.signer_promesse_embauche(
            promesse, signataire_nom=nom, ip_adresse=_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''))
    except services.PromesseSignatureError as exc:
        return _noindex(Response(
            {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST))
    return _noindex(Response({
        'statut': promesse.statut,
        'signataire_nom': promesse.signataire_nom,
        'date_signature': promesse.date_signature,
    }))
