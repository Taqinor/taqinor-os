"""T13/T14/T15 — Hub « Rapports » (lecture seule, multi-tenant).

Trois rapports agrégés à la lecture : ventes/pipeline (T13), stock (T14),
service chantier+SAV (T15). Chacun renvoie du JSON ; avec ?format=xlsx il
renvoie un .xlsx (table principale). Le PRIX D'ACHAT (stock) est interne :
présent dans le rapport stock (usage interne), jamais dans un export client.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum, F, DecimalField
from django.db.models.functions import Coalesce
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from apps.crm.exports import build_xlsx_response
from apps.crm import stages as stage_mod


def _co(user):
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


def _maybe_xlsx(request, filename, headers, rows, title):
    # NB: on n'utilise PAS le paramètre `format` (réservé par DRF pour la
    # négociation de contenu) — d'où `export=xlsx`.
    if request.query_params.get('export') == 'xlsx':
        return build_xlsx_response(filename, headers, rows, sheet_title=title)
    return None


# FG95 — export PDF branded (WeasyPrint + Jinja2)
def _maybe_pdf(request, pdf_title, sections, pdf_filename, period_label=''):
    """Retourne un HttpResponse PDF si ?export=pdf, sinon None.

    Jamais de prix d'achat dans les sections transmises ici.
    """
    if request.query_params.get('export') != 'pdf':
        return None
    from apps.parametres.models import CompanyProfile
    from apps.reporting.report_pdf import render_report_pdf, pdf_response
    try:
        profile = CompanyProfile.get(company=request.user.company)
    except Exception:
        profile = None
    pdf_bytes = render_report_pdf(
        title=pdf_title,
        sections=sections,
        company_profile=profile,
        period_label=period_label,
    )
    return pdf_response(pdf_bytes, filename=pdf_filename)


def _qdate(value):
    """Parse une date ?from=/?to= au format ISO (AAAA-MM-JJ), ou None."""
    try:
        return date.fromisoformat((value or '').strip())
    except (ValueError, TypeError):
        return None


def _period(request):
    """Fenêtre de période depuis ?from=&to= (chacune optionnelle)."""
    return (_qdate(request.query_params.get('from')),
            _qdate(request.query_params.get('to')))


# ── FG92 — comparaison périodique ─────────────────────────────────────────────
def _prior_window(start, end):
    """Décale la fenêtre d'un écart équivalent (MoM)."""
    today = date.today()
    s = start or today.replace(day=1)
    e = end or today
    span = (e - s).days + 1
    return s - timedelta(days=span), e - timedelta(days=span)


def _yoy_window(start, end):
    """Même fenêtre, un an avant."""
    today = date.today()
    s = start or today.replace(day=1)
    e = end or today
    try:
        ps = s.replace(year=s.year - 1)
    except ValueError:
        ps = s - timedelta(days=366)
    try:
        pe = e.replace(year=e.year - 1)
    except ValueError:
        pe = e - timedelta(days=366)
    return ps, pe


