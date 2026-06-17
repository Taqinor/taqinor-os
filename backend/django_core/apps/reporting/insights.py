"""N49/N70/N95/N78/N80 — Insights (lecture seule, multi-tenant, ADDITIF).

Quatre endpoints GET d'agrégation pure sur la donnée EXISTANTE — aucune
migration, aucun nouveau champ modèle.

  * N49  recurring-revenue : valeur récurrente des contrats de maintenance.
  * N70+N95 audit-log      : flux d'activité unifié (qui a fait quoi + audit).
  * N78  job-costing       : marge par chantier (ADMIN ; prix d'achat INTERNE,
                             jamais dans un export client).
  * N80  analytics         : délais lead→signature→mise en service, kWc/mois.

Le prix d'achat (`Produit.prix_achat`) n'apparaît QUE dans le JSON admin de
job-costing — jamais dans un export xlsx, jamais côté client (précédent :
`stock_report.valorisation_achat`).
"""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminRole, IsResponsableOrAdmin
from apps.crm.exports import build_xlsx_response


def _co(user):
    """Filtre société (kwargs) ou None pour un utilisateur sans accès.

    Même patron exact que `apps/reporting/reports.py`.
    """
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


def _maybe_xlsx(request, filename, headers, rows, title):
    """Renvoie une réponse .xlsx si ?export=xlsx, sinon None."""
    if request.query_params.get('export') == 'xlsx':
        return build_xlsx_response(filename, headers, rows, sheet_title=title)
    return None


# Facteur mensuel-équivalent par périodicité de contrat. On lit la table
# `MONTHS` du modèle (mois entre deux visites) et on convertit en part de mois.
def _monthly_factor(periodicite):
    """Part d'un mois représentée par une visite (1/n mois entre visites)."""
    from apps.sav.models import ContratMaintenance
    months = ContratMaintenance.MONTHS.get(periodicite, 12)
    if not months:
        return Decimal('0')
    return Decimal('1') / Decimal(months)


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def recurring_revenue(request):
    """N49 — revenu récurrent des contrats de maintenance actifs.

    Total mensuel-équivalent et annuel-équivalent, contrats à renouveler /
    prochaine visite sous ~90 jours, et nombre de contrats inactifs (lapsed).
    """
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    from apps.sav.models import ContratMaintenance

    actifs = (ContratMaintenance.objects
              .filter(**co, actif=True)
              .select_related('client', 'installation'))
    inactifs = ContratMaintenance.objects.filter(**co, actif=False).count()

    monthly_total = Decimal('0')
    annual_total = Decimal('0')
    upcoming = []
    contracts = []
    today = date.today()
    horizon = today + timedelta(days=90)

    periodicite_labels = dict(ContratMaintenance.Periodicite.choices)

    for c in actifs:
        prix = c.prix or Decimal('0')
        factor = _monthly_factor(c.periodicite)
        monthly = prix * factor
        monthly_total += monthly
        annual_total += monthly * Decimal('12')
        prochaine = c.prochaine_visite()
        client_nom = str(c.client) if c.client_id else '—'
        row = {
            'id': c.pk,
            'client': client_nom,
            'periodicite': c.periodicite,
            'periodicite_label': periodicite_labels.get(
                c.periodicite, c.periodicite),
            'prix': str(prix),
            'prochaine_visite': prochaine.isoformat() if prochaine else None,
            'monthly_equivalent': str(monthly),
        }
        contracts.append(row)
        if prochaine and today <= prochaine <= horizon:
            upcoming.append(row)

    upcoming.sort(key=lambda r: r['prochaine_visite'] or '')

    rows = [[c['client'], c['periodicite_label'], c['prix'],
             c['prochaine_visite'] or '', c['monthly_equivalent']]
            for c in contracts]
    x = _maybe_xlsx(
        request, 'revenu-recurrent.xlsx',
        ['Client', 'Périodicité', 'Prix', 'Prochaine visite', 'Mensuel équiv.'],
        rows, 'Revenu récurrent')
    if x:
        return x

    return Response({
        'monthly_total': str(monthly_total),
        'annual_total': str(annual_total),
        'active_count': len(contracts),
        'lapsed_count': inactifs,
        'upcoming_count': len(upcoming),
        'upcoming': upcoming,
        'contracts': contracts,
    })


