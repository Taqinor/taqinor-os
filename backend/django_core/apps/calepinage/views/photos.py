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

__all__ = ['PhotosSiteMixin', 'reponse_fichier']


def reponse_fichier(octets, mime_piece=''):
    """ACAL200 — la réponse « image » d'un fichier servi par le proxy Django.

    Le type vient des OCTETS (magic-bytes), jamais du nom ni d'un en-tête
    annoncé ; à défaut, du type enregistré de la pièce s'il est ``image/*``
    (WebP). Ni image ni octets : ``None`` — l'appelant rend 404, le serveur ne
    sert pas un PDF ou un script sous un chemin d'image.
    """
    from django.http import HttpResponse

    from apps.ventes import services as ventes_services

    if not octets:
        return None
    _extension, mime = ventes_services.type_image_toiture(octets)
    if mime is None and str(mime_piece or '').startswith('image/'):
        mime = mime_piece
    if mime is None:
        return None
    reponse = HttpResponse(octets, content_type=mime)
    reponse['X-Content-Type-Options'] = 'nosniff'
    reponse['Cache-Control'] = 'private, max-age=300'
    return reponse


def fichier_introuvable():
    return Response({'detail': 'Fichier introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)


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

    @extend_schema(parameters=[OpenApiParameter(
        name='photo_id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH,
        description="Identifiant de la photo de site (sous-ressource du calepinage).")])
    @action(detail=True, methods=['patch', 'delete'],
            url_path=r'photos/(?P<photo_id>\d+)',
            permission_classes=[PeutLireOuEcrireCalepinage])
    def photo_detail(self, request, pk=None, photo_id=None):
        """ACAL202 — corriger (PATCH genre/prise_le/legende) ou retirer (DELETE)
        UNE photo de site.

        L'OBJET D'ABORD (CAL29) : le calepinage est résolu borné société, puis
        la photo DANS ses photos — d'ailleurs, la même 404. Une date future ou
        un genre inconnu sont refusés comme à la création, en nommant le champ.
        Aucun statut ne bouge (règle #4).
        """
        from ..selectors import photos_site
        from ..services.photos import (
            PhotoRefusee, modifier_photo_site, photo_en_ligne,
            supprimer_photo_site,
        )

        # ACAL277 — import local : ``calepinages.py`` importe CE module.
        from .calepinages import _identifiant_ou_404

        calepinage = self.get_object()  # borné société par get_queryset
        photo = calepinage.photos_site.select_related('attachment').filter(
            pk=_identifiant_ou_404(photo_id)).first()
        if photo is None:
            return Response({'detail': 'Photo introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        if request.method.lower() == 'delete':
            supprimer_photo_site(photo)
            return Response({'photos': photos_site(calepinage)})
        try:
            modifier_photo_site(
                photo, request.data if isinstance(request.data, dict) else {})
        except PhotoRefusee as refus:
            return Response({refus.champ or 'detail': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'photo': photo_en_ligne(photo),
                         'photos': photos_site(calepinage)})

    #: YAPIC6 — ``photo_id`` n'est pas un champ du pivot : sans cette déclaration,
    #: drf-spectacular publie un paramètre de chemin sans type.
    @extend_schema(parameters=[OpenApiParameter(
        name='photo_id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH,
        description="Identifiant de la photo de site (sous-ressource du calepinage).")])
    @action(detail=True, methods=['patch'],
            url_path=r'photos/(?P<photo_id>\d+)/calage',
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

        # ACAL277 — import local : ``calepinages.py`` importe CE module.
        from .calepinages import _identifiant_ou_404

        calepinage = self.get_object()  # borné société par get_queryset
        photo = calepinage.photos_site.filter(
            pk=_identifiant_ou_404(photo_id)).first()
        if photo is None:
            return Response({'detail': 'Photo introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        # ACAL202 — la clé ``calage`` est OBLIGATOIRE : un corps qui l'omet
        # n'efface plus le calage en silence (``null`` explicite = effacer).
        corps = request.data
        if not isinstance(corps, dict) or 'calage' not in corps:
            return Response(
                {'calage': "Clé « calage » obligatoire : un objet "
                           "{coins: [[lat, lng] × 4]}, ou null pour effacer."},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            calage_photo_site(photo, corps['calage'])
        except PhotoRefusee as refus:
            return Response({refus.champ or 'detail': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'photo': photo_en_ligne(photo),
                         'photos': photos_site(calepinage)})

    @extend_schema(
        parameters=[OpenApiParameter(
            name='photo_id', type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="Identifiant de la photo de site.")],
        responses={(200, 'image/*'): OpenApiTypes.BINARY})
    @action(detail=True, methods=['get'],
            url_path=r'photos/(?P<photo_id>[^/.]+)/fichier',
            permission_classes=[PeutLireOuEcrireCalepinage])
    def photo_fichier(self, request, pk=None, photo_id=None):
        """ACAL200 — les OCTETS d'une photo, par Django (même origine).

        L'objet d'abord (société), puis la photo DANS ses photos : une photo
        d'un autre calepinage ou d'une autre société rend la MÊME 404 qu'une
        photo absente. Le bucket est résolu par la clé de la pièce
        (``lire_octets_piece``).
        """
        from ..services.photos import lire_octets_piece

        calepinage = self.get_object()  # borné société par get_queryset
        if not str(photo_id).isdigit():
            return fichier_introuvable()
        photo = (calepinage.photos_site.select_related('attachment')
                 .filter(pk=int(photo_id)).first())
        if photo is None:
            return fichier_introuvable()
        reponse = reponse_fichier(
            lire_octets_piece(photo.attachment.file_key),
            photo.attachment.mime)
        return reponse if reponse is not None else fichier_introuvable()
