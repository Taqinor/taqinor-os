"""CALX39 — la PORTE HTTP de l'import d'un plan (DXF / PDF vectoriel).

LE TROU QU'ELLE BOUCHE
----------------------
``services/import_plan.py`` (CAL62) sait analyser un plan déposé et en tirer
un contour et ses cotes hors-tout ; il est écrit et testé
(``tests/test_import_plan.py``). Mais il n'avait AUCUNE porte HTTP :
``PlanImporteCalage.jsx`` le disait lui-même, et le contour devait donc lui
arriver par une propriété que personne ne fournissait. L'écran de calage
existait, l'analyseur existait, et rien ne les reliait.

CE QUE CETTE PORTE FAIT — ET NE FAIT PAS
-----------------------------------------
* elle ANALYSE le fichier déposé (en mémoire) et rend les calques
  disponibles ; le calque choisi rend le CONTOUR et ses cotes hors-tout ;
* elle n'ÉCRIT RIEN : aucun ``roof_layout``, aucun document, aucun statut.
  Le contour revient au client, qui décide — l'enregistrement reste le geste
  existant (``POST layout/``, CAL18), déclenché par l'utilisateur.
* **le fichier n'est pas conservé** : choisir un calque redépose le même
  fichier. Un fichier gardé côté serveur serait un stockage de plus, avec sa
  durée de vie et sa purge, pour un besoin d'un seul aller-retour.
* **aucune échelle n'est devinée.** L'unité rendue est celle que le fichier
  DÉCLARE (``$INSUNITS``) ou ``'inconnu'`` ; ``echelle`` vaut toujours
  ``null``, et c'est la calibration de l'atelier (deux points, une distance
  réelle saisie) qui la donne. Une conversion supposée produirait un plan
  faux qui a l'air juste.
* **aucun booléen n'est lu du corps.** En ``multipart/form-data`` tout arrive
  en TEXTE : une case décochée envoyée « false » est une chaîne non vide,
  donc VRAIE pour un ``BooleanField``. Cette porte n'ayant rien à basculer
  (elle n'écrit jamais), ``enregistre`` est une constante du SERVEUR.

La société est forcée par le serveur : ``self.get_object()`` passe par le
``get_queryset`` du viewset pivot (``CompanyScopedModelViewSet``), donc un
calepinage d'une autre société est INTROUVABLE (404), jamais « interdit ».
L'objet est résolu AVANT toute validation du fichier : répondre « fichier
manquant » sur un objet qui n'existe pas pour cet appelant serait un oracle
d'existence par la bande.

Même forme que ``views/equipements.py`` / ``views/reglementaire.py`` : le code
vit dans son propre fichier et l'action est RATTACHÉE au ``CalepinageViewSet``
par affectation d'attribut de classe, depuis l'import unique de
``views/rattachements.py`` exécuté AVANT ``router.register``.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from ..analyse_plan import TAILLE_MAX_OCTETS
from ..permissions import PeutGererCalepinage
from ..services.import_plan import (
    PlanIllisible,
    analyser_plan,
    contour_du_calque,
    cotes_hors_tout,
)
from .calepinages import CalepinageViewSet

__all__ = ['importer_plan', 'SANS_FICHIER', 'TROP_LOURD', 'FORMATS_REFUSES']

#: Le champ du formulaire qui porte le plan — nommé dans CHAQUE refus.
CHAMP_FICHIER = 'fichier'

#: Le champ qui porte le calque choisi.
CHAMP_CALQUE = 'calque'

SANS_FICHIER = ("Aucun plan déposé : ajoutez un fichier DXF ou PDF vectoriel "
                "dans le champ « fichier ».")
TROP_LOURD = ("Ce fichier dépasse 5 Mo : simplifiez-le (purge des calques "
              "inutiles) puis réessayez.")

#: Signatures de fichiers qu'aucun analyseur de ce module ne peut lire comme
#: un plan VECTORIEL. On regarde le CONTENU, jamais l'extension (un « .dxf »
#: renommé depuis un PNG est un cas réel d'atelier), et on refuse en disant
#: la voie honnête plutôt qu'en devinant un contour depuis des pixels.
FORMATS_REFUSES = (
    (b'\x89PNG\r\n\x1a\n', 'image PNG'),
    (b'\xff\xd8\xff', 'image JPEG'),
    (b'GIF8', 'image GIF'),
    (b'RIFF', 'image WEBP'),
    (b'BM', 'image BMP'),
    (b'AC10', 'dessin DWG'),
)

REFUS_IMAGE = ("Ce fichier est une {quoi} : il ne porte aucun tracé "
               "vectoriel, donc aucun contour ne peut en être tiré sans "
               "l'inventer. Exportez le plan en DXF (ou en PDF vectoriel "
               "depuis le logiciel de dessin), ou calez la photo à la main "
               "depuis l'onglet « Plan importé ».")

MESSAGE_SANS_CALQUE = ("Plan analysé : rien n'a été enregistré. Choisissez le "
                       "calque qui porte l'enveloppe pour en tirer le "
                       "contour.")
MESSAGE_AVEC_CALQUE = ("Contour proposé depuis le calque choisi : rien n'a "
                       "été enregistré. Calez-le (deux points et leur "
                       "distance réelle) avant de l'appliquer au toit.")

MOTIF_ECHELLE_INCONNUE = ("Ce fichier ne déclare aucune unité : l'échelle "
                          "vient de la calibration (deux points du plan et "
                          "la distance réelle entre eux), jamais d'une "
                          "estimation.")
MOTIF_ECHELLE_DECLAREE = ("Le fichier déclare son unité, pas son échelle "
                          "d'impression : la calibration reste le seul "
                          "chemin qui pose l'échelle du plan.")


def _forme():
    """YAPIC6/PACT7 — la forme DÉCLARÉE, tirée du contrat CALX39."""
    return inline_serializer('CalepinageImportPlan', {
        'calepinage': serializers.IntegerField(),
        'fichier': serializers.CharField(),
        'format': serializers.CharField(),
        'unite': serializers.CharField(),
        'echelle': serializers.FloatField(allow_null=True),
        'motif_echelle': serializers.CharField(),
        'calques': serializers.ListField(child=serializers.DictField()),
        'calque': serializers.CharField(allow_null=True),
        'contour': serializers.ListField(child=serializers.ListField(),
                                         allow_null=True),
        'cotes_hors_tout': serializers.DictField(allow_null=True),
        'enregistre': serializers.BooleanField(),
        'message': serializers.CharField(),
    })


def _refus(champ, message):
    return Response({champ: message}, status=status.HTTP_400_BAD_REQUEST)


def _format_refuse(contenu):
    """Le libellé du format non vectoriel reconnu, ou ``None``."""
    for signature, quoi in FORMATS_REFUSES:
        if contenu[:len(signature)] == signature:
            return quoi
    return None


@extend_schema(responses={200: _forme()})
@action(detail=True, methods=['post'], url_path='importer-plan',
        url_name='importer-plan',
        permission_classes=[PeutGererCalepinage],
        parser_classes=[MultiPartParser, FormParser])
def importer_plan(self, request, pk=None):
    """CALX39 — analyse un plan déposé et rend ses calques (et un contour).

    Corps ``multipart/form-data`` : ``fichier`` (obligatoire) et ``calque``
    (facultatif). Sans ``calque``, la réponse liste ce que le plan contient ;
    avec, elle ajoute le contour de ce calque et ses cotes hors-tout.

    Refus (400) en NOMMANT le champ fautif : ``fichier`` (absent, vide, trop
    lourd, non vectoriel, illisible — motif français de ``PlanIllisible``) ou
    ``calque`` (inexistant : le message liste les calques disponibles).
    """
    # L'OBJET D'ABORD : un calepinage d'une autre société rend 404 quel que
    # soit le corps envoyé.
    calepinage = self.get_object()  # borné société par get_queryset

    fichier = request.FILES.get(CHAMP_FICHIER)
    if fichier is None:
        return _refus(CHAMP_FICHIER, SANS_FICHIER)
    taille = getattr(fichier, 'size', None)
    if isinstance(taille, int) and taille > TAILLE_MAX_OCTETS:
        return _refus(CHAMP_FICHIER, TROP_LOURD)

    contenu = fichier.read()
    if not contenu:
        return _refus(CHAMP_FICHIER, SANS_FICHIER)
    if len(contenu) > TAILLE_MAX_OCTETS:
        return _refus(CHAMP_FICHIER, TROP_LOURD)
    quoi = _format_refuse(contenu)
    if quoi is not None:
        return _refus(CHAMP_FICHIER, REFUS_IMAGE.format(quoi=quoi))

    nom_fichier = str(getattr(fichier, 'name', '') or '')
    try:
        analyse = analyser_plan(contenu, nom_fichier=nom_fichier)
    except PlanIllisible as refus:
        return _refus(getattr(refus, 'champ', '') or CHAMP_FICHIER,
                      str(refus))

    calque_demande = str(request.data.get(CHAMP_CALQUE) or '').strip()
    contour, cotes = None, None
    if calque_demande:
        try:
            contour = contour_du_calque(analyse, calque_demande)
        except PlanIllisible as refus:
            return _refus(getattr(refus, 'champ', '') or CHAMP_CALQUE,
                          str(refus))
        cotes = cotes_hors_tout(contour)

    unite = analyse.get('unite') or 'inconnu'
    return Response({
        'calepinage': calepinage.pk,
        'fichier': nom_fichier,
        'format': analyse.get('format') or '',
        'unite': unite,
        # JAMAIS devinée — voir la docstring du module.
        'echelle': None,
        'motif_echelle': (MOTIF_ECHELLE_INCONNUE if unite == 'inconnu'
                          else MOTIF_ECHELLE_DECLAREE),
        'calques': [{'nom': calque.get('nom') or '',
                     'entites': calque.get('entites') or 0,
                     'sommets': len(calque.get('sommets') or [])}
                    for calque in (analyse.get('calques') or [])],
        'calque': calque_demande or None,
        'contour': contour,
        'cotes_hors_tout': cotes,
        # Constante du SERVEUR : cette porte n'écrit jamais.
        'enregistre': False,
        'message': MESSAGE_AVEC_CALQUE if contour else MESSAGE_SANS_CALQUE,
    })


# Rattachement au viewset PIVOT — voir la docstring du module.
CalepinageViewSet.importer_plan = importer_plan
