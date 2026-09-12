"""NTAPI19 — `POST /api/public/v1/oauth/token/` (grant `client_credentials`).

Échange, UNE fois, un secret permanent contre un jeton COURT. L'endpoint est
lui-même non authentifié (c'est lui qui authentifie : ``client_id`` +
``client_secret`` dans le corps, comme chez tout fournisseur OAuth2) — d'où le
throttle explicite, indispensable puisque c'est la seule surface de l'API
publique où l'on peut tenter un secret.

RÉPONSES D'ERREUR UNIFORMES. Un ``client_id`` inconnu, un client désactivé et
un secret faux renvoient le MÊME 401 avec le MÊME message : autrement, un
attaquant distinguerait « ce client existe » de « ce client n'existe pas » et
aurait la moitié du travail fait.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import OAuthClient
from .oauth import GRANT_TYPE, emettre_token
from .public_response import PublicApiResponseMixin

# Message UNIQUE pour tout échec d'identification — jamais de distinction entre
# « client inconnu », « client désactivé » et « secret faux ».
_ECHEC = "Identifiants client invalides."


def _erreur(code, message, *, param=None, statut=status.HTTP_401_UNAUTHORIZED,
            request=None):
    """Enveloppe d'erreur NTAPI3, posée à la main : cette vue renvoie ses
    erreurs d'authentification en `Response` plutôt qu'en exception, pour
    garder un corps STRICTEMENT identique quel que soit le motif."""
    return Response(
        {'error': {
            'type': ('authentication_error'
                     if statut == status.HTTP_401_UNAUTHORIZED
                     else 'invalid_request_error'),
            'code': code,
            'message': message,
            'param': param,
            'doc_url': f'/api/public/v1/errors/#{code}',
            'request_id': getattr(request, 'request_id', None),
        }},
        status=statut)


@extend_schema(
    summary='Jeton OAuth2 client_credentials (NTAPI19).',
    request=inline_serializer('PublicOAuthTokenRequest', {
        'grant_type': serializers.CharField(),
        'client_id': serializers.CharField(),
        'client_secret': serializers.CharField(),
        'scope': serializers.CharField(required=False),
    }),
    responses=inline_serializer('PublicOAuthToken', {
        'access_token': serializers.CharField(),
        'token_type': serializers.CharField(),
        'expires_in': serializers.IntegerField(),
        'scope': serializers.CharField(),
    }),
)
class PublicOAuthTokenView(PublicApiResponseMixin, APIView):
    """``POST /api/public/v1/oauth/token/`` — délivre un jeton court."""

    authentication_classes = []
    permission_classes = [AllowAny]
    # YRBAC9 — surface anonyme ET seule surface où un secret peut être deviné :
    # throttle explicite par IP, scope dédié (jamais le throttle par clé, qui
    # serait inopérant ici puisqu'aucune clé n'est encore résolue).
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'publicapi_oauth_token'

    def post(self, request):
        corps = request.data or {}
        grant = (corps.get('grant_type') or '').strip()
        if grant != GRANT_TYPE:
            return _erreur(
                'unsupported_grant_type',
                f"Seul le grant « {GRANT_TYPE} » est accepté.",
                param='grant_type',
                statut=status.HTTP_400_BAD_REQUEST, request=request)

        client_id = (corps.get('client_id') or '').strip()
        client_secret = corps.get('client_secret') or ''
        oauth_client = OAuthClient.objects.filter(
            client_id=client_id, actif=True).first() if client_id else None
        # Réponse IDENTIQUE dans les trois cas d'échec (cf. docstring).
        if oauth_client is None or not oauth_client.verifie_secret(client_secret):
            return _erreur('invalid_client', _ECHEC, request=request)

        scope_demande = (corps.get('scope') or '').split()
        jeton, expire_in = emettre_token(
            oauth_client, scopes=scope_demande or None)
        accordes = (
            [s for s in scope_demande if oauth_client.has_scope(s)]
            if scope_demande else list(oauth_client.scopes or []))
        return Response({
            'access_token': jeton,
            'token_type': 'Bearer',
            'expires_in': expire_in,
            'scope': ' '.join(accordes),
        })
