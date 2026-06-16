from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum, Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.ventes.models import Facture, LigneFacture, Devis
from apps.stock.models import Produit
from apps.crm.models import Client
from authentication.permissions import IsResponsableOrAdmin

from . import helpers


def _co(user):
    """Return company filter kwargs or None for superuser."""
    return helpers.company_filter(user)


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
    top_produits = (
        LigneFacture.objects
        .filter(facture__in=factures_qs.filter(statut=Facture.Statut.PAYEE))
        .values('produit__nom')
        .annotate(qte=Sum('quantite'))
        .order_by('-qte')[:5]
    )

    # ── Statuts des factures ──────────────────────────────────────────────────
    statuts_factures = (
        factures_qs
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
    today = date.today()
    for i in range(11, -1, -1):
        d = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        cle = d.strftime('%Y-%m')
        mois_num = d.strftime('%m')
        label = f"{mois_labels[mois_num]} {d.year}"
        result.append({'mois': label, 'ca': float(par_mois.get(cle, 0))})

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  Rapports analytiques — LECTURE SEULE. Toutes les requêtes sont scopées par
#  société (multi-tenant). Les étapes du pipeline viennent de STAGES.py via
#  apps.crm.stages — jamais codées en dur. Le prix d'achat (prix_achat) ne
#  paraît QUE dans la valorisation de stock interne (T14), jamais ailleurs.
# ═══════════════════════════════════════════════════════════════════════════

from apps.crm import stages as crm_stages           # noqa: E402
from apps.crm.models import Lead                     # noqa: E402
from apps.stock.models import MouvementStock         # noqa: E402
from apps.installations.models import Installation   # noqa: E402
from apps.sav.models import Ticket, Equipement       # noqa: E402

# Poids de prévision pondérée par étape (probabilité de signature). Les CLÉS
# viennent des étapes canoniques de STAGES.py (apps.crm.stages.STAGES) —
# jamais une liste codée en dur ici. Si une étape canonique n'a pas de poids
# explicite, elle reçoit le poids neutre 0 (aucune valeur inventée).
_FORECAST_WEIGHT_BY_KEY = {
    'NEW': Decimal('0.10'),
    'CONTACTED': Decimal('0.25'),
    'QUOTE_SENT': Decimal('0.50'),
    'FOLLOW_UP': Decimal('0.65'),
    'SIGNED': Decimal('1.00'),
    'COLD': Decimal('0.05'),
}
STAGE_FORECAST_WEIGHTS = {
    key: _FORECAST_WEIGHT_BY_KEY.get(key, Decimal('0'))
    for key in crm_stages.STAGES
}

# Étape « gagné » (conversion) — lue depuis le module canonique, jamais codée
# en dur (STAGES.py : CONVERSION_STAGE = SIGNED).
SIGNED_STAGE = getattr(
    crm_stages._stages, 'CONVERSION_STAGE',
    getattr(crm_stages._stages, 'SIGNED', crm_stages.STAGES[-2]))

DEVIS_STATUT_LABELS = dict(Devis.Statut.choices)
FACTURE_STATUT_LABELS = dict(Facture.Statut.choices)


def _devis_ttc(devis):
    """Total TTC d'un devis (propriété modèle), en Decimal."""
    return Decimal(devis.total_ttc)


def _lead_value(lead, devis_by_lead):
    """Valeur pipeline d'un lead : le TTC de son meilleur devis si présent,
    sinon une estimation depuis la facture annuelle (× 12 mois × ~5 ans de
    visibilité ramenée à 0 quand inconnue → on n'invente rien : 0)."""
    devis_list = devis_by_lead.get(lead.id)
    if devis_list:
        return max(_devis_ttc(d) for d in devis_list)
    return Decimal('0')


# ── T7b — Tableau de bord valeur du pipeline ─────────────────────────────────

@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def pipeline_value(request):
    """Valeur du pipeline par étape + prévision pondérée, devis par statut,
    et gagné/perdu par motif de perte. Lecture seule, filtrable par période
    (sur la date de création du lead)."""
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    debut, fin, label = helpers.parse_periode(request)
    leads_qs = Lead.objects.filter(**co, is_archived=False)
    leads_qs = helpers.apply_date_range(leads_qs, 'date_creation__date', debut, fin)

    leads = list(leads_qs)
    lead_ids = [le.id for le in leads]

    # Devis rattachés à ces leads (pour valoriser le pipeline).
    devis_by_lead = {}
    devis_qs = (
        Devis.objects.filter(**co, lead_id__in=lead_ids)
        .prefetch_related('lignes')
    )
    for d in devis_qs:
        devis_by_lead.setdefault(d.lead_id, []).append(d)

    # Valeur + prévision par étape.
    par_etape = {}
    for key in crm_stages.STAGES:
        par_etape[key] = {
            'stage': key,
            'label': crm_stages.STAGE_LABELS[key],
            'nb': 0,
            'valeur': Decimal('0'),
            'valeur_ponderee': Decimal('0'),
        }
    weight_default = Decimal('0')
    for le in leads:
        bucket = par_etape.get(le.stage)
        if bucket is None:
            continue
        val = _lead_value(le, devis_by_lead)
        weight = STAGE_FORECAST_WEIGHTS.get(le.stage, weight_default)
        bucket['nb'] += 1
        bucket['valeur'] += val
        bucket['valeur_ponderee'] += val * weight

    par_etape_list = [
        {
            'stage': b['stage'],
            'label': b['label'],
            'nb': b['nb'],
            'valeur': helpers.f2(b['valeur']),
            'valeur_ponderee': helpers.f2(b['valeur_ponderee']),
            'poids': float(STAGE_FORECAST_WEIGHTS.get(b['stage'], weight_default)),
        }
        for b in (par_etape[k] for k in crm_stages.STAGES)
    ]
    total_pipeline = sum((b['valeur'] for b in par_etape.values()), Decimal('0'))
    forecast = sum(
        (b['valeur_ponderee'] for b in par_etape.values()), Decimal('0'))

    # Devis par statut (count + valeur TTC) — sur la période (date_creation).
    dq = Devis.objects.filter(**co).prefetch_related('lignes')
    dq = helpers.apply_date_range(dq, 'date_creation__date', debut, fin)
    par_statut = {}
    for s, lbl in Devis.Statut.choices:
        par_statut[s] = {'statut': s, 'label': lbl, 'nb': 0,
                         'valeur': Decimal('0')}
    for d in dq:
        b = par_statut.get(d.statut)
        if b is None:
            continue
        b['nb'] += 1
        b['valeur'] += _devis_ttc(d)
    devis_par_statut = [
        {**b, 'valeur': helpers.f2(b['valeur'])}
        for b in par_statut.values()
    ]

    # Gagné / perdu par motif de perte.
    gagnes = leads_qs.filter(stage=SIGNED_STAGE, perdu=False).count()
    perdus_qs = leads_qs.filter(perdu=True)
    perdus = perdus_qs.count()
    win_loss_motifs = list(
        perdus_qs.values('motif_perte')
        .annotate(nb=Count('id'))
        .order_by('-nb')
    )
    win_loss = [
        {'motif': row['motif_perte'] or 'Non précisé', 'nb': row['nb']}
        for row in win_loss_motifs
    ]

    return Response({
        'periode': label,
        'total_pipeline': helpers.f2(total_pipeline),
        'forecast_pondere': helpers.f2(forecast),
        'par_etape': par_etape_list,
        'devis_par_statut': devis_par_statut,
        'win_loss': {
            'gagnes': gagnes,
            'perdus': perdus,
            'par_motif': win_loss,
        },
    })


# ── Helpers ventes partagés (T13) ────────────────────────────────────────────

def _sales_funnel(leads_qs):
    """Leads & conversion par étape (entonnoir)."""
    counts = dict(
        leads_qs.values_list('stage')
        .annotate(nb=Count('id'))
        .values_list('stage', 'nb')
    )
    return [
        {'stage': key, 'label': crm_stages.STAGE_LABELS[key],
         'nb': counts.get(key, 0)}
        for key in crm_stages.STAGES
    ]


def _devis_status_value(co, debut, fin):
    dq = Devis.objects.filter(**co).prefetch_related('lignes')
    dq = helpers.apply_date_range(dq, 'date_creation__date', debut, fin)
    buckets = {}
    for s, lbl in Devis.Statut.choices:
        buckets[s] = {'statut': s, 'label': lbl, 'nb': 0,
                      'valeur': Decimal('0')}
    for d in dq:
        b = buckets[d.statut]
        b['nb'] += 1
        b['valeur'] += _devis_ttc(d)
    return [{**b, 'valeur': helpers.f2(b['valeur'])} for b in buckets.values()]


def _sales_by(co, debut, fin):
    """CA (factures émises) par responsable, par canal (lead) et par mois."""
    fq = (
        Facture.objects.filter(**co)
        .exclude(statut__in=[Facture.Statut.BROUILLON, Facture.Statut.ANNULEE])
        .select_related('created_by', 'devis__lead')
        .prefetch_related('lignes')
    )
    fq = helpers.apply_date_range(fq, 'date_emission', debut, fin)

    par_resp = {}
    par_canal = {}
    par_mois = {}
    canal_labels = dict(Lead.Canal.choices)
    for f in fq:
        ht = Decimal(f.total_ht)
        # par responsable (created_by)
        who = (f.created_by.get_full_name() or f.created_by.username
               if f.created_by else 'Non attribué')
        par_resp[who] = par_resp.get(who, Decimal('0')) + ht
        # par canal (via le lead du devis)
        lead = getattr(f.devis, 'lead', None) if f.devis_id else None
        canal_key = lead.canal if (lead and lead.canal) else None
        canal_lbl = canal_labels.get(canal_key, 'Non précisé')
        par_canal[canal_lbl] = par_canal.get(canal_lbl, Decimal('0')) + ht
        # par mois
        cle = f.date_emission.strftime('%Y-%m')
        par_mois[cle] = par_mois.get(cle, Decimal('0')) + ht

    return (
        sorted(
            [{'nom': k, 'ca': helpers.f2(v)} for k, v in par_resp.items()],
            key=lambda x: x['ca'], reverse=True),
        sorted(
            [{'canal': k, 'ca': helpers.f2(v)} for k, v in par_canal.items()],
            key=lambda x: x['ca'], reverse=True),
        [{'mois': k, 'ca': helpers.f2(v)} for k in sorted(par_mois)
         for v in [par_mois[k]]],
    )


def _win_loss(leads_qs):
    perdus_qs = leads_qs.filter(perdu=True)
    par_motif = [
        {'motif': row['motif_perte'] or 'Non précisé', 'nb': row['nb']}
        for row in perdus_qs.values('motif_perte')
        .annotate(nb=Count('id')).order_by('-nb')
    ]
    return {
        'gagnes': leads_qs.filter(
            stage=SIGNED_STAGE, perdu=False).count(),
        'perdus': perdus_qs.count(),
        'par_motif': par_motif,
    }


# ── T13 — Hub de rapports : ventes / pipeline ────────────────────────────────

@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def sales_report(request):
    """Rapport ventes/pipeline : entonnoir leads, devis par statut & valeur,
    CA par responsable / canal / période, gagné-perdu par motif. Lecture seule.
    `?export=xlsx` exporte le rapport en classeur Excel."""
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    debut, fin, label = helpers.parse_periode(request)
    leads_qs = Lead.objects.filter(**co, is_archived=False)
    leads_qs = helpers.apply_date_range(
        leads_qs, 'date_creation__date', debut, fin)

    funnel = _sales_funnel(leads_qs)
    devis_status = _devis_status_value(co, debut, fin)
    par_resp, par_canal, par_mois = _sales_by(co, debut, fin)
    win_loss = _win_loss(leads_qs)

    if request.GET.get('export') == 'xlsx':
        return _sales_xlsx(label, funnel, devis_status, par_resp,
                           par_canal, par_mois, win_loss)

    return Response({
        'periode': label,
        'funnel': funnel,
        'devis_par_statut': devis_status,
        'ca_par_responsable': par_resp,
        'ca_par_canal': par_canal,
        'ca_par_mois': par_mois,
        'win_loss': win_loss,
    })


def _sales_xlsx(label, funnel, devis_status, par_resp, par_canal,
                par_mois, win_loss):
    wb = helpers.make_workbook()

    ws = wb.create_sheet('Entonnoir')
    ws.append(['Étape', 'Nombre de leads'])
    helpers.style_header(ws)
    for r in funnel:
        ws.append([r['label'], r['nb']])

    ws = wb.create_sheet('Devis par statut')
    ws.append(['Statut', 'Nombre', 'Valeur TTC (MAD)'])
    helpers.style_header(ws)
    for r in devis_status:
        ws.append([r['label'], r['nb'], r['valeur']])

    ws = wb.create_sheet('CA par responsable')
    ws.append(['Responsable', 'CA HT (MAD)'])
    helpers.style_header(ws)
    for r in par_resp:
        ws.append([r['nom'], r['ca']])

    ws = wb.create_sheet('CA par canal')
    ws.append(['Canal', 'CA HT (MAD)'])
    helpers.style_header(ws)
    for r in par_canal:
        ws.append([r['canal'], r['ca']])

    ws = wb.create_sheet('CA par mois')
    ws.append(['Mois', 'CA HT (MAD)'])
    helpers.style_header(ws)
    for r in par_mois:
        ws.append([r['mois'], r['ca']])

    ws = wb.create_sheet('Gagné-Perdu')
    ws.append(['Indicateur', 'Valeur'])
    helpers.style_header(ws)
    ws.append(['Gagnés (Signé)', win_loss['gagnes']])
    ws.append(['Perdus', win_loss['perdus']])
    ws.append([])
    ws.append(['Motif de perte', 'Nombre'])
    for r in win_loss['par_motif']:
        ws.append([r['motif'], r['nb']])

    return helpers.xlsx_response(wb, f'rapport_ventes_{label}.xlsx')


# ── T14 — Hub de rapports : stock (INTERNE, prix d'achat autorisé ici) ────────

@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def stock_report(request):
    """Rapport stock INTERNE : valorisation (valeur de vente ET valeur d'achat
    — interne uniquement), historique des mouvements, ruptures/sous-seuil, et
    répartition par catégorie / marque. `?export=xlsx` exporte le classeur."""
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    debut, fin, label = helpers.parse_periode(request)

    produits = list(
        Produit.objects.filter(**co, is_archived=False)
        .select_related('categorie')
    )

    valeur_vente = Decimal('0')
    valeur_achat = Decimal('0')
    par_categorie = {}
    par_marque = {}
    valorisation_rows = []
    for p in produits:
        qte = Decimal(p.quantite_stock or 0)
        pv = Decimal(p.prix_vente or 0)
        pa = Decimal(p.prix_achat or 0)
        vv = qte * pv
        va = qte * pa
        valeur_vente += vv
        valeur_achat += va
        cat = p.categorie.nom if p.categorie else 'Sans catégorie'
        marque = p.marque or 'Sans marque'
        c = par_categorie.setdefault(
            cat, {'categorie': cat, 'nb': 0, 'valeur_vente': Decimal('0'),
                  'valeur_achat': Decimal('0')})
        c['nb'] += 1
        c['valeur_vente'] += vv
        c['valeur_achat'] += va
        m = par_marque.setdefault(
            marque, {'marque': marque, 'nb': 0, 'valeur_vente': Decimal('0'),
                     'valeur_achat': Decimal('0')})
        m['nb'] += 1
        m['valeur_vente'] += vv
        m['valeur_achat'] += va
        valorisation_rows.append({
            'nom': p.nom,
            'sku': p.sku or '',
            'categorie': cat,
            'marque': marque,
            'quantite': p.quantite_stock or 0,
            'prix_achat': helpers.f2(pa),
            'prix_vente': helpers.f2(pv),
            'valeur_achat': helpers.f2(va),
            'valeur_vente': helpers.f2(vv),
            'marge_potentielle': helpers.f2(vv - va),
        })

    valorisation_rows.sort(key=lambda r: r['valeur_vente'], reverse=True)

    from django.db.models import F
    sous_seuil = list(
        Produit.objects.filter(**co, is_archived=False)
        .exclude(seuil_alerte=0)
        .filter(quantite_stock__lte=F('seuil_alerte'))
        .order_by('quantite_stock')
        .values('nom', 'sku', 'quantite_stock', 'seuil_alerte')
    )

    mvts_qs = (
        MouvementStock.objects.filter(**co)
        .select_related('produit', 'created_by')
        .order_by('-date')
    )
    mvts_qs = helpers.apply_date_range(mvts_qs, 'date__date', debut, fin)
    type_labels = dict(MouvementStock.TypeMouvement.choices)
    mouvements = [
        {
            'date': m.date.strftime('%Y-%m-%d %H:%M'),
            'produit': m.produit.nom,
            'type': type_labels.get(m.type_mouvement, m.type_mouvement),
            'quantite': m.quantite,
            'quantite_avant': m.quantite_avant,
            'quantite_apres': m.quantite_apres,
            'reference': m.reference or '',
            'par': (m.created_by.get_full_name() or m.created_by.username
                    if m.created_by else ''),
        }
        for m in mvts_qs[:1000]
    ]

    par_categorie_list = sorted(
        [{**c, 'valeur_vente': helpers.f2(c['valeur_vente']),
          'valeur_achat': helpers.f2(c['valeur_achat'])}
         for c in par_categorie.values()],
        key=lambda x: x['valeur_vente'], reverse=True)
    par_marque_list = sorted(
        [{**m, 'valeur_vente': helpers.f2(m['valeur_vente']),
          'valeur_achat': helpers.f2(m['valeur_achat'])}
         for m in par_marque.values()],
        key=lambda x: x['valeur_vente'], reverse=True)

    if request.GET.get('export') == 'xlsx':
        return _stock_xlsx(
            label, valeur_vente, valeur_achat, valorisation_rows,
            sous_seuil, mouvements, par_categorie_list, par_marque_list)

    return Response({
        'periode': label,
        'valorisation_totale': {
            'valeur_vente': helpers.f2(valeur_vente),
            'valeur_achat': helpers.f2(valeur_achat),
            'marge_potentielle': helpers.f2(valeur_vente - valeur_achat),
        },
        'valorisation': valorisation_rows,
        'sous_seuil': sous_seuil,
        'mouvements': mouvements,
        'par_categorie': par_categorie_list,
        'par_marque': par_marque_list,
    })


def _stock_xlsx(label, valeur_vente, valeur_achat, valorisation_rows,
                sous_seuil, mouvements, par_categorie, par_marque):
    wb = helpers.make_workbook()

    ws = wb.create_sheet('Valorisation')
    ws.append(['Produit', 'SKU', 'Catégorie', 'Marque', 'Quantité',
               "Prix d'achat", 'Prix vente', "Valeur d'achat",
               'Valeur vente', 'Marge potentielle'])
    helpers.style_header(ws)
    for r in valorisation_rows:
        ws.append([r['nom'], r['sku'], r['categorie'], r['marque'],
                   r['quantite'], r['prix_achat'], r['prix_vente'],
                   r['valeur_achat'], r['valeur_vente'],
                   r['marge_potentielle']])
    ws.append([])
    ws.append(['TOTAL', '', '', '', '', '', '',
               helpers.f2(valeur_achat), helpers.f2(valeur_vente),
               helpers.f2(valeur_vente - valeur_achat)])

    ws = wb.create_sheet('Sous seuil')
    ws.append(['Produit', 'SKU', 'Quantité', "Seuil d'alerte"])
    helpers.style_header(ws)
    for r in sous_seuil:
        ws.append([r['nom'], r['sku'] or '', r['quantite_stock'],
                   r['seuil_alerte']])

    ws = wb.create_sheet('Mouvements')
    ws.append(['Date', 'Produit', 'Type', 'Quantité', 'Avant', 'Après',
               'Référence', 'Par'])
    helpers.style_header(ws)
    for r in mouvements:
        ws.append([r['date'], r['produit'], r['type'], r['quantite'],
                   r['quantite_avant'], r['quantite_apres'],
                   r['reference'], r['par']])

    ws = wb.create_sheet('Par catégorie')
    ws.append(['Catégorie', 'Nb produits', "Valeur d'achat", 'Valeur vente'])
    helpers.style_header(ws)
    for r in par_categorie:
        ws.append([r['categorie'], r['nb'], r['valeur_achat'],
                   r['valeur_vente']])

    ws = wb.create_sheet('Par marque')
    ws.append(['Marque', 'Nb produits', "Valeur d'achat", 'Valeur vente'])
    helpers.style_header(ws)
    for r in par_marque:
        ws.append([r['marque'], r['nb'], r['valeur_achat'],
                   r['valeur_vente']])

    return helpers.xlsx_response(wb, f'rapport_stock_{label}.xlsx')


# ── T15 — Hub de rapports : service (chantiers + SAV) ─────────────────────────

@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def service_report(request):
    """Rapport service : charge de planning chantier + délais de réalisation,
    activité par technicien, SAV ouverts vs résolus + délai de résolution, et
    garanties d'équipements expirant bientôt. `?export=xlsx` exporte."""
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    debut, fin, label = helpers.parse_periode(request)

    # ── Chantiers ──
    inst_qs = (
        Installation.objects.filter(**co)
        .select_related('technicien_responsable')
    )
    inst_period = helpers.apply_date_range(
        inst_qs, 'date_creation__date', debut, fin)

    statut_labels = dict(Installation.Statut.choices)
    chantiers_par_statut_counts = dict(
        inst_period.values_list('statut')
        .annotate(nb=Count('id')).values_list('statut', 'nb'))
    chantiers_par_statut = [
        {'statut': s, 'label': statut_labels[s],
         'nb': chantiers_par_statut_counts.get(s, 0)}
        for s in Installation.STATUT_ORDER
    ]

    # Délai de réalisation (création → pose réelle), en jours.
    delais = []
    for inst in inst_period:
        if inst.date_pose_reelle:
            d0 = inst.date_creation.date()
            delais.append((inst.date_pose_reelle - d0).days)
    completion = {
        'nb_termines': len(delais),
        'delai_moyen_jours': round(sum(delais) / len(delais), 1) if delais else 0,
        'delai_min_jours': min(delais) if delais else 0,
        'delai_max_jours': max(delais) if delais else 0,
    }

    # Activité par technicien (chantiers attribués, hors annulés).
    tech_counts = {}
    for inst in inst_qs.filter(annule=False):
        t = inst.technicien_responsable
        nom = (t.get_full_name() or t.username) if t else 'Non attribué'
        b = tech_counts.setdefault(
            nom, {'technicien': nom, 'chantiers': 0, 'termines': 0})
        b['chantiers'] += 1
        if inst.statut == Installation.Statut.CLOTURE:
            b['termines'] += 1
    activite_techniciens = sorted(
        tech_counts.values(), key=lambda x: x['chantiers'], reverse=True)

    # ── SAV ──
    tickets_qs = Ticket.objects.filter(**co)
    tickets_period = helpers.apply_date_range(
        tickets_qs, 'date_creation__date', debut, fin)
    ouverts = tickets_qs.filter(
        statut__in=Ticket.OPEN_STATUTS, annule=False).count()
    resolus = tickets_qs.filter(
        statut__in=[Ticket.Statut.RESOLU, Ticket.Statut.CLOTURE]).count()

    res_delais = []
    for t in tickets_period:
        if t.date_ouverture and t.date_resolution:
            res_delais.append((t.date_resolution - t.date_ouverture).days)
    sav = {
        'ouverts': ouverts,
        'resolus': resolus,
        'total_periode': tickets_period.count(),
        'delai_resolution_moyen_jours':
            round(sum(res_delais) / len(res_delais), 1) if res_delais else 0,
        'nb_resolus_avec_delai': len(res_delais),
    }

    # ── Garanties expirant (90 jours par défaut) ──
    try:
        horizon = int(request.GET.get('jours_garantie', 90))
    except (TypeError, ValueError):
        horizon = 90
    today = date.today()
    limite = today + timedelta(days=horizon)
    garanties = [
        {
            'equipement': str(eq),
            'produit': eq.produit.nom,
            'numero_serie': eq.numero_serie or '',
            'client': str(eq.installation.client),
            'date_fin_garantie': eq.date_fin_garantie.isoformat(),
            'jours_restants': (eq.date_fin_garantie - today).days,
        }
        for eq in Equipement.objects.filter(**co)
        .filter(date_fin_garantie__isnull=False,
                date_fin_garantie__lte=limite,
                date_fin_garantie__gte=today)
        .select_related('produit', 'installation__client')
        .order_by('date_fin_garantie')
    ]

    if request.GET.get('export') == 'xlsx':
        return _service_xlsx(
            label, chantiers_par_statut, completion, activite_techniciens,
            sav, garanties, horizon)

    return Response({
        'periode': label,
        'chantiers_par_statut': chantiers_par_statut,
        'completion': completion,
        'activite_techniciens': activite_techniciens,
        'sav': sav,
        'garanties_expirant': garanties,
        'horizon_garantie_jours': horizon,
    })


def _service_xlsx(label, chantiers_par_statut, completion,
                  activite_techniciens, sav, garanties, horizon):
    wb = helpers.make_workbook()

    ws = wb.create_sheet('Chantiers par statut')
    ws.append(['Statut', 'Nombre'])
    helpers.style_header(ws)
    for r in chantiers_par_statut:
        ws.append([r['label'], r['nb']])
    ws.append([])
    ws.append(['Délai de réalisation', 'Jours'])
    ws.append(['Chantiers terminés', completion['nb_termines']])
    ws.append(['Délai moyen', completion['delai_moyen_jours']])
    ws.append(['Délai min', completion['delai_min_jours']])
    ws.append(['Délai max', completion['delai_max_jours']])

    ws = wb.create_sheet('Activité techniciens')
    ws.append(['Technicien', 'Chantiers', 'Clôturés'])
    helpers.style_header(ws)
    for r in activite_techniciens:
        ws.append([r['technicien'], r['chantiers'], r['termines']])

    ws = wb.create_sheet('SAV')
    ws.append(['Indicateur', 'Valeur'])
    helpers.style_header(ws)
    ws.append(['Tickets ouverts', sav['ouverts']])
    ws.append(['Tickets résolus', sav['resolus']])
    ws.append(['Tickets sur la période', sav['total_periode']])
    ws.append(['Délai résolution moyen (j)',
               sav['delai_resolution_moyen_jours']])

    ws = wb.create_sheet('Garanties expirant')
    ws.append([f'Équipement (≤ {horizon} j)', 'Produit', 'N° série',
               'Client', 'Fin garantie', 'Jours restants'])
    helpers.style_header(ws)
    for r in garanties:
        ws.append([r['equipement'], r['produit'], r['numero_serie'],
                   r['client'], r['date_fin_garantie'], r['jours_restants']])

    return helpers.xlsx_response(wb, f'rapport_service_{label}.xlsx')


# ── T12 — Export comptable : journal des ventes + TVA ─────────────────────────

@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def journal_ventes_xlsx(request):
    """Export comptable .xlsx : toutes les factures ÉMISES de la période avec
    la ventilation TVA par ligne, plus un récapitulatif TVA 10 % / 20 %
    réconcilié au centime et les totaux HT / TVA / TTC. Lecture seule."""
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    debut, fin, label = helpers.parse_periode(request)

    # Factures « émises » comptablement = tout sauf brouillon et annulée.
    factures = (
        Facture.objects.filter(**co)
        .exclude(statut__in=[Facture.Statut.BROUILLON,
                             Facture.Statut.ANNULEE])
        .select_related('client')
        .prefetch_related('lignes')
        .order_by('date_emission', 'reference')
    )
    factures = helpers.apply_date_range(factures, 'date_emission', debut, fin)

    wb = helpers.make_workbook()

    # ── Feuille 1 : Journal des ventes (une ligne par ligne de facture) ──
    ws = wb.create_sheet('Journal des ventes')
    ws.append(['Date', 'Facture', 'Client', 'Désignation', 'Quantité',
               'P.U. HT', 'Remise %', 'Total HT', 'Taux TVA',
               'Montant TVA', 'Total TTC'])
    helpers.style_header(ws)

    total_ht_global = Decimal('0')
    total_tva_global = Decimal('0')
    total_ttc_global = Decimal('0')
    # Récap TVA par taux, réconcilié au centime via les propriétés modèle.
    recap = {}

    for f in factures:
        ht, tva, ttc = helpers.facture_totaux(f)
        total_ht_global += ht
        total_tva_global += tva
        total_ttc_global += ttc

        # Ventilation TVA réconciliée au centime (propriété modèle).
        for bucket in f.tva_par_taux:
            taux = Decimal(bucket['taux'])
            r = recap.setdefault(
                taux, {'base_ht': Decimal('0'), 'montant': Decimal('0')})
            r['base_ht'] += Decimal(bucket['base_ht'])
            r['montant'] += Decimal(bucket['montant'])

        lignes = list(f.lignes.all())
        if lignes:
            for ligne in lignes:
                lht = Decimal(ligne.total_ht)
                taux = Decimal(ligne.taux_tva_effectif)
                lmtva = helpers.q2(lht * taux / Decimal('100'))
                ws.append([
                    f.date_emission.isoformat(),
                    f.reference,
                    str(f.client),
                    ligne.designation,
                    float(ligne.quantite),
                    float(ligne.prix_unitaire),
                    float(ligne.remise),
                    helpers.f2(lht),
                    float(taux),
                    helpers.f2(lmtva),
                    helpers.f2(lht + lmtva),
                ])
        else:
            # Facture de tranche sans lignes (acompte/solde) : une ligne synthèse.
            ws.append([
                f.date_emission.isoformat(),
                f.reference,
                str(f.client),
                f.libelle or 'Tranche de facturation',
                1,
                helpers.f2(ht),
                0,
                helpers.f2(ht),
                float(f.taux_tva),
                helpers.f2(tva),
                helpers.f2(ttc),
            ])

    ws.append([])
    ws.append(['', '', '', '', '', '', 'TOTAL',
               helpers.f2(total_ht_global), '',
               helpers.f2(total_tva_global),
               helpers.f2(total_ttc_global)])

    # ── Feuille 2 : Récapitulatif TVA ──
    ws2 = wb.create_sheet('Récapitulatif TVA')
    ws2.append(['Taux TVA', 'Base HT', 'Montant TVA'])
    helpers.style_header(ws2)
    recap_base_total = Decimal('0')
    recap_tva_total = Decimal('0')
    for taux in sorted(recap):
        base = helpers.q2(recap[taux]['base_ht'])
        montant = helpers.q2(recap[taux]['montant'])
        recap_base_total += base
        recap_tva_total += montant
        ws2.append([f'{float(taux):g} %', helpers.f2(base),
                    helpers.f2(montant)])
    ws2.append([])
    ws2.append(['TOTAL', helpers.f2(recap_base_total),
                helpers.f2(recap_tva_total)])
    ws2.append([])
    ws2.append(['Total HT', helpers.f2(total_ht_global)])
    ws2.append(['Total TVA', helpers.f2(total_tva_global)])
    ws2.append(['Total TTC', helpers.f2(total_ttc_global)])
    ws2.append(['Période', label])

    return helpers.xlsx_response(wb, f'journal_ventes_{label}.xlsx')
