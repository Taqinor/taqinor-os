"""CALX107 câblage — ``GET calepinages/<pk>/plan-importe/`` : le FICHIER du fond.

LE TROU QUE CETTE PORTE BOUCHE
-------------------------------
Le document v2 peut porter un calque de fond (``underlay``, contrat CALX86).
De genre ``plan``, il désigne la PIÈCE JOINTE qui porte le fichier
(``attachmentId``). L'atelier sait peindre ce fond
(``roofPro11/underlay.ts`` + ``mapDraw.setFond``) mais il ne parle jamais à
Django : il attend de la page hôte une ``RessourceFond`` (``url``,
``tailleImage``). Or AUCUNE porte ne publiait l'URL ni les dimensions de cette
pièce — ``POST calepinages/<pk>/importer-plan/`` rend un contour et ne
conserve même pas le fichier, et ``GET calepinages/<pk>/photos/`` ne sert que
les ``PhotoSite``. Un dossier rouvert avec un fond de genre ``plan`` restait
donc muet alors que le document le portait.

LES CONVENTIONS SONT CELLES DE ``services/photos.py::photo_en_ligne``
----------------------------------------------------------------------
``url`` est PRÉ-SIGNÉE (le magasin d'objets de ``roof-image``, via les
fonctions minces d'``apps.ventes.services``) et vaut ``''`` quand le magasin ne
répond pas : jamais un chemin disque, jamais un lien mort présenté comme
valide.

AUCUNE DIMENSION N'EST DEVINÉE (D-CALX 7)
------------------------------------------
``largeur`` et ``hauteur`` sont les pixels NATURELS du fichier, LUS dans son
en-tête (PNG : bloc ``IHDR`` ; JPEG : segment ``SOF``). Un fichier absent du
magasin, ou d'un format dont l'en-tête ne porte pas ses dimensions, rend
``null`` / ``null`` avec un ``motif`` qui DIT ce qui manque : l'atelier refuse
alors le plan avec sa propre phrase (``MOTIF_PLAN_NON_CALE``) plutôt que
d'étaler l'image sur une étendue supposée.

LECTURE PURE : aucun statut, aucun champ, aucune ligne de journal n'est
écrit ; l'échelle d'un plan reste celle des deux points et de la distance
réelle SAISIE (CALX108), jamais celle du fichier.

LA GREFFE (piège de classe #105)
---------------------------------
L'action est posée sur le viewset pivot par AFFECTATION D'ATTRIBUT, et le nom
de l'attribut est EXACTEMENT ``fonction.__name__`` : DRF mappe par
``__name__``, un nom qui diverge fait disparaître la route. L'import qui
exécute ce module vit en FIN de ``views/rattachements.py``, donc AVANT
``router.register``.
"""
from __future__ import annotations

import struct

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage

__all__ = ['plan_importe', 'dimensions_image', 'SANS_FOND', 'FOND_PHOTO',
           'SANS_PIECE', 'PIECE_INTROUVABLE', 'MOTIF_FICHIER_ABSENT',
           'motif_taille_inconnue']

SANS_FOND = ("Ce calepinage n’a pas de plan importé en fond : son document ne "
             "demande aucun calque de fond.")

FOND_PHOTO = ("Ce calepinage n’a pas de plan importé en fond : son calque de "
              "fond est une photo de site, servie par GET "
              "calepinages/<pk>/photos/ avec son calage à quatre coins.")

SANS_PIECE = ("Le fond de genre « plan » de ce calepinage ne désigne aucune "
              "pièce jointe (champ « attachmentId » du document) : il n’y a "
              "donc aucun fichier à servir.")

PIECE_INTROUVABLE = ("La pièce jointe désignée comme plan de fond n’est pas "
                     "rattachée à ce calepinage : rien n’est servi, et "
                     "aucune autre pièce n’est proposée à sa place.")

MOTIF_FICHIER_ABSENT = ("Le fichier du plan n’a pas pu être lu dans le "
                        "magasin d’objets : ses dimensions restent inconnues "
                        "et le fond ne peut pas être posé.")


def motif_taille_inconnue(nom_fichier):
    """Le motif d'une taille non lisible — il NOMME le fichier en cause."""
    return (f"Les dimensions de « {nom_fichier or 'ce fichier'} » ne sont pas "
            "lisibles dans son en-tête (PNG et JPEG le portent) : le fond ne "
            "peut pas être étendu sans les inventer.")


#: En-tête d'un PNG : signature (8 octets), longueur + type de bloc (8), puis
#: largeur et hauteur sur 4 octets big-endian chacune (norme PNG, § IHDR).
_PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
_PNG_IHDR = 16

#: Marqueurs JPEG « Start Of Frame » qui portent les dimensions de l'image.
#: Les trois exclus (``\xc4`` tables de Huffman, ``\xc8`` réservé, ``\xcc``
#: table arithmétique) ne sont PAS des SOF malgré leur voisinage numérique.
_JPEG_SOF = tuple(m for m in range(0xC0, 0xD0) if m not in (0xC4, 0xC8, 0xCC))


def _dimensions_png(octets):
    if len(octets) < _PNG_IHDR + 8:
        return None, None
    largeur, hauteur = struct.unpack('>II', octets[_PNG_IHDR:_PNG_IHDR + 8])
    if largeur <= 0 or hauteur <= 0:
        return None, None
    return largeur, hauteur


