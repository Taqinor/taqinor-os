"""NTEXT29 — éditeur no-code de conditions (arbre ET/OU/NON) réutilisable.

Socle SERVEUR du builder de conditions partagé par plusieurs points
d'extension (XPLT15 — conditions de champ personnalisé, NTEXT5 — branches
d'automatisation, NTEXT21 — condition d'onglet custom) : au lieu que chaque
écran connaisse le format ``core.rules`` en dur, il interroge ces deux
endpoints pour découvrir les opérateurs disponibles ET valider un arbre
avant de le sauver — un seul évaluateur, jamais dupliqué.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAnyRole

__all__ = ['RegleOperateursView', 'RegleValiderView']


class RegleOperateursView(APIView):
    """NTEXT29 — catalogue documenté des opérateurs de feuille sûrs
    (``core.rules.LEAF_OPERATORS``), avec libellé FR + exemple."""

    permission_classes = [IsAnyRole]

    @extend_schema(responses=inline_serializer('RegleOperateursReponse', {
        'operateurs': drf_serializers.JSONField(),
    }))
    def get(self, request):
        from core.rules import catalogue_operateurs
        return Response({'operateurs': catalogue_operateurs()})


class RegleValiderView(APIView):
    """NTEXT29 — dry-run de validation d'un arbre de conditions.

    ``POST core/regles/valider/`` — corps ``{"conditions": {...}}`` (arbre
    ``core.rules`` : groupe ``{op, conditions}`` ou feuille directe
    ``{field, operator, value}``). Délègue ENTIÈREMENT à
    ``core.rules.validate_condition_group`` : AUCUN effet de bord, rien
    n'est évalué ni enregistré — seule la STRUCTURE est vérifiée."""

    permission_classes = [IsAnyRole]

    @extend_schema(
        request=inline_serializer('RegleValiderRequete', {
            'conditions': drf_serializers.JSONField(),
        }),
        responses=inline_serializer('RegleValiderReponse', {
            'ok': drf_serializers.BooleanField(),
            'erreurs': drf_serializers.JSONField(),
        }))
    def post(self, request):
        from core.rules import validate_condition_group

        donnees = request.data if isinstance(request.data, dict) else {}
        conditions = donnees.get('conditions')
        if conditions is None:
            return Response(
                {'ok': False, 'erreurs': ["L'arbre « conditions » est requis."]})
        erreurs = validate_condition_group(conditions)
        return Response({'ok': not erreurs, 'erreurs': erreurs})
