"""T12 — endpoint export comptable (journal des ventes + résumé TVA)."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from .exports import export_journal_ventes, period_bounds


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
