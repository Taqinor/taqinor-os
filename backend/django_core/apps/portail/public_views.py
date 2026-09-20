"""NTPRT19 — Vue PUBLIQUE du branding portail (page de login white-label).

Un seul endpoint, en lecture, sans authentification :
``GET /api/django/public/portail/theme/``.

La société est résolue STRICTEMENT par l'en-tête ``Host`` (domaine white-label
de ``TenantTheme``) — jamais par un paramètre de requête, qui transformerait cet
endpoint en énumérateur de tenants. Aucun host correspondant ⇒ marque VIDE
(200), jamais 404 : la page de login s'affiche simplement avec le thème par
défaut.

La charge utile ne contient QUE de la marque (nom affiché, logo, deux
couleurs) : ni identifiant de société, ni domaine, ni identité légale.

DURCISSEMENT (YRBAC9) : `AllowAny` sans authentification ⇒ le débit par IP est
BORNÉ. Sans cela, chaque appel déclenche une requête `TenantTheme` par `Host`,
donc un anonyme pouvait (a) énumérer les domaines white-label en faisant varier
l'en-tête `Host` autant qu'il voulait, et (b) charger la base gratuitement. Le
quota est par IP, donc indépendant du `Host` — faire varier le domaine ne
réarme pas le compteur, ce qui est précisément l'abus visé.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .branding import MARQUE_VIDE, company_pour_hote, marque_portail

# ── NTPRT6 — forme déclarée de l'acceptation d'invitation ───────────────────
ACCEPTER_INVITATION_PORTAIL_REQUEST = inline_serializer(
    'AccepterInvitationPortailRequest', {
        'token': serializers.CharField(),
        'mot_de_passe': serializers.CharField(),
    })

ACCEPTER_INVITATION_PORTAIL_RESPONSE = inline_serializer(
    'AccepterInvitationPortailResponse', {
        'detail': serializers.CharField(),
    })


class ThemePortailPublicThrottle(SimpleRateThrottle):
    """Quota anonyme du thème public, par IP (jamais par `Host`).

    60/minute : large pour un vrai chargement de page de login (quelques appels
    par visiteur, y compris derrière le NAT d'une société), étroit pour un
    balayage de domaines.
    """

    scope = 'portail_theme_public'
    rate = '60/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([ThemePortailPublicThrottle])
def theme_portail_public(request):
    """Marque du portail pour le domaine appelant (repli neutre)."""
    company = company_pour_hote(request.get_host())
    if company is None:
        return Response(dict(MARQUE_VIDE))
    return Response(marque_portail(company))


# ── NTPRT6 — Acceptation PUBLIQUE d'une invitation à l'équipe portail ───────

class AccepterInvitationPortailThrottle(SimpleRateThrottle):
    """Formulaire anonyme d'écriture (pose un mot de passe + crée un compte) :
    même patron de limitation par IP que ``CandidatureFournisseurThrottle``
    (NTPRT25) — un token seul ne suffit pas à se dispenser d'un plafond."""

    scope = 'portail_accepter_invitation'
    rate = '20/hour'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }


@extend_schema(request=ACCEPTER_INVITATION_PORTAIL_REQUEST,
               responses=ACCEPTER_INVITATION_PORTAIL_RESPONSE)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AccepterInvitationPortailThrottle])
def accepter_invitation_portail_public(request):
    """NTPRT6 — L'invité pose son mot de passe via le lien reçu par email.

    ``token`` et ``mot_de_passe`` sont les SEULS champs lus — jamais d'email
    ni de rôle depuis le corps (l'un et l'autre viennent de l'invitation
    elle-même, posée côté serveur à l'appel ``inviter_membre_portail``). La
    réponse ne renvoie AUCUNE information sur l'invitation en cas d'échec
    (token inconnu/expiré/déjà utilisé/révoqué) — un seul message générique,
    jamais de quoi distinguer un token invalide d'un token déjà consommé.
    """
    from . import services

    token = (request.data.get('token') or '').strip()
    mot_de_passe = request.data.get('mot_de_passe') or ''
    if not token or not mot_de_passe:
        return Response(
            {'detail': 'Le token et le mot de passe sont requis.'},
            status=status.HTTP_400_BAD_REQUEST)

    user = services.accepter_invitation_portail(token, mot_de_passe)
    if user is None:
        return Response(
            {'detail': 'Invitation introuvable, déjà utilisée, révoquée '
                       'ou expirée.'},
            status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {'detail': 'Compte créé — vous pouvez maintenant vous connecter.'})
