from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum, Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.ventes.models import Facture, LigneFacture, Devis
from apps.stock.models import Produit
from apps.crm.models import Client
from authentication.permissions import IsResponsableOrAdmin
from core.analytics_db import analytics_queryset
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema


def _co(user):
    """Return company filter kwargs or None for superuser."""
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


# ── FG92 — comparaison périodique ─────────────────────────────────────────────
def _prior_period(start, end):
    """Retourne (prev_start, prev_end) décalé d'un mois ou d'un an.

    Si start/end sont None, on calcule la fenêtre du mois courant vs le mois
    précédent (compare='prev') ou le même mois l'an passé (compare='yoy').
    """
    today = date.today()
    if start is None or end is None:
        # Par défaut : mois courant
        start = today.replace(day=1)
        end = today
    span = (end - start).days + 1
    return start - timedelta(days=span), end - timedelta(days=span)


def _yoy_period(start, end):
    """Même fenêtre, un an avant."""
    today = date.today()
    if start is None or end is None:
        start = today.replace(day=1)
        end = today
    try:
        prev_start = start.replace(year=start.year - 1)
    except ValueError:
        prev_start = start - timedelta(days=366)
    try:
        prev_end = end.replace(year=end.year - 1)
    except ValueError:
        prev_end = end - timedelta(days=366)
    return prev_start, prev_end


def _compare_kpi(current, previous):
    """Retourne {current, previous, delta_pct} pour un KPI numérique."""
    delta = None
    if previous and float(previous) != 0:
        delta = round((float(current) - float(previous)) / float(previous) * 100, 1)
    return {
        'current': float(current),
        'previous': float(previous),
        'delta_pct': delta,
    }


def _qdate(value):
    """Parse une date au format ISO, ou None."""
    try:
        return date.fromisoformat((value or '').strip())
    except (ValueError, TypeError):
        return None


