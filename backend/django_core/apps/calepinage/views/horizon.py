"""CAL92/93 — la vue ``GET /calepinages/<pk>/horizon/`` du contrat CAL92.

POURQUOI CE FICHIER EST À PART DE ``views/calepinages.py``
------------------------------------------------------------
Même discipline que ``views/equipements.py`` (CAL243) : plusieurs lanes
``backend/calepinage-*`` travaillent en ce moment sur ``views/calepinages.py``
(fichier file-disjoint par construction du plan de lanes,
``scripts/plan_lanes.py``) — y ajouter une méthode dessus créerait un conflit
de fusion garanti. L'action est donc posée ICI, sur son propre fichier, puis
RATTACHÉE au ``CalepinageViewSet`` par une seule ligne d'import dans
``urls.py``, AVANT ``router.register(...)`` pour que
``DefaultRouter.get_extra_actions()`` la découvre.

CE QUE CETTE VUE GARANTIT
--------------------------
Le service CAL92 (``services/horizon.ClientHorizon``) sait déjà obtenir un
profil d'horizon PVGIS ``printhorizon`` mais n'était exposé par AUCUNE route
HTTP — l'écran CAL93 (``HorizonPanel.jsx``) ne connaissait que la saisie
manuelle. Cette action :

1. lit l'épingle du site (même source que ``contexte_geographique`` /
   ``roof_layout['pin']``) ; sans épingle, ``points`` reste ``[]`` et
   ``detail`` le dit — jamais une erreur HTTP pour un état normal de
   l'atelier (un calepinage sans pin n'est pas une panne) ;
2. interroge PVGIS via ``ClientHorizon`` (réseau injectable, même cadence et
   même cache que les autres clients PVGIS du module) ;
3. republie chaque point dans le repère de FACE de l'écran (``azimuthDeg``,
   0=Nord) — jamais le repère PVGIS (0=Sud) tel quel ;
4. PVGIS injoignable ou incohérent (``PvgisIndisponible``) ⇒ AUCUN horizon
   plat n'est inventé : ``points`` reste ``[]``, ``source`` vaut ``None`` et
   ``detail`` NOMME la raison en français (CAL92).

Cette route ne sert QUE l'appel réseau — ``source`` vaut toujours ``pvgis``
ou ``None`` ici, jamais ``saisie`` : la correction manuelle reste locale à
``HorizonPanel.jsx`` jusqu'à son enregistrement dans
``roof_layout.horizonProfile`` (``layout``/``enregistrerLayoutCalepinage``,
CAL18).
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..services.horizon import ClientHorizon
from ..services.pvgis_serie import EntreeInvalide, PvgisIndisponible
from .calepinages import CalepinageViewSet

__all__ = ['horizon', 'profil_horizon_pour']


def _reponse_vide(calepinage, *, detail):
    return {
        'calepinage': calepinage.pk,
        'source': None,
        'points': [],
        'hauteurMaxDeg': None,
        'baseHorizon': None,
        'altitudeM': None,
        'source_url': None,
        'obtenu_le': None,
        'detail': detail,
    }


def profil_horizon_pour(calepinage, *, client=None):
    """Le profil d'horizon d'un calepinage — jamais un horizon plat inventé.

    Sépare de l'action DRF pour être testable sans requête HTTP : un test
    unitaire appelle directement cette fonction avec un ``client``
    (``ClientHorizon``) au transport ENREGISTRÉ (jamais le réseau).
    """
    from .. import selectors as cal_selectors

    geo = cal_selectors.contexte_geographique(calepinage)
    layout = getattr(calepinage, 'roof_layout', None)
    pin = (layout.get('pin') if isinstance(layout, dict) else None) or geo['pin']
    if not isinstance(pin, dict) or pin.get('lat') is None or pin.get('lng') is None:
        return _reponse_vide(
            calepinage,
            detail="Aucune épingle n'est posée sur ce calepinage : "
                   'impossible d’interroger PVGIS sans coordonnées.')

    cli = client or ClientHorizon()
    try:
        profil = cli.profil_horizon(lat=pin['lat'], lon=pin['lng'])
    except PvgisIndisponible as indispo:
        return _reponse_vide(calepinage, detail=indispo.motif)
    except EntreeInvalide as refus:
        return _reponse_vide(calepinage, detail=str(refus))

    from datetime import datetime, timezone

    return {
        'calepinage': calepinage.pk,
        'source': profil['source'],
        'points': [
            {'azimuthDeg': p['azimut_face_deg'], 'heightDeg': p['hauteur_deg']}
            for p in profil['points']
        ],
        'hauteurMaxDeg': profil['hauteur_max_deg'],
        'baseHorizon': profil['base_horizon'],
        'altitudeM': profil['altitude_m'],
        'source_url': profil['url'],
        'obtenu_le': datetime.now(timezone.utc).isoformat(),
        'detail': None,
    }


@extend_schema(responses=inline_serializer('CalepinageHorizon', {
    'calepinage': drf_serializers.IntegerField(),
    'source': drf_serializers.CharField(allow_null=True),
    'points': drf_serializers.ListField(child=drf_serializers.DictField()),
    'hauteurMaxDeg': drf_serializers.FloatField(allow_null=True),
    'baseHorizon': drf_serializers.CharField(allow_null=True),
    'altitudeM': drf_serializers.FloatField(allow_null=True),
    'source_url': drf_serializers.CharField(allow_null=True),
    'obtenu_le': drf_serializers.CharField(allow_null=True),
    'detail': drf_serializers.CharField(allow_null=True),
}))
@action(detail=True, methods=['get'], url_path='horizon',
        permission_classes=[PeutVoirCalepinage])
def horizon(self, request, pk=None):
    """CAL92/93 — le profil d'horizon PVGIS du site (contrat CAL92)."""
    return Response(profil_horizon_pour(self.get_object()))


# Rattachement au viewset PIVOT — voir la docstring du module pour le
# pourquoi de cette forme plutôt qu'une méthode inline.
CalepinageViewSet.horizon = horizon
