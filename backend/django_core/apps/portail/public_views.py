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
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .branding import MARQUE_VIDE, company_pour_hote, marque_portail


@api_view(['GET'])
@permission_classes([AllowAny])
def theme_portail_public(request):
    """Marque du portail pour le domaine appelant (repli neutre)."""
    company = company_pour_hote(request.get_host())
    if company is None:
        return Response(dict(MARQUE_VIDE))
    return Response(marque_portail(company))
