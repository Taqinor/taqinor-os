"""ACAL72 — téléverser une image de plan (PNG/JPEG) comme FOND du document.

``POST calepinages/<pk>/fond-plan/`` ÉCRIT : une ``records.Attachment`` est
rattachée au calepinage et ``underlay = {kind:'plan', ...}`` est posé par la
primitive de section (verrou de ligne + jeton ``base_empreinte``). C'est
pourquoi ce geste vit dans SON fichier et non dans ``views/import_plan.py`` :
la porte ``importer-plan/`` (CALX39) est une LECTURE et sa source ne doit
contenir aucune écriture (``test_calx39_import_plan.AucuneEcritureTest``) ;
``plan-importe/`` (CALX107) reste lui aussi une lecture pure — il SERT le
fond produit ici.

La société est forcée par le serveur : ``self.get_object()`` passe par le
``get_queryset`` du viewset pivot, donc un calepinage d'une autre société est
INTROUVABLE (404). Rattachée au ``CalepinageViewSet`` par affectation
d'attribut depuis ``views/rattachements.py`` (même patron que les autres).
"""
from __future__ import annotations

from uuid import uuid4

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage
from .calepinages import CalepinageViewSet
from .import_plan import CHAMP_FICHIER, SANS_FICHIER, _refus

__all__ = ['fond_plan', 'OPACITE_FOND_PLAN', 'REFUS_FOND_PLAN']

#: ACAL72 — opacité de départ d'un fond de plan posé par le téléversement.
OPACITE_FOND_PLAN = 0.6

REFUS_FOND_PLAN = ("Seuls les plans PNG et JPEG se posent en fond : un DXF ou "
                   "un PDF passe par l'import de plan.")


@extend_schema(responses={200: inline_serializer('CalepinageFondPlan', {
    'roof_layout': serializers.DictField(),
    'underlay': serializers.DictField(),
    'empreinte_document': serializers.CharField(allow_null=True),
    'layout_hash': serializers.CharField(allow_null=True),
    'inchange': serializers.BooleanField(),
    'version': serializers.IntegerField(allow_null=True),
})})
@action(detail=True, methods=['post'], url_path='fond-plan',
        url_name='fond-plan', permission_classes=[PeutGererCalepinage],
        parser_classes=[MultiPartParser, FormParser])
def fond_plan(self, request, pk=None):
    """ACAL72 — téléverse une image de plan (PNG/JPEG) comme fond du document.

    Corps ``multipart/form-data`` : ``fichier`` + ``base_empreinte`` (le jeton
    d'écriture, D-ACAL-4). Une ``records.Attachment`` est rattachée au
    calepinage et ``underlay = {kind:'plan', attachmentId, opacite:0.6,
    calage:null}`` est écrit par la primitive de section (verrou de ligne et
    base respectés) : ``GET plan-importe/`` sert alors enfin un fond.

    Refus (400, champ nommé) : ``fichier`` (absent, vide, trop lourd, ni PNG
    ni JPEG) ou ``base_empreinte`` ; 409 ``document_modifie`` sur jeton
    périmé ; 404 pour un calepinage d'une autre société (``get_queryset``).
    """
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction

    from apps.records.models import Attachment
    from apps.ventes import services as ventes_services

    from ..services.layout import (
        DocumentModifie, LayoutRefuse, empreinte_document,
        enregistrer_section,
    )
    from ..services.photos import MAX_OCTETS
    from .calepinages import _reponse_ecriture

    calepinage = self.get_object()  # L'OBJET D'ABORD (borné société)

    base = str(request.data.get('base_empreinte') or '').strip()
    if not base:
        return _refus('base_empreinte',
                      "Jeton manquant : envoyez base_empreinte, l'empreinte "
                      "du document ouvert.")
    fichier = request.FILES.get(CHAMP_FICHIER)
    if fichier is None:
        return _refus(CHAMP_FICHIER, SANS_FICHIER)
    donnees = fichier.read()
    if not donnees:
        return _refus(CHAMP_FICHIER, SANS_FICHIER)
    if len(donnees) > MAX_OCTETS:
        return _refus(CHAMP_FICHIER,
                      "Image trop volumineuse : "
                      f"{MAX_OCTETS // (1024 * 1024)} Mo au maximum.")
    extension, mime = ventes_services.type_image_toiture(donnees)
    if extension is None:
        return _refus(CHAMP_FICHIER, REFUS_FOND_PLAN)

    # Jeton déjà périmé : refus AVANT de téléverser (aucun objet orphelin).
    courante = empreinte_document(calepinage.roof_layout)
    if base != courante:
        return Response(DocumentModifie(courante).corps(),
                        status=status.HTTP_409_CONFLICT)

    cle = (f'roofs/{calepinage.company_id or 0}/'
           f'calepinage-{calepinage.pk}-plan-{uuid4().hex}.{extension}')
    ventes_services.stocker_image_toiture(donnees, cle, content_type=mime)
    utilisateur = request.user if getattr(request.user, 'pk', None) else None
    try:
        with transaction.atomic():
            piece = Attachment.objects.create(
                company=calepinage.company,
                content_type=ContentType.objects.get_for_model(
                    type(calepinage)),
                object_id=calepinage.pk,
                file_key=cle,
                filename=(getattr(fichier, 'name', '')
                          or f'plan.{extension}')[:255],
                size=len(donnees),
                mime=mime or '',
                uploaded_by=utilisateur,
            )
            fond = {'kind': 'plan', 'attachmentId': piece.pk,
                    'opacite': OPACITE_FOND_PLAN, 'calage': None}
            resultat = enregistrer_section(
                calepinage, 'underlay', fond, base_empreinte=base,
                user=request.user)
    except DocumentModifie as conflit:
        return Response(conflit.corps(), status=status.HTTP_409_CONFLICT)
    except LayoutRefuse as refus:
        return _refus(refus.champ or 'roof_layout', str(refus))
    reponse = _reponse_ecriture(calepinage, resultat)
    reponse['underlay'] = fond
    return Response(reponse)


# Rattachement au viewset PIVOT — voir la docstring du module.
CalepinageViewSet.fond_plan = fond_plan
