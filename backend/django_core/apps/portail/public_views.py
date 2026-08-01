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
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .branding import MARQUE_VIDE, company_pour_hote, marque_portail


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
