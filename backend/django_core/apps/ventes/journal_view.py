"""T12 — endpoint export comptable (journal des ventes + résumé TVA)."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from .exports import (
    export_journal_ventes, period_bounds,
    export_comptable_xlsx, export_comptable_csv,
)


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def journal_ventes(request):
    """GET ?month=YYYY-MM | ?quarter=YYYY-Q | ?start=&end= → .xlsx
    (journal des ventes + résumé TVA), borné à la société."""
    user = request.user
    if not user.company_id and not user.is_superuser:
        return Response({'detail': 'Accès refusé.'}, status=403)
    try:
        debut, fin = period_bounds(request.query_params)
    except (ValueError, TypeError):
        return Response({'detail': 'Période invalide.'}, status=400)
    return export_journal_ventes(user.company, debut, fin)


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def export_comptable(request):
    """GET ?start=&end= (ou ?month=/?quarter=) &format=xlsx|csv → export
    comptable des factures VALIDÉES de la plage (ventilation TVA par ligne,
    ICE client, totaux). Groundwork DGI — lecture seule, borné société,
    aucune transmission. `format` par défaut = xlsx."""
    user = request.user
    if not user.company_id and not user.is_superuser:
        return Response({'detail': 'Accès refusé.'}, status=403)
    try:
        debut, fin = period_bounds(request.query_params)
    except (ValueError, TypeError):
        return Response({'detail': 'Période invalide.'}, status=400)
    fmt = (request.query_params.get('format') or 'xlsx').lower()
    if fmt == 'csv':
        return export_comptable_csv(user.company, debut, fin)
    return export_comptable_xlsx(user.company, debut, fin)