def _compare_kpi(current, previous):
    """Retourne {current, previous, delta_pct}."""
    c, p = float(current), float(previous)
    delta = round((c - p) / p * 100, 1) if p else None
    return {'current': c, 'previous': p, 'delta_pct': delta}


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def sales_report(request):
    """T13 — ventes/pipeline : funnel par étape, par responsable, par canal,
    par mois, gains/pertes par motif."""
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    from apps.crm.models import Lead
    from apps.ventes.models import Devis
    from apps.ventes.utils.expiry import is_expired

    start, end = _period(request)
    leads = Lead.objects.filter(**co, is_archived=False)
    if start:
        leads = leads.filter(date_creation__date__gte=start)
    if end:
        leads = leads.filter(date_creation__date__lte=end)

    funnel = []
    total = leads.count()
    for key in stage_mod.STAGES:
        n = leads.filter(stage=key).count()
        funnel.append({'stage': key, 'label': stage_mod.STAGE_LABELS.get(key, key),
                       'count': n})
    par_responsable = list(
        leads.values('owner__username')
        .annotate(count=Count('id'),
                  gagnes=Count('id', filter=models_q_signed()))
        .order_by('-count'))
    par_canal = list(
        leads.values('canal').annotate(count=Count('id')).order_by('-count'))
    perdus = list(
        leads.filter(perdu=True).values('motif_perte')
        .annotate(count=Count('id')).order_by('-count'))

    # ── Devis par statut (expiration à la volée) — un bucket « Expiré »
    #    apparaît pour les devis en attente dont la validité est dépassée. ──
    devis_qs = Devis.objects.filter(**co)
    if start:
        devis_qs = devis_qs.filter(date_creation__date__gte=start)
    if end:
        devis_qs = devis_qs.filter(date_creation__date__lte=end)
    statut_labels = dict(Devis.Statut.choices)
    statut_labels['expire'] = 'Expiré'
    devis_buckets = {}
    for d in devis_qs:
        statut = 'expire' if is_expired(d) else d.statut
        devis_buckets[statut] = devis_buckets.get(statut, 0) + 1
    devis_par_statut = [
        {'statut': k, 'label': statut_labels.get(k, k), 'count': v}
        for k, v in sorted(devis_buckets.items(), key=lambda kv: -kv[1])
    ]

    rows = [[f['label'], f['count']] for f in funnel]
    x = _maybe_xlsx(request, 'rapport-ventes.xlsx',
                    ['Étape', 'Leads'], rows, 'Ventes')
    if x:
        return x

    # FG95 — export PDF branded
    period_label = ''
    if start or end:
        _s = start.isoformat() if start else '…'
        _e = end.isoformat() if end else "aujourd'hui"
        period_label = f"{_s} → {_e}"
    p = _maybe_pdf(
        request, 'Rapport Ventes',
        sections=[
            {'title': 'Funnel pipeline',
             'kv': [{'label': 'Leads total', 'value': str(total)}],
             'table': {'headers': ['Étape', 'Leads'], 'rows': rows}},
            {'title': 'Par canal',
             'kv': None,
             'table': {'headers': ['Canal', 'Leads'],
                       'rows': [[c['canal'] or '—', c['count']] for c in par_canal]}},
            {'title': 'Pertes par motif',
             'kv': None,
             'table': {'headers': ['Motif', 'Leads perdus'],
                       'rows': [[p['motif_perte'] or '—', p['count']] for p in perdus]}},
        ],
        pdf_filename='rapport-ventes.pdf',
        period_label=period_label,
    )
    if p:
        return p

    # FG92 — comparaison périodique (?compare=prev|yoy)
    comparison = None
    compare = request.query_params.get('compare')
    if compare in ('prev', 'yoy'):
        if compare == 'prev':
            p_start, p_end = _prior_window(start, end)
        else:
            p_start, p_end = _yoy_window(start, end)
        prev_leads = Lead.objects.filter(**co, is_archived=False)
        if p_start:
            prev_leads = prev_leads.filter(date_creation__date__gte=p_start)
        if p_end:
            prev_leads = prev_leads.filter(date_creation__date__lte=p_end)
        prev_total = prev_leads.count()
        prev_signed = prev_leads.filter(stage='SIGNED').count()
        curr_signed = leads.filter(stage='SIGNED').count()
        comparison = {
            'period': compare,
            'prev_start': p_start.isoformat() if p_start else None,
            'prev_end': p_end.isoformat() if p_end else None,
            'total_leads': _compare_kpi(total, prev_total),
            'leads_signes': _compare_kpi(curr_signed, prev_signed),
        }

    return Response({
        'funnel': funnel, 'total_leads': total,
        'par_responsable': par_responsable, 'par_canal': par_canal,
        'perdus_par_motif': perdus,
        'devis_par_statut': devis_par_statut,
        'comparison': comparison,
    })


