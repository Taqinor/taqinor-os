"""Vues de lecture du module « mlops » — backtests (NTAI28).

Réservé Responsable/Admin (lecture d'un diagnostic technique des scorers).
"""
from datetime import date

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
