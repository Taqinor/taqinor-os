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

    ca_paye = factures_qs.filter(
        statut=Facture.Statut.PAYEE
    ).aggregate(total=Sum('lignes__prix_unitaire'))['total'] or Decimal('0')

    # CA payé calculé proprement via les lignes
    ca_paye = _ca_factures(factures_qs.filter(statut=Facture.Statut.PAYEE))

    # Factures en attente (émises + en retard)
    ca_attente = _ca_factures(
        factures_qs.filter(statut__in=[Facture.Statut.EMISE, Facture.Statut.EN_RETARD])
    )

    nb_clients = Client.objects.filter(**co).count()

    # Valeur stock = quantite * prix_vente
    produits = Produit.objects.filter(**co, is_archived=False)
    valeur_stock_dh = sum(
        (p.quantite_stock or 0) * p.prix_vente for p in produits
    )

    # ── CA mensuel (12 derniers mois) ─────────────────────────────────────────
    debut = date.today().replace(day=1) - timedelta(days=365)
    # Calcule le CA HT par mois via les lignes
    ca_mensuel = _ca_mensuel(
        factures_qs.filter(statut=Facture.Statut.PAYEE, date_emission__gte=debut)
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
    nb_devis_acceptes = devis_qs.filter(statut=Devis.Statut.ACCEPTE).count()
    nb_factures_emises = factures_qs.exclude(
        statut__in=[Facture.Statut.BROUILLON, Facture.Statut.ANNULEE]
    ).count()

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
    today = date.today()
    factures_impayees = (
        factures_qs
        .filter(statut__in=[Facture.Statut.EMISE, Facture.Statut.EN_RETARD])
        .select_related('client')
        .prefetch_related('lignes')
    )
    creances = {}
    for f in factures_impayees:
        cid = f.client_id
        if cid not in creances:
            creances[cid] = {
                'client': str(f.client),
                'nb_factures': 0,
                'montant_total': Decimal('0'),
                'jours_retard_max': 0,
            }
        montant = sum(
            ligne.quantite * ligne.prix_unitaire * (1 - ligne.remise / 100)
            for ligne in f.lignes.all()
        )
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
            ['KPI', 'CA encaissé (DH)', float(ca_paye), 'Factures payées'],
            ['KPI', 'En attente de paiement (DH)', float(ca_attente),
             'Émises + en retard'],
            ['KPI', 'Clients actifs', nb_clients, 'Total base clients'],
            ['KPI', 'Valeur du stock (DH)', float(valeur_stock_dh),
             'Prix vente × quantité'],
        ]
        for c in creances_list:
            rows.append([
                'Créance', c['client'], c['montant_total'],
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
        prev_ca = _ca_factures(prev_fqs.filter(statut=Facture.Statut.PAYEE))
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
        curr_ca = _ca_factures(curr_fqs_f.filter(statut=Facture.Statut.PAYEE))
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
        },
        'stock_alerte': stock_alerte_list,
        'creances': creances_list,
        'comparison': comparison,
    })


def _ca_factures(qs):
    """Calcule le CA HT total d'un queryset de Facture."""
    total = Decimal('0')
    for f in qs.prefetch_related('lignes'):
        for ligne in f.lignes.all():
            total += ligne.quantite * ligne.prix_unitaire * (1 - ligne.remise / 100)
    return total


def _ca_mensuel(factures_qs):
    """
    Retourne le CA HT par mois pour les 12 derniers mois.
    Format : [{'mois': 'Jan 2025', 'ca': 12345.67}, ...]
    """
    from collections import defaultdict

    par_mois = defaultdict(Decimal)
    for f in factures_qs.prefetch_related('lignes'):
        cle = f.date_emission.strftime('%Y-%m')
        for ligne in f.lignes.all():
            par_mois[cle] += ligne.quantite * ligne.prix_unitaire * (1 - ligne.remise / 100)

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