# ── N70 + N95 — flux d'audit/activité unifié ──
# Libellés FR par type d'objet + clé de filtre ?type=.
_TYPE_LABELS = {
    'lead': 'Lead',
    'devis': 'Devis',
    'chantier': 'Chantier',
    'sav': 'Ticket SAV',
    'parametres': 'Paramètres',
}


def _activity_summary(act):
    """Résumé lisible d'une entrée de chatter (LeadActivity & co.)."""
    kind = getattr(act, 'kind', '')
    if kind == 'note':
        return (act.body or 'Note').strip()
    if kind == 'creation':
        return 'Création'
    label = act.field_label or act.field or 'champ'
    old = act.old_value or '∅'
    new = act.new_value or '∅'
    return f'{label} : {old} → {new}'


def _username(user):
    return getattr(user, 'username', '') if user else ''


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def audit_log(request):
    """N70 + N95 — journal d'activité unifié, company-scopé, trié par date.

    Fusionne LeadActivity, DevisActivity, InstallationActivity, TicketActivity
    et SettingsAuditLog. Filtres : ?user=<id|username>, ?type=<lead|devis|
    chantier|sav|parametres>, ?since=YYYY-MM-DD. Limite par défaut 200.
    """
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    from apps.crm.models import LeadActivity
    from apps.ventes.models import DevisActivity
    from apps.installations.models import InstallationActivity
    from apps.sav.models import TicketActivity
    from apps.parametres.models import SettingsAuditLog

    type_filter = request.query_params.get('type')
    user_filter = request.query_params.get('user')
    since_raw = request.query_params.get('since')
    since = None
    if since_raw:
        try:
            since = datetime.strptime(since_raw, '%Y-%m-%d').date()
        except ValueError:
            since = None
    try:
        limit = int(request.query_params.get('limit', 200))
    except (TypeError, ValueError):
        limit = 200
    limit = max(1, min(limit, 1000))

    def _user_match(user_obj):
        """Filtre utilisateur tolérant : id numérique OU username."""
        if not user_filter:
            return True
        if user_obj is None:
            return False
        if str(user_obj.pk) == str(user_filter):
            return True
        return getattr(user_obj, 'username', None) == user_filter

    items = []

    def act_date(act):
        # Le chatter porte created_at ; SettingsAuditLog porte timestamp.
        return getattr(act, 'created_at', None) or getattr(act, 'timestamp')

    # Chacune des sources : (clé type, queryset, accès objet→ref).
    def _collect(type_key, qs, ref_fn):
        if type_filter and type_filter != type_key:
            return
        for act in qs:
            if since and act_date(act).date() < since:
                continue
            user_obj = getattr(act, 'user', None)
            if not _user_match(user_obj):
                continue
            items.append({
                'date': act_date(act).isoformat(),
                'user': _username(user_obj),
                'type': type_key,
                'type_label': _TYPE_LABELS[type_key],
                'object_ref': ref_fn(act),
                'summary': _activity_summary(act),
            })

    # Pour limiter le coût, on borne chaque source à `limit` entrées récentes.
    _collect('lead',
             LeadActivity.objects.filter(**co)
             .select_related('user', 'lead')[:limit],
             lambda a: str(a.lead) if a.lead_id else '—')
    _collect('devis',
             DevisActivity.objects.filter(**co)
             .select_related('user', 'devis')[:limit],
             lambda a: a.devis.reference if a.devis_id else '—')
    _collect('chantier',
             InstallationActivity.objects.filter(**co)
             .select_related('user', 'installation')[:limit],
             lambda a: a.installation.reference if a.installation_id else '—')
    _collect('sav',
             TicketActivity.objects.filter(**co)
             .select_related('user', 'ticket')[:limit],
             lambda a: a.ticket.reference if a.ticket_id else '—')

    # SettingsAuditLog : pas de kind/field_label identiques, on adapte le résumé.
    if not type_filter or type_filter == 'parametres':
        for log in (SettingsAuditLog.objects.filter(**co)
                    .select_related('user')[:limit]):
            if since and log.timestamp.date() < since:
                continue
            if not _user_match(log.user):
                continue
            label = log.field_label or log.field or log.section
            summary = (f'{label} : {log.old_value or "∅"} → '
                       f'{log.new_value or "∅"}')
            items.append({
                'date': log.timestamp.isoformat(),
                'user': _username(log.user),
                'type': 'parametres',
                'type_label': _TYPE_LABELS['parametres'],
                'object_ref': log.section,
                'summary': summary,
            })

    items.sort(key=lambda it: it['date'], reverse=True)
    items = items[:limit]

    rows = [[it['date'], it['user'], it['type_label'], it['object_ref'],
             it['summary']] for it in items]
    x = _maybe_xlsx(
        request, 'journal-activite.xlsx',
        ['Date', 'Utilisateur', 'Type', 'Référence', 'Action'],
        rows, 'Journal')
    if x:
        return x

    return Response({'count': len(items), 'items': items})