@extend_schema(
    parameters=[
        OpenApiParameter('compare', OpenApiTypes.STR, required=False),
        OpenApiParameter('from', OpenApiTypes.STR, required=False),
        OpenApiParameter('to', OpenApiTypes.STR, required=False),
        OpenApiParameter('export', OpenApiTypes.STR, required=False),
    ],
    responses={(200, 'application/json'): OpenApiTypes.ANY,
               (200, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'): OpenApiTypes.BINARY})
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def dashboard(request):
    """
    Retourne tous les agregats pour la page Reporting en un seul appel.
    Toutes les donnees sont filtrees par company de l'utilisateur connecte.
    """
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Acces refuse.'}, status=403)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    factures_qs = Facture.objects.filter(**co)

    # AANA20 / D-AANA-6 — CA en HT lu sur ``Facture.total_ht`` (remise
    # globale honorée), jamais une somme de lignes. Le reliquat d'une facture
    # « payée » n'est PAS encaissé : il reste en attente.
    factures_payees = factures_qs.filter(statut=Facture.Statut.PAYEE)
    ca_paye = _ca_encaisse_ht(factures_payees)

    # Factures en attente (émises + en retard) + reliquats des « payées ».
    ca_attente = _ca_attente_ht(
        factures_qs.filter(
            statut__in=[Facture.Statut.EMISE, Facture.Statut.EN_RETARD]),
        factures_payees,
    )

    nb_clients = Client.objects.filter(**co).count()

    # Valeur stock = quantite * prix_vente
    produits = Produit.objects.filter(**co, is_archived=False)
    valeur_stock_dh = sum(
        (p.quantite_stock or 0) * p.prix_vente for p in produits
    )

    # ── CA mensuel (12 derniers mois) ─────────────────────────────────────────
    debut = date.today().replace(day=1) - timedelta(days=365)
    # CA HT encaissé par mois (Facture.total_ht — AANA20)
    ca_mensuel = _ca_mensuel(
        factures_payees.filter(date_emission__gte=debut)
    )

    # ── Top 5 produits vendus ─────────────────────────────────────────────────
    # YHARD9 — agrégats BI (lecture seule) : route vers le réplica analytique si
    # configuré, no-op strict sinon. Scoping société inchangé (filtres préservés).
    top_produits = (
        analytics_queryset(LigneFacture.objects)
        .filter(facture__in=factures_qs.filter(statut=Facture.Statut.PAYEE))
        .values('produit__nom')
        .annotate(qte=Sum('quantite'))
        .order_by('-qte')[:5]
    )

    # ── Statuts des factures ──────────────────────────────────────────────────
    statuts_factures = (
        analytics_queryset(factures_qs)
        .values('statut')
        .annotate(nb=Count('id'))
        .order_by('statut')
    )
    statut_labels = {
        'brouillon': 'Brouillon',
        'emise': 'Émise',
        'payee': 'Payée',
        'en_retard': 'En retard',
        'annulee': 'Annulée',
    }
    statut_colors = {
        'brouillon': '#94a3b8',
        'emise': '#3b82f6',
        'payee': '#22c55e',
        'en_retard': '#ef4444',
        'annulee': '#f59e0b',
    }

    # ── Taux conversion Devis → Facture ───────────────────────────────────────
    devis_qs = Devis.objects.filter(**co)
    nb_devis_total = devis_qs.count()
    # AANA19 — signés = acceptés ACTIFS (helper unique du reporting).
    from apps.reporting.pipeline import _devis_signes
    nb_devis_acceptes = _devis_signes(co).count()
    nb_factures_emises = factures_qs.exclude(
        statut__in=[Facture.Statut.BROUILLON, Facture.Statut.ANNULEE]
    ).count()
    # AANA28 (contrat AANA1, dashboard.json) — taux d'acceptation SERVI :
    # devis acceptés ÷ devis créés, 1 décimale, None sans devis. L'écran le
    # lit tel quel (fini la formule nb_factures ÷ nb_devis, qui dépassait
    # 100 %).
    taux_acceptation_pct = (
        round(nb_devis_acceptes / nb_devis_total * 100, 1)
        if nb_devis_total else None)

    # ── Stock critique (produits sous seuil, seuil > 0) ───────────────────────
    from django.db.models import F
    stock_alerte_list = list(
        Produit.objects
        .filter(**co, is_archived=False)
        .exclude(seuil_alerte=0)
        .filter(quantite_stock__lte=F('seuil_alerte'))
        .order_by('quantite_stock')
        .values('nom', 'quantite_stock', 'seuil_alerte')[:15]
    )

    # ── Créances clients ──────────────────────────────────────────────────────
    # AANA20 / D-AANA-6 — la créance est ``Facture.montant_du`` (TTC restant
    # dû : paiements, retenues, avoirs et abandons déduits, notes de débit
    # ajoutées), jamais une somme HT de lignes.
    today = date.today()
    factures_impayees = (
        factures_qs
        .filter(statut__in=[Facture.Statut.EMISE, Facture.Statut.EN_RETARD])
        .select_related('client')
        .prefetch_related('lignes')
    )
    creances = {}
    for f in factures_impayees:
        montant = f.montant_du
        if montant <= 0:
            continue
        cid = f.client_id
        if cid not in creances:
            creances[cid] = {
                'client': str(f.client),
                'nb_factures': 0,
                'montant_total': Decimal('0'),
                'jours_retard_max': 0,
            }
        creances[cid]['nb_factures'] += 1
        creances[cid]['montant_total'] += montant
        if f.date_echeance:
            retard = (today - f.date_echeance).days
            if retard > creances[cid]['jours_retard_max']:
                creances[cid]['jours_retard_max'] = retard

    creances_list = sorted(
        [
            {**v, 'montant_total': float(v['montant_total'])}
            for v in creances.values()
        ],
        key=lambda x: x['montant_total'],
        reverse=True,
    )[:10]

    # ── Export .xlsx (KPIs + créances clients) — scopé société ────────────
    if request.query_params.get('export') == 'xlsx':
        from apps.crm.exports import build_xlsx_response
        headers = ['Section', 'Libellé', 'Valeur', 'Détail']
        rows = [
            ['KPI', 'CA encaissé HT (DH)', float(ca_paye), 'Factures payées'],
            ['KPI', 'En attente de paiement HT (DH)', float(ca_attente),
             'Émises + en retard (+ reliquats)'],
            ['KPI', 'Clients actifs', nb_clients, 'Total base clients'],
            ['KPI', 'Valeur du stock (DH)', float(valeur_stock_dh),
             'Prix vente × quantité'],
        ]
        for c in creances_list:
            rows.append([
                'Créance TTC restant dû', c['client'], c['montant_total'],
                f"{c['nb_factures']} facture(s) · retard max "
                f"{c['jours_retard_max']} j",
            ])
        return build_xlsx_response(
            'reporting-dashboard.xlsx', headers, rows, sheet_title='Reporting')

    # ── FG92 — comparaison période (?compare=prev|yoy) ───────────────────────
    compare = request.query_params.get('compare')
    comparison = None
    if compare in ('prev', 'yoy'):
        from_param = _qdate(request.query_params.get('from'))
        to_param = _qdate(request.query_params.get('to'))
        if compare == 'prev':
            p_start, p_end = _prior_period(from_param, to_param)
        else:
            p_start, p_end = _yoy_period(from_param, to_param)
        prev_fqs = factures_qs.filter(
            date_emission__gte=p_start,
            date_emission__lte=p_end)
        prev_ca = _ca_encaisse_ht(prev_fqs.filter(statut=Facture.Statut.PAYEE))
        prev_leads = 0
        try:
            from apps.crm.models import Lead
            prev_leads = Lead.objects.filter(
                **co, date_creation__date__gte=p_start,
                date_creation__date__lte=p_end).count()
        except Exception:
            pass
        from apps.crm.models import Lead
        curr_from = _qdate(request.query_params.get('from'))
        curr_to = _qdate(request.query_params.get('to'))
        curr_fqs_f = factures_qs
        if curr_from:
            curr_fqs_f = curr_fqs_f.filter(date_emission__gte=curr_from)
        if curr_to:
            curr_fqs_f = curr_fqs_f.filter(date_emission__lte=curr_to)
        curr_ca = _ca_encaisse_ht(curr_fqs_f.filter(statut=Facture.Statut.PAYEE))
        curr_leads = Lead.objects.filter(**co)
        if curr_from:
            curr_leads = curr_leads.filter(date_creation__date__gte=curr_from)
        if curr_to:
            curr_leads = curr_leads.filter(date_creation__date__lte=curr_to)
        curr_leads_count = curr_leads.count()
        comparison = {
            'period': compare,
            'prev_start': p_start.isoformat(),
            'prev_end': p_end.isoformat(),
            'ca_paye': _compare_kpi(curr_ca, prev_ca),
            'nb_leads': _compare_kpi(curr_leads_count, prev_leads),
        }

    return Response({
        'kpis': {
            'ca_paye': float(ca_paye),
            'ca_attente': float(ca_attente),
            'nb_clients': nb_clients,
            'valeur_stock': float(valeur_stock_dh),
        },
        'ca_mensuel': ca_mensuel,
        'top_produits': [
            {'nom': t['produit__nom'], 'qte': float(t['qte'])}
            for t in top_produits
        ],
        'statuts_factures': [
            {
                'name': statut_labels.get(s['statut'], s['statut']),
                'value': s['nb'],
                'color': statut_colors.get(s['statut'], '#94a3b8'),
            }
            for s in statuts_factures
        ],
        'conversion': {
            'nb_devis': nb_devis_total,
            'nb_acceptes': nb_devis_acceptes,
            'nb_factures': nb_factures_emises,
            'taux_acceptation_pct': taux_acceptation_pct,
        },
        'stock_alerte': stock_alerte_list,
        'creances': creances_list,
        'comparison': comparison,
    })


def _ht_encaisse(facture):
    """AANA20 — HT réellement encaissé d'une facture « payée ».

    ``Facture.total_ht`` (remise globale honorée), moins la part HT de son
    reliquat ``montant_du`` (TTC) : un reliquat n'est jamais compté encaissé.
    """
    total_ht = Decimal(facture.total_ht or 0)
    reste = Decimal(facture.montant_du or 0)
    if reste <= 0 or total_ht <= 0:
        return total_ht
    total_ttc = Decimal(facture.total_ttc or 0)
    if total_ttc <= 0:
        return total_ht
    encaisse = total_ht - (reste * total_ht / total_ttc)
    return encaisse if encaisse > 0 else Decimal('0')


def _reliquat_ht(facture):
    """AANA20 — part HT du reliquat d'une facture « payée » (0 si soldée)."""
    return Decimal(facture.total_ht or 0) - _ht_encaisse(facture)


def _ca_encaisse_ht(factures_payees):
    """AANA20 / D-AANA-6 — CA encaissé HT d'un queryset de factures payées."""
    return sum((_ht_encaisse(f)
                for f in factures_payees.prefetch_related('lignes')),
               Decimal('0'))


def _ca_attente_ht(factures_ouvertes, factures_payees):
    """AANA20 / D-AANA-6 — CA HT en attente : ``total_ht`` des factures
    émises/en retard + la part HT des reliquats des factures « payées »."""
    total = sum((Decimal(f.total_ht or 0)
                 for f in factures_ouvertes.prefetch_related('lignes')),
                Decimal('0'))
    total += sum((_reliquat_ht(f)
                  for f in factures_payees.prefetch_related('lignes')),
                 Decimal('0'))
    return total


def _ca_mensuel(factures_qs):
    """
    Retourne le CA HT ENCAISSÉ par mois pour les 12 derniers mois.
    Format : [{'mois': 'Jan 2025', 'ca': 12345.67}, ...]

    AANA20 — lu sur ``Facture.total_ht`` (via ``_ht_encaisse``), jamais une
    somme de lignes.
    """
    from collections import defaultdict

    par_mois = defaultdict(Decimal)
    for f in factures_qs.prefetch_related('lignes'):
        cle = f.date_emission.strftime('%Y-%m')
        par_mois[cle] += _ht_encaisse(f)

    mois_labels = {
        '01': 'Jan', '02': 'Fév', '03': 'Mar', '04': 'Avr',
        '05': 'Mai', '06': 'Jun', '07': 'Jul', '08': 'Aoû',
        '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Déc',
    }

    result = []
    # Recule de mois CALENDAIRES (12 mois distincts finissant ce mois) — un
    # recul en jours (i*30) dérive et peut sauter ou dupliquer un mois.
    cur = date.today().replace(day=1)
    months = []
    for _ in range(12):
        months.append(cur)
        # Mois précédent : le 1er du mois courant moins un jour, ramené au 1er.
        cur = (cur - timedelta(days=1)).replace(day=1)
    for d in reversed(months):
        cle = d.strftime('%Y-%m')
        mois_num = d.strftime('%m')
        label = f"{mois_labels[mois_num]} {d.year}"
        result.append({'mois': label, 'ca': float(par_mois.get(cle, 0))})

    return result