def models_q_signed():
    from django.db.models import Q
    return Q(stage='SIGNED')


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def stock_report(request):
    """T14 — stock : valorisation (vente + achat interne), bas stock, par
    catégorie. Le prix d'achat reste un repère INTERNE."""
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    from apps.stock.models import Produit
    qs = Produit.objects.filter(**co, is_archived=False)

    dec = DecimalField()
    sum_vente = Coalesce(
        Sum(F('prix_vente') * F('quantite_stock'), output_field=dec),
        Decimal('0'))
    sum_achat = Coalesce(
        Sum(F('prix_achat') * F('quantite_stock'), output_field=dec),
        Decimal('0'))
    val_vente = qs.aggregate(t=sum_vente)['t']
    val_achat = qs.aggregate(t=sum_achat)['t']
    par_categorie = list(
        qs.values('categorie__nom')
        .annotate(nb=Count('id'), valeur_vente=sum_vente)
        .order_by('-valeur_vente'))
    # ERR57 — `seuil_alerte=0` signifie « aucun seuil » : exclu de la liste bas
    # stock (cohérent avec le dashboard), sinon tout produit à 0 en stock par
    # défaut serait faussement signalé.
    bas_stock = list(
        qs.exclude(seuil_alerte=0)
        .filter(quantite_stock__lte=F('seuil_alerte'))
        .values('nom', 'sku', 'quantite_stock', 'seuil_alerte')[:200])

    rows = [[c['categorie__nom'] or '—', c['nb'], str(c['valeur_vente'])]
            for c in par_categorie]
    x = _maybe_xlsx(request, 'rapport-stock.xlsx',
                    ['Catégorie', 'Articles', 'Valeur vente HT'], rows, 'Stock')
    if x:
        return x

    # FG95 — export PDF branded (valorisation achat JAMAIS dans le PDF client)
    p = _maybe_pdf(
        request, 'Rapport Stock',
        sections=[
            {'title': 'Valorisation par catégorie',
             'kv': [{'label': 'Valeur vente totale (HT)',
                     'value': f'{val_vente:,.0f} MAD'}],
             'table': {'headers': ['Catégorie', 'Articles', 'Valeur vente HT (MAD)'],
                       'rows': rows}},
            {'title': 'Articles en bas stock',
             'kv': None,
             'table': {'headers': ['Nom', 'SKU', 'Quantité', 'Seuil alerte'],
                       'rows': [[b['nom'], b['sku'] or '—',
                                 b['quantite_stock'], b['seuil_alerte']]
                                for b in bas_stock]}},
        ],
        pdf_filename='rapport-stock.pdf',
    )
    if p:
        return p

    return Response({
        'valorisation_vente': str(val_vente),
        'valorisation_achat': str(val_achat),  # interne, non client-facing
        'par_categorie': [
            {**c, 'valeur_vente': str(c['valeur_vente'])} for c in par_categorie],
        'bas_stock': bas_stock,
    })


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def service_report(request):
    """T15 — service : chantiers par statut, activité technicien, SAV ouverts
    vs résolus, garanties expirant ≤90 j."""
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    from apps.installations.models import Installation, Intervention
    from apps.sav.models import Equipement, Ticket

    start, end = _period(request)
    inst_qs = Installation.objects.filter(**co)
    interv_qs = Intervention.objects.filter(**co)
    ticket_qs = Ticket.objects.filter(**co)
    if start:
        inst_qs = inst_qs.filter(date_creation__date__gte=start)
        interv_qs = interv_qs.filter(date_prevue__gte=start)
        ticket_qs = ticket_qs.filter(date_creation__date__gte=start)
    if end:
        inst_qs = inst_qs.filter(date_creation__date__lte=end)
        interv_qs = interv_qs.filter(date_prevue__lte=end)
        ticket_qs = ticket_qs.filter(date_creation__date__lte=end)

    chantiers_statut = list(
        inst_qs.values('statut')
        .annotate(count=Count('id')).order_by('-count'))
    interventions_tech = list(
        interv_qs.values('technicien__username')
        .annotate(count=Count('id')).order_by('-count'))
    tickets_statut = list(
        ticket_qs.values('statut')
        .annotate(count=Count('id')).order_by('-count'))
    open_statuts = list(Ticket.OPEN_STATUTS)
    tickets_ouverts = ticket_qs.filter(statut__in=open_statuts).count()
    tickets_resolus = ticket_qs.exclude(
        statut__in=open_statuts).count()
    horizon = date.today() + timedelta(days=90)
    garanties = Equipement.objects.filter(
        **co, date_fin_garantie__gte=date.today(),
        date_fin_garantie__lte=horizon).count()

    # YSERV12 — taux de résolution à distance (KPI d'évitement de
    # déplacement). Company requise par le sélecteur ; superuser sans société
    # (co == {}) est simplement omis (comme les autres compteurs ci-dessus,
    # qui sont déjà scopés implicitement par ticket_qs).
    resolution_a_distance = None
    if request.user.company_id:
        from apps.sav.selectors import taux_resolution_a_distance
        resolution_a_distance = taux_resolution_a_distance(
            request.user.company, date_debut=start, date_fin=end,
            group_by_technicien=True)

    rows = [[c['statut'], c['count']] for c in chantiers_statut]
    x = _maybe_xlsx(request, 'rapport-service.xlsx',
                    ['Statut chantier', 'Nombre'], rows, 'Service')
    if x:
        return x

    # FG95 — export PDF branded
    p = _maybe_pdf(
        request, 'Rapport Service',
        sections=[
            {'title': 'Chantiers par statut',
             'kv': None,
             'table': {'headers': ['Statut', 'Nombre'], 'rows': rows}},
            {'title': 'Interventions par technicien',
             'kv': None,
             'table': {'headers': ['Technicien', 'Interventions'],
                       'rows': [[i['technicien__username'] or '—', i['count']]
                                for i in interventions_tech]}},
            {'title': 'Tickets par statut',
             'kv': [{'label': 'Tickets ouverts', 'value': str(tickets_ouverts)},
                    {'label': 'Tickets résolus', 'value': str(tickets_resolus)},
                    {'label': 'Garanties expirant ≤90 j',
                     'value': str(garanties)}],
             'table': {'headers': ['Statut ticket', 'Nombre'],
                       'rows': [[t['statut'], t['count']] for t in tickets_statut]}},
        ],
        pdf_filename='rapport-service.pdf',
    )
    if p:
        return p

    return Response({
        'chantiers_par_statut': chantiers_statut,
        'interventions_par_technicien': interventions_tech,
        'tickets_par_statut': tickets_statut,
        'tickets_ouverts': tickets_ouverts,
        'tickets_resolus': tickets_resolus,
        'garanties_expirantes_90j': garanties,
        # YSERV12 — KPI d'évitement de déplacement.
        'resolution_a_distance': resolution_a_distance,
    })


