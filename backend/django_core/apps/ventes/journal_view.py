"""T12 — endpoint export comptable (journal des ventes + résumé TVA)."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from .exports import (
    export_journal_ventes, period_bounds,
    export_comptable_xlsx, export_comptable_csv,
    export_grand_livre_xlsx, export_grand_livre_csv,
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
    """GET ?start=&end= (ou ?month=/?quarter=) &fmt=xlsx|csv &layout=… → export
    comptable des factures VALIDÉES de la plage. Groundwork DGI — lecture seule,
    borné société, aucune transmission.

    `layout` (FG49) :
      • ``ligne`` (défaut) — une ligne par ligne de facture, ventilation TVA par
        ligne + ICE client + totaux ;
      • ``grand-livre`` — grand-livre codé par compte CGNC (3421 clients / 7111
        ventes / 4455 TVA collectée), écritures débit/crédit équilibrées prêtes
        pour import direct chez le fiduciaire (mise en page type PCG/Sage).

    `fmt` par défaut = xlsx (sinon csv). (NB : on n'utilise pas ``format``,
    réservé par DRF pour la négociation de contenu.)"""
    user = request.user
    if not user.company_id and not user.is_superuser:
        return Response({'detail': 'Accès refusé.'}, status=403)
    try:
        debut, fin = period_bounds(request.query_params)
    except (ValueError, TypeError):
        return Response({'detail': 'Période invalide.'}, status=400)
    fmt = (request.query_params.get('fmt') or 'xlsx').lower()
    layout = (request.query_params.get('layout') or 'ligne').lower()
    if layout in ('grand-livre', 'grand_livre', 'gl', 'compte'):
        if fmt == 'csv':
            return export_grand_livre_csv(user.company, debut, fin)
        return export_grand_livre_xlsx(user.company, debut, fin)
    if fmt == 'csv':
        return export_comptable_csv(user.company, debut, fin)
    return export_comptable_xlsx(user.company, debut, fin)
