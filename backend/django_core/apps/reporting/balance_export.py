"""Export Excel (.xlsx) de la balance âgée — créances par tranche d'âge.

Miroir de l'export journal des ventes (apps.ventes) côté reporting : une ligne
par client avec ses encours bucketés 0–30 / 31–60 / 61–90 / 90+ jours + total.
Lecture seule, borné à la société (multi-tenant). `openpyxl` (pré-approuvé) est
importé À LA DEMANDE via le helper partagé `crm.exports.build_xlsx_response`.

Aucun prix d'achat ni marge n'est exposé : seuls les montants dus visibles.
"""
from decimal import Decimal

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin


def _s2(x):
    """Decimal → flottant au centime (valeur numérique de la cellule)."""
    return float(Decimal(x).quantize(Decimal('0.01')))


BALANCE_AGEE_HEADERS = [
    'Client', '0–30 j', '31–60 j', '61–90 j', '90+ j', 'Total dû',
]


def balance_agee_rows(user):
    """Lignes de la balance âgée (une par client), bornées à la société.

    Réutilise la même source/bucketing que l'endpoint JSON
    `/ventes/balance-agee/` (apps.ventes.recouvrement._facture_due_rows)
    pour rester cohérent au centime.
    """
    from apps.ventes.recouvrement import _facture_due_rows

    by_client = {}
    for f in _facture_due_rows(user):
        cid = f.client_id
        entry = by_client.setdefault(cid, {
            'client_nom': f"{f.client.nom} {f.client.prenom or ''}".strip(),
            'b0_30': Decimal('0'), 'b31_60': Decimal('0'),
            'b61_90': Decimal('0'), 'b90_plus': Decimal('0'),
            'total': Decimal('0'),
        })
        jr = f.jours_retard
        due = f.montant_du
        if jr <= 30:
            entry['b0_30'] += due
        elif jr <= 60:
            entry['b31_60'] += due
        elif jr <= 90:
            entry['b61_90'] += due
        else:
            entry['b90_plus'] += due
        entry['total'] += due

    ordered = sorted(
        by_client.values(), key=lambda e: e['total'], reverse=True)
    rows = [[
        e['client_nom'],
        _s2(e['b0_30']), _s2(e['b31_60']),
        _s2(e['b61_90']), _s2(e['b90_plus']), _s2(e['total']),
    ] for e in ordered]
    # Pied de page : totaux par tranche (réconciliation comptable).
    if rows:
        rows.append([
            'Total',
            sum(r[1] for r in rows), sum(r[2] for r in rows),
            sum(r[3] for r in rows), sum(r[4] for r in rows),
            sum(r[5] for r in rows),
        ])
    return rows


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def balance_agee_export(request):
    """GET → .xlsx de la balance âgée (créances par client + tranches d'âge),
    borné à la société de l'utilisateur connecté."""
    from apps.crm.exports import build_xlsx_response

    user = request.user
    if not user.company_id and not user.is_superuser:
        return Response({'detail': 'Accès refusé.'}, status=403)
    rows = balance_agee_rows(user)
    return build_xlsx_response(
        'balance-agee.xlsx', BALANCE_AGEE_HEADERS, rows,
        sheet_title='Balance âgée',
    )