# ── N78 — coût de revient par chantier (ADMIN ; marge INTERNE) ───────────────
def _devis_cost_estimate(devis):
    """Coût estimé d'un devis = Σ prix_achat × quantité de ses lignes.

    Le prix d'achat est lu sur le produit lié à chaque ligne. INTERNE.
    """
    total = Decimal('0')
    for ligne in devis.lignes.all():
        produit = ligne.produit
        prix_achat = getattr(produit, 'prix_achat', None) or Decimal('0')
        qte = ligne.quantite or Decimal('0')
        total += Decimal(prix_achat) * Decimal(qte)
    return total


@api_view(['GET'])
@permission_classes([IsAdminRole])
def job_costing(request):
    """N78 — coût de revient & marge par chantier (ADMIN UNIQUEMENT).

    Facturé HT (Σ total HT des factures liées au chantier via son devis) vs
    coût estimé (Σ prix_achat × quantité des lignes du devis lié). Marge et %
    de marge par chantier + récap mensuel.

    HYPOTHÈSE DE LIAISON : on privilégie le chemin devis→chantier (le chantier
    porte un FK `devis`). Les factures sont rattachées par leur FK `devis` au
    MÊME devis que le chantier. C'est le lien fiable et documenté ici ; la
    facturation directe chantier↔facture n'existe pas dans le modèle.
    """
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    from apps.installations.models import Installation
    from apps.ventes.models import Facture

    chantiers = (Installation.objects
                 .filter(**co)
                 .select_related('client', 'devis')
                 .prefetch_related('devis__lignes__produit'))

    # Factures non annulées, indexées par devis_id (chemin devis→chantier).
    factures = (Facture.objects.filter(**co)
                .exclude(statut=Facture.Statut.ANNULEE)
                .exclude(devis__isnull=True)
                .prefetch_related('lignes'))
    invoiced_by_devis = defaultdict(Decimal)
    for f in factures:
        invoiced_by_devis[f.devis_id] += Decimal(f.total_ht)

    rows = []
    monthly = defaultdict(lambda: {'invoiced': Decimal('0'),
                                   'cost': Decimal('0')})
    total_invoiced = Decimal('0')
    total_cost = Decimal('0')

    for ch in chantiers:
        invoiced = (invoiced_by_devis.get(ch.devis_id, Decimal('0'))
                    if ch.devis_id else Decimal('0'))
        cost = _devis_cost_estimate(ch.devis) if ch.devis_id else Decimal('0')
        margin = invoiced - cost
        margin_pct = (float(margin / invoiced * 100)
                      if invoiced else 0.0)
        total_invoiced += invoiced
        total_cost += cost
        # Mois de rattachement : réception/clôture/signature/création.
        ref_date = (ch.date_reception or ch.date_cloture
                    or ch.date_signature
                    or (ch.date_creation.date() if ch.date_creation else None))
        if ref_date:
            key = ref_date.strftime('%Y-%m')
            monthly[key]['invoiced'] += invoiced
            monthly[key]['cost'] += cost
        rows.append({
            'ref': ch.reference,
            'client': str(ch.client) if ch.client_id else '—',
            'invoiced_ht': str(invoiced),
            'cost_estimate': str(cost),   # INTERNE
            'margin': str(margin),        # INTERNE
            'margin_pct': round(margin_pct, 1),  # INTERNE
        })

    margin_by_month = [
        {
            'mois': k,
            'invoiced': str(v['invoiced']),
            'cost': str(v['cost']),
            'margin': str(v['invoiced'] - v['cost']),
        }
        for k, v in sorted(monthly.items())
    ]

    total_margin = total_invoiced - total_cost

    # Export interne (clairement marqué interne) — toléré pour l'admin, mais
    # JAMAIS un export client. On garde le prix d'achat hors de ce fichier en
    # n'exportant que les colonnes facturé/coût/marge agrégées par chantier.
    rows_xlsx = [[r['ref'], r['client'], r['invoiced_ht'],
                  r['cost_estimate'], r['margin'], r['margin_pct']]
                 for r in rows]
    x = _maybe_xlsx(
        request, 'cout-revient-INTERNE.xlsx',
        ['Réf chantier', 'Client', 'Facturé HT', 'Coût estimé (interne)',
         'Marge (interne)', 'Marge %'],
        rows_xlsx, 'Coût de revient (interne)')
    if x:
        return x

    return Response({
        'internal': True,
        'total_invoiced_ht': str(total_invoiced),
        'total_cost_estimate': str(total_cost),
        'total_margin': str(total_margin),
        'chantiers': rows,
        'margin_by_month': margin_by_month,
    })


