"""CAL52 — la sous-ressource « photos de site » du pivot.

UNE SEULE FORME D'URL (CAL233) : la photo est une SOUS-RESSOURCE du
calepinage, donc elle s'expose en ``@action`` du viewset pivot
(``/api/django/calepinage/calepinages/<pk>/photos/``) — jamais en seconde
famille d'URL. Le mixin vit dans SON fichier pour que la lane « site » et la
lane « pivot » restent file-disjointes : ``views/calepinages.py`` n'ajoute
qu'une base à la classe.

CE QUE L'ACTION GARANTIT
------------------------
* **L'OBJET D'ABORD (CAL29)** — ``self.get_object()`` est appelé AVANT toute
  lecture du corps : un calepinage d'une autre société rend 404 quel que soit
  le fichier envoyé. Valider le fichier d'abord répondrait « fichier
  manquant » sur un objet qui, pour cet appelant, n'existe pas — un oracle
  d'existence par la bande.
* **La société et l'auteur viennent du SERVEUR**, jamais du corps.
* **Le refus NOMME le champ** (``photo``, ``prise_le``, ``genre``), en
  français, sous le champ fautif — jamais un « non enregistré » générique.
* **Aucun statut ne bouge** (règle #4) : ranger une photo n'est pas un
  événement commercial.
"""
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from ..permissions import PeutLireOuEcrireCalepinage

__all__ = ['PhotosSiteMixin']


class PhotosSiteMixin:
    """``GET``/``POST`` ``calepinages/<pk>/photos/`` — les photos du site."""

    @action(detail=True, methods=['get', 'post'], url_path='photos',
            permission_classes=[PeutLireOuEcrireCalepinage],
            parser_classes=[MultiPartParser, FormParser])
    def photos(self, request, pk=None):
        from ..selectors import photos_site
        from ..services.photos import PhotoRefusee, ajouter_photo_site

        # L'OBJET D'ABORD (CAL29) : borné société par ``get_queryset``.
        calepinage = self.get_object()

        if request.method.lower() == 'get':
            return Response({'photos': photos_site(calepinage)})

        try:
            photo = ajouter_photo_site(
                calepinage,
                request.FILES.get('photo') or request.FILES.get('file'),
                genre=request.data.get('genre'),
                prise_le=request.data.get('prise_le'),
                legende=request.data.get('legende') or '',
                user=request.user,
            )
        except PhotoRefusee as refus:
            return Response({refus.champ or 'detail': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)

        from ..services.photos import photo_en_ligne

        return Response({'photo': photo_en_ligne(photo),
                         'photos': photos_site(calepinage)},
                        status=status.HTTP_201_CREATED)

    #: YAPIC6 — ``photo_id`` n'est pas un champ du pivot : sans cette déclaration,
    #: drf-spectacular publie un paramètre de chemin sans type.
    @extend_schema(parameters=[OpenApiParameter(
        name='photo_id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH,
        description="Identifiant de la photo de site (sous-ressource du calepinage).")])
    @action(detail=True, methods=['patch'],
            url_path=r'photos/(?P<photo_id>[^/.]+)/calage',
            permission_classes=[PeutLireOuEcrireCalepinage])
    def photo_calage(self, request, pk=None, photo_id=None):
        """CAL53 — pose (ou efface) le calage des 4 coins d'UNE photo de site.

        L'OBJET D'ABORD (CAL29) : le calepinage est résolu par
        ``self.get_object()`` (borné société), PUIS la photo est cherchée
        DANS ses photos — une photo d'un autre calepinage, ou d'une autre
        société, rend 404 sans jamais dire si elle existe ailleurs. Aucun
        statut ne bouge (règle #4) : caler une photo n'est pas un événement
        commercial.
        """
        from ..selectors import photos_site
        from ..services.photos import (
            PhotoRefusee, calage_photo_site, photo_en_ligne,
        )

        calepinage = self.get_object()  # borné société par get_queryset
        photo = calepinage.photos_site.filter(pk=photo_id).first()
        if photo is None:
            return Response({'detail': 'Photo introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            calage_photo_site(photo, request.data.get('calage'))
        except PhotoRefusee as refus:
            return Response({refus.champ or 'detail': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'photo': photo_en_ligne(photo),
                         'photos': photos_site(calepinage)})
