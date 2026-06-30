"""Vue PUBLIQUE du portail d'avancement client (PROJ37).

Endpoint non authentifié, accédé par un jeton (``PortailProjetToken``) :
expose UNIQUEMENT l'avancement non financier d'un projet (phases, jalons,
avancement global). AUCUN coût, budget, marge, P&L ni ``facturation_pct`` ne
traverse cette frontière — voir ``selectors.portail_avancement_client``.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import selectors
from .models import PortailProjetToken


@api_view(['GET'])
@permission_classes([AllowAny])
def portail_avancement(request, token):
    """Avancement client d'un projet par JETON public (PROJ37) — sans coûts.

    Le jeton doit exister ET être ``actif`` (sinon 404 — on ne distingue pas un
    jeton inconnu d'un jeton révoqué, pour ne rien divulguer). La société est
    portée par le jeton (jamais lue d'un paramètre). Lecture seule, données
    strictement non financières.
    """
    token_obj = PortailProjetToken.objects.filter(
        token=token, actif=True).select_related('projet').first()
    if token_obj is None:
        return Response({'detail': 'Lien invalide ou expiré.'}, status=404)
    return Response(
        selectors.portail_avancement_client(token_obj.projet))
