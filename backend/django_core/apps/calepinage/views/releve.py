"""CAL64 — la sous-ressource « relevé terrain » du pivot.

UNE SEULE FORME D'URL (CAL233) : le relevé est une SOUS-RESSOURCE du
calepinage, donc une ``@action`` du viewset pivot
(``/api/django/calepinage/calepinages/<pk>/releve/``). Le mixin vit dans SON
fichier pour garder les lanes file-disjointes.

CE QUE L'ACTION GARANTIT
------------------------
* **L'OBJET D'ABORD (CAL29)** — ``get_object()`` précède la lecture du corps :
  un calepinage d'une autre société rend 404 quelle que soit la saisie ;
* **la société et l'auteur viennent du SERVEUR**, jamais du corps ;
* **le refus NOMME le champ** (``releve_le``, ``chaines[i]``,
  ``precision_azimut_deg``…), en français ;
* une cote DÉDUITE remonte marquée « à confirmer » — jamais une cote inventée
  en silence ;
* aucun statut ne bouge (règle #4), et le relevé n'écrit PAS le
  ``roof_layout`` : il propose une géométrie, c'est le dessinateur qui décide.
"""
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.champs_stricts import ChaineStricte, DateStricte
from core.conflit_etat import ConflitEtat
from core.parseurs import ListeJSON

from ..permissions import PeutGererCalepinage, PeutLireOuEcrireCalepinage
from ..serializers import forme_reponse

__all__ = ['ReleveTerrainMixin']


_FORME_RELEVE = forme_reponse('CalepinageReleveTerrain', 'releve', 'releves',
                              'releve_courant_id')


def _statut_refus_releve(refus):
    """ENF11 — le CONTENU d'une chaîne de cotes (deux cotes manquantes, valeur
    illisible) est un document libre que le schéma ne décrit pas : 409, même
    doctrine que les réglages. La forme du corps reste un 400."""
    if refus.document_libre or (refus.champ or '').startswith('chaines['):
        return status.HTTP_409_CONFLICT
    return status.HTTP_400_BAD_REQUEST


