"""CALX62 — la PORTE HTTP du dépôt d'une série météo horaire de la société.

CE QU'ELLE FAIT
---------------
``POST calepinages/<pk>/meteo-fichier/`` (``multipart/form-data``) :

1. elle LIT le fichier avec ``services/meteo_fichier.py`` — donc elle le
   REFUSE tout de suite s'il n'est pas exploitable, en nommant la colonne (et
   la ligne) fautive plutôt qu'en acceptant un dépôt qui se révélerait faux au
   moment de la simulation ;
2. elle le DÉPOSE dans le magasin d'objets du dépôt et crée sa ligne
   ``records.Attachment`` rattachée au calepinage (primitive plateforme,
   ARC26 : aucun champ fichier dans les modèles du module — c'est déjà le
   chemin des photos de site, CAL52, et aucun second magasin n'est ouvert) ;
3. elle rend la PROVENANCE (bloc ``meteo`` de CALX143, ``service='fichier'``,
   fournisseur saisi, nom, taille, empreinte SHA-256) et un RÉSUMÉ de la
   série — jamais ses 8 760 points, qui pèseraient plusieurs mégaoctets dans
   une réponse HTTP.

CE QU'ELLE NE FAIT PAS
----------------------
Elle ne LANCE aucune simulation et ne touche aucun ``resultat``. Le
branchement « la simulation prend ce fichier plutôt que PVGIS » appartient à
l'orchestrateur de simulation (``services/simulation.py``, CALX5), qui
n'existe pas encore dans le dépôt : ce que cette porte garantit, c'est que la
série déposée est LISIBLE et que sa provenance est publiée, à la forme exacte
que la chaîne consomme (``ClientPvgis.serie_irradiance``, CALX150).

Elle n'invente non plus AUCUN fournisseur : celui-ci est SAISI, et un dépôt
sans fournisseur est refusé en nommant le champ. Une série météo dont on ne
sait pas d'où elle vient est un chiffre orphelin le lendemain.

LE CORPS EST DU TEXTE, TOUJOURS
-------------------------------
En ``multipart/form-data`` tout arrive en TEXTE : aucun booléen n'est lu de ce
corps (une case décochée envoyée « false » est une chaîne non vide, donc VRAIE
pour un ``BooleanField``). Cette porte n'a rien à basculer.

La société est forcée par le serveur : ``self.get_object()`` passe par le
``get_queryset`` du viewset pivot, donc un calepinage d'une autre société est
INTROUVABLE (404), jamais « interdit ». L'objet est résolu AVANT toute
validation du fichier : répondre « fichier manquant » sur un objet qui
n'existe pas pour cet appelant serait un oracle d'existence par la bande.

Même forme que ``views/import_plan.py`` : le code vit dans son propre fichier
et l'action est RATTACHÉE au ``CalepinageViewSet`` par affectation d'attribut
de classe, depuis l'import unique de ``views/rattachements.py`` exécuté AVANT
``router.register``.
"""
from __future__ import annotations

from uuid import uuid4

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage
from ..services.meteo_fichier import (
    MeteoFichierRefuse, OCTETS_MAX, lire_serie_meteo,
)
from .calepinages import CalepinageViewSet

__all__ = ['meteo_fichier', 'CHAMP_FICHIER', 'CHAMP_FOURNISSEUR',
           'SANS_FICHIER', 'SANS_FOURNISSEUR', 'TROP_LOURD']

#: Le champ du formulaire qui porte le fichier — nommé dans CHAQUE refus.
CHAMP_FICHIER = 'fichier'

#: Le champ qui porte le fournisseur SAISI de la série.
CHAMP_FOURNISSEUR = 'fournisseur'

SANS_FICHIER = ('Aucun fichier météo déposé : ajoutez un CSV dans le champ '
                '« fichier ».')
SANS_FOURNISSEUR = (
    "Indiquez le fournisseur de cette série météo (station, bureau d'études, "
    'éditeur du fichier) : une série dont la provenance n\'est pas écrite '
    'devient un chiffre sans origine dès le lendemain.')
