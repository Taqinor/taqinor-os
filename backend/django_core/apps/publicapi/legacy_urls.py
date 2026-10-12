"""NTAPI1 — alias de compatibilité de la racine publique NON versionnée.

``/api/public/<n'importe quoi>`` redirige DÉFINITIVEMENT vers
``/api/public/v1/<la même chose>`` pendant 12 mois
(``constants.PUBLIC_API_LEGACY_SUNSET``). Aucune clé existante n'est cassée :
tout client HTTP suit une redirection permanente, et la clé (en-tête
``Authorization``) est ré-émise sur la cible — même hôte, même schéma.

Méthode PRÉSERVÉE : un GET/HEAD reçoit **301** (le code annoncé par NTAPI1),
mais une écriture (POST/PATCH/PUT/DELETE) reçoit **308**. La raison est un vrai
bug évité, pas du zèle : la RFC autorise un client à retomber en GET sur un 301,
ce qui transformerait silencieusement un ``POST /api/public/leads-write/`` en
lecture et perdrait le corps ; 308 interdit explicitement cette conversion.

Cette urlconf est montée APRÈS le routeur versionné dans l'urlconf racine, donc
elle ne voit que les chemins qu'aucune route v1 n'a servis. Elle refuse malgré
tout explicitement un chemin déjà versionné (404) : sans cette garde, un
``/api/public/v1/inconnu`` serait redirigé vers ``/api/public/v1/v1/inconnu``
puis à l'infini.
"""
from django.http import HttpResponsePermanentRedirect, JsonResponse
from django.urls import re_path
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .constants import (
    PUBLIC_API_BASE,
    PUBLIC_API_LEGACY_SUNSET,
    PUBLIC_API_VERSIONS,
)

# Méthodes sûres : un 301 est sans danger (aucun corps à perdre).
_SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


class _PermanentRedirect308(HttpResponsePermanentRedirect):
    """308 Permanent Redirect — 301 « qui ne change pas la méthode »."""
    status_code = 308


@method_decorator(csrf_exempt, name='dispatch')
class LegacyPublicApiRedirectView(View):
    """Redirige la racine non versionnée vers la racine versionnée courante.

    ENF11 — ``csrf_exempt`` : cette vue ne lit ni ne modifie rien (redirection
    ou 404). Sans cela, un POST/PATCH vers un chemin versionné non résolu
    (identifiant mal formé) recevait la page HTML 403 du middleware CSRF au
    lieu d'un 404 ; le 404 est désormais rendu en JSON (enveloppe publique)."""

    def dispatch(self, request, rest='', *args, **kwargs):
        premier_segment = (rest or '').split('/', 1)[0]
        if premier_segment in PUBLIC_API_VERSIONS:
            # Déjà versionné : c'est un 404 de route, jamais une redirection
            # (sinon boucle `/v1/v1/v1/…`).
            return JsonResponse({'error': {
                'type': 'invalid_request_error',
                'code': 'not_found',
                'message': 'Route inconnue de cette version de l’API publique.',
                'param': None,
                'doc_url': '/api/public/v1/errors/#not_found',
                'request_id': getattr(request, 'request_id', None),
            }}, status=404)
        cible = f'{PUBLIC_API_BASE}{rest or ""}'
        query = request.META.get('QUERY_STRING', '')
        if query:
            cible = f'{cible}?{query}'
        redirect_class = (HttpResponsePermanentRedirect
                          if request.method in _SAFE_METHODS
                          else _PermanentRedirect308)
        response = redirect_class(cible)
        # RFC 8594 — l'alias est daté : une intégration qui ne migre pas voit
        # l'échéance dans ses propres journaux, sans lire la doc.
        response['Deprecation'] = 'true'
        response['Sunset'] = PUBLIC_API_LEGACY_SUNSET
        return response


urlpatterns = [
    re_path(r'^(?P<rest>.*)$', LegacyPublicApiRedirectView.as_view(),
            name='public-legacy-alias'),
]