# ── ARC40 — KPI fédérés pilotés par le registre plateforme ───────────────────

@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def kpi_federes(request):
    """ARC40 — endpoint KPI fédéré : agrège les tuiles des providers déclarés.

    Avant ARC40, ce hub n'agrégeait que 3 rapports (ventes/stock/service) —
    rh/paie/contrats/compta/gestion_projet/qhse avaient une empreinte
    reporting NULLE. Cet endpoint itère la surface ``kpi_providers`` du
    registre plateforme (``core.platform.kpi_providers(company)`` — gatée
    ``ModuleToggle`` : un module OFF disparaît avec ses tuiles) : chaque
    provider est un CALLABLE DOTTED (ex.
    ``apps.rh.selectors.kpi_effectifs_absences``) résolu à l'exécution,
    appelé ``provider(company)``, qui renvoie des tuiles normalisées
    ``{id, label, valeur, unite?}``. Le reporting n'importe AUCUN modèle des
    apps fournisseuses — la frontière inter-app passe par leurs selectors.

    Un provider déclaré apparaît donc SANS toucher ce fichier ; une clé
    non-dotted (héritage informatif, ex. ``crm_sales_report``) ou un dotted
    introuvable est ignoré silencieusement (jamais un 500 pour une
    déclaration cassée). Company-scopé : un superuser sans société reçoit une
    liste vide (mêmes conventions que les autres rapports).
    """
    import importlib

    from core import platform as core_platform

    company = request.user.company
    if company is None:
        return Response({'count': 0, 'tuiles': []})

    tuiles = []
    for dotted in sorted(core_platform.kpi_providers(company)):
        if '.' not in dotted:
            # Clé libre héritée (informative), pas un provider résoluble.
            continue
        module_path, func_name = dotted.rsplit('.', 1)
        try:
            provider = getattr(importlib.import_module(module_path), func_name)
        except (ImportError, AttributeError):
            # Provider déclaré mais introuvable : ignoré, jamais un 500.
            continue
        for tuile in (provider(company) or []):
            if (not isinstance(tuile, dict) or 'id' not in tuile
                    or 'label' not in tuile or 'valeur' not in tuile):
                continue  # tuile non conforme à la forme normalisée : ignorée
            normalisee = {
                'id': tuile['id'],
                'label': tuile['label'],
                'valeur': tuile['valeur'],
                'provider': dotted,
            }
            if tuile.get('unite'):
                normalisee['unite'] = tuile['unite']
            tuiles.append(normalisee)

    return Response({'count': len(tuiles), 'tuiles': tuiles})