TROP_LOURD = ('Ce fichier dépasse {0} Mo : un CSV météo au pas horaire ne '
              'pèse jamais autant.'.format(OCTETS_MAX // (1024 * 1024)))

MESSAGE_DEPOSE = (
    'Série météo enregistrée et rattachée au calepinage. Elle ne relance '
    'aucun calcul : la simulation la reprendra à son prochain lancement.')


def _forme():
    """YAPIC6/PACT7 — la forme DÉCLARÉE, tirée du contrat CALX62."""
    return inline_serializer('CalepinageMeteoFichier', {
        'calepinage': serializers.IntegerField(),
        'piece_jointe': serializers.IntegerField(),
        'meteo': serializers.DictField(),
        'serie': serializers.DictField(),
        'message': serializers.CharField(),
    })


def _refus(champ, message, ligne=None):
    corps = {champ: [message]}
    if ligne is not None:
        corps['ligne'] = ligne
    return Response(corps, status=status.HTTP_400_BAD_REQUEST)


def _deposer(calepinage, contenu, nom_fichier, user):
    """Le fichier dans le magasin d'objets, sa ligne ``records.Attachment``.

    Rien n'est écrit tant que la série n'a pas été LUE : un dépôt refusé ne
    laisse donc aucun objet orphelin derrière lui.
    """
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Attachment
    from apps.ventes import services as ventes_services

    cle = ('meteo/{0}/calepinage-{1}-{2}.csv'.format(
        calepinage.company_id or 0, calepinage.pk, uuid4().hex))
    ventes_services.stocker_image_toiture(contenu, cle,
                                          content_type='text/csv')
    return Attachment.objects.create(
        company=calepinage.company,
        content_type=ContentType.objects.get_for_model(type(calepinage)),
        object_id=calepinage.pk,
        file_key=cle,
        filename=(nom_fichier or 'meteo.csv')[:255],
        size=len(contenu),
        mime='text/csv',
        uploaded_by=user if getattr(user, 'pk', None) else None,
    )


@extend_schema(responses={201: _forme()})
@action(detail=True, methods=['post'], url_path='meteo-fichier',
        url_name='meteo-fichier',
        permission_classes=[PeutGererCalepinage],
        parser_classes=[MultiPartParser, FormParser])
def meteo_fichier(self, request, pk=None):
    """CALX62 — ``POST /calepinages/<pk>/meteo-fichier/``.

    Corps ``multipart/form-data`` : ``fichier`` (CSV, obligatoire) et
    ``fournisseur`` (texte, obligatoire).

    * **201** — la série est lisible : le fichier est rattaché au calepinage
      et la réponse porte sa provenance (``meteo``) et le résumé de la série ;
    * **400** — refus en NOMMANT le champ : ``fichier`` (absent, vide, trop
      lourd, illisible), ``fournisseur`` (non saisi), ou la COLONNE fautive du
      CSV (``horodatage``, ``gi_w_m2``, ``ghi_w_m2``…) avec, quand elle est
      connue, la LIGNE du fichier.
    """
    # L'OBJET D'ABORD : un calepinage d'une autre société rend 404 quel que
    # soit le corps envoyé.
    calepinage = self.get_object()  # borné société par get_queryset

    fichier = request.FILES.get(CHAMP_FICHIER)
    if fichier is None:
        return _refus(CHAMP_FICHIER, SANS_FICHIER)
    taille = getattr(fichier, 'size', None)
    if isinstance(taille, int) and taille > OCTETS_MAX:
        return _refus(CHAMP_FICHIER, TROP_LOURD)

    fournisseur = str(request.data.get(CHAMP_FOURNISSEUR) or '').strip()
    if not fournisseur:
        return _refus(CHAMP_FOURNISSEUR, SANS_FOURNISSEUR)

    nom_fichier = str(getattr(fichier, 'name', '') or '')
    contenu = fichier.read()
    if isinstance(contenu, str):
        contenu = contenu.encode('utf-8')
    try:
        serie = lire_serie_meteo(contenu, fournisseur=fournisseur,
                                 nom_fichier=nom_fichier)
    except MeteoFichierRefuse as refus:
        return _refus(refus.champ or CHAMP_FICHIER, refus.motif,
                      ligne=refus.ligne)

    piece = _deposer(calepinage, contenu, nom_fichier, request.user)
    bloc = serie['serie_horaire']
    return Response({
        'calepinage': calepinage.pk,
        'piece_jointe': piece.pk,
        'meteo': serie['meteo'],
        # Le RÉSUMÉ, jamais les points : une série horaire pèse plusieurs
        # mégaoctets, et l'écran n'a rien à en faire ici.
        'serie': {
            'points': len(serie['points']),
            'annees': serie['annees'],
            'pas_minutes': bloc['pas_minutes'],
            'tronquee': bloc['tronquee'],
            'colonnes': bloc['colonnes'],
            'composantes_disponibles': serie['composantes_disponibles'],
            'motif_composantes': serie['motif_composantes'],
        },
        'message': MESSAGE_DEPOSE,
    }, status=status.HTTP_201_CREATED)


# Rattachement au viewset PIVOT — voir la docstring du module.
CalepinageViewSet.meteo_fichier = meteo_fichier
