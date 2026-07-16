"""ZSAV7 — pivot/graphique tickets SAV (technicien×statut…) via le dataset BI
`sav_tickets` déclaré côté `apps.sav.bi_datasets`, lu par le noyau
(`core.data_explorer`/`core.pivot`) — jamais d'import de `apps.sav.models`
depuis `reporting` (frontière cross-app, contrat import-linter).

Le coût interne (`Ticket.cout`) est MASQUÉ sans la permission
`prix_achat_voir` (`request.user.can_view_buy_prices`) — jamais exposé côté
JSON ni export xlsx sans elle."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin


def _co(user):
    if user.company_id:
        return user.company
    return None


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def sav_tickets_pivot(request):
    """ZSAV7 — ``GET reporting/insights/sav-tickets-pivot/``.

    ``?rows=technicien_responsable__username&columns=statut`` (défaut :
    lignes=technicien, colonnes=statut, mesure=nombre). ``?export=xlsx``
    renvoie un tableau plat (une ligne par groupe rows×columns)."""
    from core import data_explorer
    from core.pivot import PivotSpec, build_pivot

    company = _co(request.user)
    if company is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    rows_field = request.query_params.get(
        'rows', 'technicien_responsable__username')
    columns_field = request.query_params.get('columns', 'statut')

    try:
        records = data_explorer.run_query(
            'sav_tickets', company, request.user, {
                'select': [rows_field, columns_field, 'id'],
            })
    except data_explorer.DatasetInconnu as exc:
        return Response({'detail': str(exc)}, status=404)
    except data_explorer.ChampNonAutorise as exc:
        return Response({'detail': str(exc)}, status=400)

    spec = PivotSpec(rows=[rows_field], columns=[columns_field], agg='count')
    pivot = build_pivot(records, spec)

    if request.query_params.get('export') == 'xlsx':
        from apps.crm.exports import build_xlsx_response
        headers = ([rows_field]
                   + [','.join(ck) for ck in pivot['col_keys']] + ['Total'])
        rows_out = []
        for rk in pivot['row_keys']:
            key = ','.join(rk)
            row_out = [key]
            for ck in pivot['col_keys']:
                ck_key = ','.join(ck)
                row_out.append(pivot['cells'].get(key, {}).get(ck_key, 0))
            row_out.append(pivot['row_totals'].get(key, 0))
            rows_out.append(row_out)
        return build_xlsx_response(
            'pivot-tickets-sav.xlsx', headers, rows_out, sheet_title='Tickets SAV')

    return Response(pivot)


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def sav_tickets_cout_moyen(request):
    """ZSAV7 — coût interne moyen par technicien (mesure gated
    `prix_achat_voir`). Renvoie 403 explicite sans la permission — jamais un
    JSON avec le champ silencieusement absent (pas d'ambiguïté "vide" vs
    "masqué")."""
    company = _co(request.user)
    if company is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    if not request.user.can_view_buy_prices:
        return Response(
            {'detail': 'Coût interne réservé (permission prix_achat_voir).'},
            status=403)

    from core import data_explorer

    rows = data_explorer.run_query(
        'sav_tickets', company, request.user, {
            'group_by': ['technicien_responsable__username'],
            'aggregates': [
                {'alias': 'cout_moyen', 'fn': 'avg', 'field': 'cout'},
                {'alias': 'n', 'fn': 'count', 'field': 'id'},
            ],
        })
    return Response({'rows': rows})


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def sav_taux_attache(request):
    """YSERV10 — ``GET reporting/insights/sav-taux-attache/`` : part des
    chantiers réceptionnés de la période (``?date_debut=``/``?date_fin=``,
    ISO ``YYYY-MM-DD``) qui ont un contrat de maintenance actif ≤90 j après
    réception. Lu via ``apps.sav.selectors.taux_attache`` (frontière
    cross-app — jamais un import de ``apps.sav.models``)."""
    company = _co(request.user)
    if company is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    from apps.sav.selectors import taux_attache

    date_debut = request.query_params.get('date_debut') or None
    date_fin = request.query_params.get('date_fin') or None
    result = taux_attache(company, date_debut=date_debut, date_fin=date_fin)
    return Response(result)