class ReleveTerrainMixin:
    """``GET``/``POST`` ``calepinages/<pk>/releve/`` — les relevés terrain."""

    @extend_schema(methods=['GET'], responses=_FORME_RELEVE)
    @extend_schema(
        methods=['POST'],
        request=inline_serializer('CalepinageReleveCorps', {
            # ENF11 — la date est OBLIGATOIRE et s'écrit AAAA-MM-JJ (publié).
            'releve_le': DateStricte(),
            'notes': ChaineStricte(required=False, allow_blank=True),
            'chaines': ListeJSON(element=dict, required=False)}),
        responses={201: _FORME_RELEVE})
    @action(detail=True, methods=['get', 'post'], url_path='releve',
            permission_classes=[PeutLireOuEcrireCalepinage])
    def releve(self, request, pk=None):
        from ..selectors import releves_terrain
        from ..services.releve import (
            ReleveRefuse, enregistrer_releve, releve_courant_id,
        )

        # L'OBJET D'ABORD (CAL29) : borné société par ``get_queryset``.
        calepinage = self.get_object()

        if request.method.lower() == 'get':
            return Response({
                'releves': releves_terrain(calepinage),
                'releve_courant_id': releve_courant_id(calepinage)})

        try:
            releve = enregistrer_releve(
                calepinage,
                request.data if isinstance(request.data, dict) else None,
                user=request.user)
        except ReleveRefuse as refus:
            if refus.champ == 'releve_le' and 'futur' in str(refus):
                # ENF11 — règle d'HORLOGE, que le schéma ne peut pas dire.
                raise ConflitEtat(str(refus))
            return Response({refus.champ or 'detail': str(refus)},
                            status=_statut_refus_releve(refus))

        from ..services.releve import releve_en_ligne

        return Response({'releve': releve_en_ligne(releve),
                         'releves': releves_terrain(calepinage),
                         'releve_courant_id': releve_courant_id(calepinage)},
                        status=status.HTTP_201_CREATED)

    @extend_schema(
        parameters=[OpenApiParameter(
            name='releve_id', type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="Identifiant du relevé terrain (sous-ressource).")],
        request=inline_serializer('CalepinageReleveModifCorps', {
            'notes': ChaineStricte(required=False, allow_blank=True),
            'chaines': ListeJSON(element=dict, required=False)}),
        responses={200: _FORME_RELEVE, 204: None})
    @action(detail=True, methods=['patch', 'delete'],
            url_path=r'releve/(?P<releve_id>[^/.]+)',
            permission_classes=[PeutLireOuEcrireCalepinage])
    def releve_detail(self, request, pk=None, releve_id=None):
        """ACAL204 — corrige (PATCH) ou retire (DELETE) UN relevé de saisie.

        L'OBJET D'ABORD : le calepinage est résolu par ``get_object()``
        (société), PUIS le relevé est cherché DANS ses relevés — un relevé
        d'un autre calepinage ou d'une autre société rend la même 404 qu'un
        relevé absent. PATCH met à jour LE MÊME relevé (jamais une nouvelle
        ligne) ; un relevé repris d'une visite n'est ni modifiable ni
        supprimable (400 nommé) ; le verrou du devis envoyé rend 409.
        """
        from ..services.releve import (
            ReleveRefuse, modifier_releve, releve_courant_id,
            releve_en_ligne, supprimer_releve,
        )

        calepinage = self.get_object()  # borné société par get_queryset
        releve = None
        if str(releve_id).isdigit():
            releve = (calepinage.releves_terrain
                      .select_related('releve_par')
                      .filter(pk=int(releve_id)).first())
        if releve is None:
            return Response({'detail': 'Relevé introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            if request.method.lower() == 'delete':
                supprimer_releve(releve)
                return Response(status=status.HTTP_204_NO_CONTENT)
            releve = modifier_releve(
                releve,
                request.data if isinstance(request.data, dict) else None,
                user=request.user)
        except ReleveRefuse as refus:
            return Response({refus.champ or 'detail': str(refus)},
                            status=_statut_refus_releve(refus))
        return Response({'releve': releve_en_ligne(releve),
                         'releve_courant_id': releve_courant_id(calepinage)})

    @extend_schema(
        parameters=[OpenApiParameter(
            name='releve_id', type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="Identifiant du relevé terrain (sous-ressource).")],
        request=inline_serializer('CalepinageAppliquerCoteCorps', {
            'zone_id': serializers.CharField(),
            'cote_index': serializers.IntegerField(),
            'longueur_m': serializers.FloatField(),
            'base_empreinte': serializers.CharField(allow_blank=True)}),
        responses={200: forme_reponse('CalepinageAppliquerCote',
                                      'roof_layout', 'version',
                                      'empreinte_document')})
    @action(detail=True, methods=['post'],
            url_path=r'releve/(?P<releve_id>[^/.]+)/appliquer-cote',
            permission_classes=[PeutGererCalepinage])
    def releve_appliquer_cote(self, request, pk=None, releve_id=None):
        """ACAL207 (D-ACAL-28) — « Appliquer la cote au pan ».

        Corps ``{zone_id, cote_index, longueur_m}`` (contrat
        ``calepinage_releve.json`` › ``appliquer_cote``) → ``{roof_layout,
        version}``. Le côté ``cote_index`` du pan est recalé par homothétie le
        long de sa direction (``services.releve.appliquer_cote_au_pan``) et
        une version est déposée. 400 nommé : cote A_CONFIRMER, pan croisé,
        longueur absente du relevé ; 409 : calepinage verrouillé ; 404 : relevé
        ou calepinage d'ailleurs. Jamais d'application automatique.
        """
        from ..services.layout import DocumentModifie
        from ..services.releve import ReleveRefuse, appliquer_cote_au_pan

        calepinage = self.get_object()  # borné société par get_queryset
        corps = request.data if isinstance(request.data, dict) else {}
        if not (str(releve_id).isdigit() and calepinage.releves_terrain
                .filter(pk=int(releve_id)).exists()):
            return Response({'detail': 'Relevé introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            resultat = appliquer_cote_au_pan(
                calepinage, zone_id=corps.get('zone_id'),
                cote_index=corps.get('cote_index'),
                longueur_m=corps.get('longueur_m'),
                releve_id=releve_id, user=request.user,
                base_empreinte=corps.get('base_empreinte'))
        except DocumentModifie as conflit:  # ACON2 — jeton périmé, rien écrit
            return Response(conflit.corps(), status=status.HTTP_409_CONFLICT)
        except ReleveRefuse as refus:
            return Response({refus.champ or 'detail': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        version = resultat['version']
        return Response({
            'roof_layout': calepinage.roof_layout,
            'version': version.pk if version is not None else None,
            'empreinte_document': resultat.get('empreinte_document') or '',
        })
