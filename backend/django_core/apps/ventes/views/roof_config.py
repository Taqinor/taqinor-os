"""Configuration carte pour l'outil de conception 3D de toiture (ERP).

Endpoint de LECTURE SEULE, authentifié (cookie httpOnly via la session ERP),
servi MÊME ORIGINE que le frontend ERP. La page ``ToitureDesign`` le lit pour
obtenir la clé MapTiler (et le token Mapbox optionnel) du builder roofPro11 sans
appel cross-origin vers taqinor.ma et sans exposer la clé dans le bundle front.

Les valeurs viennent des variables d'environnement ERP
(``PUBLIC_MAPTILER_KEY`` / ``PUBLIC_MAPBOX_TOKEN``), posées au déploiement.
``available`` est vrai dès qu'une clé MapTiler est présente (la carte ne peut
booter sans elle)."""
import os

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole


@api_view(['GET'])
@permission_classes([IsAnyRole])
def roof_config(request):
    """GET /ventes/roof-config/

    Renvoie ``{available, maptilerKey, mapboxToken}`` pour le builder 3D. Tout
    utilisateur authentifié de l'ERP y a accès (auth cookie par défaut DRF).
    Aucune écriture, aucune donnée société : seules les clés carte d'environnement
    sont renvoyées."""
    maptiler = os.environ.get('PUBLIC_MAPTILER_KEY', '') or ''
    mapbox = os.environ.get('PUBLIC_MAPBOX_TOKEN', '') or ''
    return Response({
        'available': bool(maptiler),
        'maptilerKey': maptiler,
        'mapboxToken': mapbox or None,
    })