# ── N80 — analytics métier ──
def _days_between(d1, d2):
    """Jours entre deux dates (None si l'une manque)."""
    if not d1 or not d2:
        return None
    return (d2 - d1).days


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def analytics(request):
    """N80 — analytics lecture seule.

    - délai moyen lead→signature (Lead.date_creation → date d'acceptation du
      devis accepté lié au lead) ;
    - délai moyen signature→mise en service (date d'acceptation → chantier
      réceptionné/clôturé) ;
    - kWc installés par mois (somme de Installation.puissance_installee_kwc).
    """
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    from apps.ventes.models import Devis
    from apps.installations.models import Installation

    # ── lead → signature : devis acceptés portant un lead ──
    devis_acceptes = (Devis.objects
                      .filter(**co, statut=Devis.Statut.ACCEPTE)
                      .exclude(lead__isnull=True)
                      .select_related('lead'))
    lead_to_sign_days = []
    for d in devis_acceptes:
        signed = d.date_acceptation
        created = d.lead.date_creation.date() if (
            d.lead_id and d.lead.date_creation) else None
        days = _days_between(created, signed)
        if days is not None and days >= 0:
            lead_to_sign_days.append(days)

    # ── signature → mise en service : chantiers réceptionnés/clôturés issus
    #    d'un devis accepté (date d'acceptation → date de réception/clôture) ──
    chantiers = (Installation.objects
                 .filter(**co)
                 .select_related('devis'))
    sign_to_commission_days = []
    kwc_par_mois = defaultdict(Decimal)
    for ch in chantiers:
        commission = ch.date_reception or ch.date_cloture
        sign = ch.date_signature
        if sign is None and ch.devis_id and ch.devis:
            sign = ch.devis.date_acceptation
        days = _days_between(sign, commission)
        if days is not None and days >= 0:
            sign_to_commission_days.append(days)
        # kWc installés par mois : on impute à la date de réception (sinon
        # clôture, sinon signature) — un système est « installé » à sa pose.
        kwc = ch.puissance_installee_kwc
        if kwc:
            ref_date = (ch.date_reception or ch.date_cloture
                        or ch.date_signature)
            if ref_date:
                kwc_par_mois[ref_date.strftime('%Y-%m')] += Decimal(kwc)

    def _avg(xs):
        return round(sum(xs) / len(xs), 1) if xs else None

    kwc_series = [
        {'mois': k, 'kwc': str(v)}
        for k, v in sorted(kwc_par_mois.items())
    ]

    rows = [[s['mois'], s['kwc']] for s in kwc_series]
    x = _maybe_xlsx(
        request, 'analytics-kwc.xlsx',
        ['Mois', 'kWc installés'], rows, 'kWc / mois')
    if x:
        return x

    return Response({
        'avg_days_lead_to_signature': _avg(lead_to_sign_days),
        'lead_to_signature_count': len(lead_to_sign_days),
        'avg_days_signature_to_commissioning': _avg(sign_to_commission_days),
        'signature_to_commissioning_count': len(sign_to_commission_days),
        'kwc_by_month': kwc_series,
    })
