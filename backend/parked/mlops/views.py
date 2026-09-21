"""Vues de lecture du module « mlops » — backtests (NTAI28).

Réservé Responsable/Admin (lecture d'un diagnostic technique des scorers).
"""
from datetime import date

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin

from .backtest import SCORERS_SUPPORTES, SEUIL_DEFAUT, backtester


def _parse_date(valeur):
    if not valeur:
        return None
    try:
        return date.fromisoformat(valeur)
    except ValueError:
        return None


# NTAI28 — forme réelle de ``backtester()`` (apps/mlops/backtest.py) : deux
# branches ``disponible`` (True/False) qui ne portent pas les mêmes clés — les
# champs propres à la branche « disponible=True » (métriques de confusion +
# AUC) sont donc tous ``required=False``/``allow_null=True``, jamais un objet
# vide qui ne dirait rien de la forme réellement renvoyée.
BACKTESTS_RESPONSE = inline_serializer('MlopsBacktestResultat', {
    'nom': serializers.CharField(),
    'disponible': serializers.BooleanField(),
    'motif': serializers.CharField(required=False, allow_null=True),
    'taille_echantillon': serializers.IntegerField(
        required=False, allow_null=True),
    'seuil': serializers.FloatField(required=False, allow_null=True),
    'auc': serializers.FloatField(required=False, allow_null=True),
    'precision': serializers.FloatField(required=False, allow_null=True),
    'rappel': serializers.FloatField(required=False, allow_null=True),
    'exactitude': serializers.FloatField(required=False, allow_null=True),
    'vrais_positifs': serializers.IntegerField(
        required=False, allow_null=True),
    'faux_positifs': serializers.IntegerField(
        required=False, allow_null=True),
    'vrais_negatifs': serializers.IntegerField(
        required=False, allow_null=True),
    'faux_negatifs': serializers.IntegerField(
        required=False, allow_null=True),
})


@extend_schema(responses=BACKTESTS_RESPONSE)
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def backtests(request):
    """NTAI28 — ``GET mlops/backtests/?nom=&debut=&fin=&seuil=``.

    ``nom`` (obligatoire) — un scorer de :data:`SCORERS_SUPPORTES`.
    ``debut``/``fin`` (``AAAA-MM-JJ``, optionnels, ignorés si invalides)
    bornent la période sur le mois de création du lead. ``seuil`` (``0..1``,
    défaut 0.5) — seuil de classification.
    """
    nom = request.query_params.get('nom')
    if nom not in SCORERS_SUPPORTES:
        return Response(
            {'detail': 'Scorer invalide (valeurs possibles : %s).'
                       % ', '.join(SCORERS_SUPPORTES)},
            status=400)
    seuil_raw = request.query_params.get('seuil')
    try:
        seuil = float(seuil_raw) if seuil_raw is not None else SEUIL_DEFAUT
    except (TypeError, ValueError):
        return Response({'detail': 'Seuil invalide (nombre attendu).'},
                        status=400)
    periode = (
        _parse_date(request.query_params.get('debut')),
        _parse_date(request.query_params.get('fin')),
    )
    resultat = backtester(
        request.user.company, nom, periode=periode, seuil=seuil,
        user=request.user)
    return Response(resultat)