def _dimensions_jpeg(octets):
    i, fin = 2, len(octets)
    while i + 1 < fin:
        if octets[i] != 0xFF:
            i += 1
            continue
        marqueur = octets[i + 1]
        # Bourrage entre segments : une suite de ``\xff`` est licite.
        if marqueur == 0xFF:
            i += 1
            continue
        # Marqueurs SANS segment de longueur (début/fin d'image, redémarrages).
        if marqueur in (0x01, 0xD8, 0xD9) or 0xD0 <= marqueur <= 0xD7:
            i += 2
            continue
        if i + 4 > fin:
            return None, None
        taille = struct.unpack('>H', octets[i + 2:i + 4])[0]
        if taille < 2:
            return None, None
        if marqueur in _JPEG_SOF:
            if i + 9 > fin:
                return None, None
            hauteur, largeur = struct.unpack('>HH', octets[i + 5:i + 9])
            if largeur <= 0 or hauteur <= 0:
                return None, None
            return largeur, hauteur
        i += 2 + taille
    return None, None


def dimensions_image(octets):
    """``(largeur, hauteur)`` en pixels NATURELS, ou ``(None, None)``.

    Les dimensions sont LUES dans l'en-tête du fichier — bloc ``IHDR`` d'un
    PNG, segment ``SOF`` d'un JPEG : les deux seuls formats que le magasin
    d'objets accepte pour une image (``SIGNATURES_IMAGE_TOITURE``). Tout autre
    contenu rend ``(None, None)`` : l'appelant DIT alors qu'il ne connaît pas
    la taille, il ne la suppose pas.

    PURE : aucun accès réseau, aucune base, aucune bibliothèque d'image.
    """
    octets = octets or b''
    if octets[:len(_PNG_SIGNATURE)] == _PNG_SIGNATURE:
        return _dimensions_png(octets)
    if octets[:3] == b'\xff\xd8\xff':
        return _dimensions_jpeg(octets)
    return None, None


def _forme():
    """YAPIC6/PACT7 — la forme DÉCLARÉE, tirée du contrat CALX107."""
    return inline_serializer('CalepinagePlanImporte', {
        'calepinage': serializers.IntegerField(),
        'attachment': serializers.IntegerField(),
        'filename': serializers.CharField(),
        'mime': serializers.CharField(),
        'url': serializers.CharField(allow_blank=True),
        'largeur': serializers.IntegerField(allow_null=True),
        'hauteur': serializers.IntegerField(allow_null=True),
        'motif': serializers.CharField(allow_blank=True),
    })


def _absent(champ, detail):
    """404 qui NOMME son champ — jamais un « non trouvé » générique."""
    return Response({'detail': detail, 'champ': champ},
                    status=status.HTTP_404_NOT_FOUND)


def _piece_du_calepinage(calepinage, attachment_id):
    """La pièce jointe ``attachment_id`` RATTACHÉE à ce calepinage, ou ``None``.

    Bornée société ET dossier : une pièce d'une autre société ou d'un autre
    calepinage est INTROUVABLE, jamais « interdite » (pas d'oracle
    d'existence).
    """
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Attachment

    return (Attachment.objects
            .filter(pk=attachment_id,
                    company=calepinage.company,
                    content_type=ContentType.objects.get_for_model(
                        type(calepinage)),
                    object_id=calepinage.pk)
            .first())


@extend_schema(responses={200: _forme()})
@action(detail=True, methods=['get'], url_path='plan-importe',
        url_name='plan-importe', permission_classes=[PeutVoirCalepinage])
def plan_importe(self, request, pk=None):
    """CALX107 — l'URL servie et la taille en pixels du plan de fond.

    Les huit clés sont TOUJOURS présentes. ``largeur``/``hauteur`` valent
    ``null`` quand l'en-tête du fichier ne les porte pas, et ``motif`` dit
    alors POURQUOI : une taille supposée poserait le fond sur une étendue
    fausse.
    """
    from apps.ventes import services as ventes_services

    calepinage = self.get_object()  # borné société par get_queryset

    document = calepinage.roof_layout
    fond = document.get('underlay') if isinstance(document, dict) else None
    if not isinstance(fond, dict):
        return _absent('underlay', SANS_FOND)
    if fond.get('kind') != 'plan':
        return _absent('kind', FOND_PHOTO)
    attachment_id = fond.get('attachmentId')
    if isinstance(attachment_id, bool) or not isinstance(attachment_id, int):
        return _absent('attachmentId', SANS_PIECE)

    piece = _piece_du_calepinage(calepinage, attachment_id)
    if piece is None:
        return _absent('attachmentId', PIECE_INTROUVABLE)

    try:
        url = ventes_services.url_image_toiture(piece.file_key) or ''
    except Exception:       # pragma: no cover - dépend du stockage
        url = ''

    contenu = ventes_services.lire_fichier_toiture(piece.file_key)
    if not contenu:
        largeur, hauteur, motif = None, None, MOTIF_FICHIER_ABSENT
    else:
        largeur, hauteur = dimensions_image(contenu)
        motif = ('' if largeur and hauteur
                 else motif_taille_inconnue(piece.filename))

    return Response({
        'calepinage': calepinage.pk,
        'attachment': piece.pk,
        'filename': piece.filename,
        'mime': piece.mime or '',
        'url': url,
        'largeur': largeur,
        'hauteur': hauteur,
        'motif': motif,
    })


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7 / bug de classe #105).
CalepinageViewSet.plan_importe = plan_importe
