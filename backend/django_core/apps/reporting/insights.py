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

from django.db.models import Count
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


def _qdate(value):
    """Parse une date ?from=/?to= au format ISO, ou None."""
    try:
        return date.fromisoformat((value or '').strip())
    except (ValueError, TypeError):
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

# N83 — clé de route front par type, pour les liens profonds object_ref. Le
# frontend mappe `object_type` + `object_id` vers la fiche concernée.
_TYPE_ROUTE = {
    'lead': 'lead',
    'devis': 'devis',
    'chantier': 'chantier',
    'sav': 'ticket',
}


def _field_change(label, old_value, new_value):
    """N83 — format UNIQUE « champ : ancien → nouveau », identique pour le
    chatter (LeadActivity & co.) ET SettingsAuditLog. Source de vérité unique
    du rendu d'un changement de champ dans le Journal."""
    label = label or 'champ'
    old = old_value if old_value not in (None, '') else '∅'
    new = new_value if new_value not in (None, '') else '∅'
    return f'{label} : {old} → {new}'


def _activity_summary(act):
    """Résumé lisible d'une entrée de chatter (LeadActivity & co.)."""
    kind = getattr(act, 'kind', '')
    if kind == 'note':
        return (act.body or 'Note').strip()
    if kind == 'creation':
        return 'Création'
    return _field_change(
        act.field_label or act.field, act.old_value, act.new_value)


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

    # Chacune des sources : (clé type, queryset, accès objet→ref, accès→id).
    # N83 — `ref_fn` donne le libellé affiché, `id_fn` la PK de l'objet lié pour
    # le lien profond du Journal (object_type + object_id côté front).
    def _collect(type_key, qs, ref_fn, id_fn):
        if type_filter and type_filter != type_key:
            return
        for act in qs:
            if since and act_date(act).date() < since:
                continue
            user_obj = getattr(act, 'user', None)
            if not _user_match(user_obj):
                continue
            obj_id = id_fn(act)
            items.append({
                'date': act_date(act).isoformat(),
                'user': _username(user_obj),
                'type': type_key,
                'type_label': _TYPE_LABELS[type_key],
                'object_ref': ref_fn(act),
                # Lien profond : type de route + id (None = pas de cible).
                'object_type': _TYPE_ROUTE.get(type_key),
                'object_id': obj_id,
                'summary': _activity_summary(act),
            })

    # Pour limiter le coût, on borne chaque source à `limit` entrées récentes.
    _collect('lead',
             LeadActivity.objects.filter(**co)
             .select_related('user', 'lead')[:limit],
             lambda a: str(a.lead) if a.lead_id else '—',
             lambda a: a.lead_id)
    _collect('devis',
             DevisActivity.objects.filter(**co)
             .select_related('user', 'devis')[:limit],
             lambda a: a.devis.reference if a.devis_id else '—',
             lambda a: a.devis_id)
    _collect('chantier',
             InstallationActivity.objects.filter(**co)
             .select_related('user', 'installation')[:limit],
             lambda a: a.installation.reference if a.installation_id else '—',
             lambda a: a.installation_id)
    _collect('sav',
             TicketActivity.objects.filter(**co)
             .select_related('user', 'ticket')[:limit],
             lambda a: a.ticket.reference if a.ticket_id else '—',
             lambda a: a.ticket_id)

    # SettingsAuditLog : même format de changement que le chatter (L16) via le
    # helper unique `_field_change`. Pas de cible profonde (réglage de société).
    if not type_filter or type_filter == 'parametres':
        for log in (SettingsAuditLog.objects.filter(**co)
                    .select_related('user')[:limit]):
            if since and log.timestamp.date() < since:
                continue
            if not _user_match(log.user):
                continue
            summary = _field_change(
                log.field_label or log.field or log.section,
                log.old_value, log.new_value)
            items.append({
                'date': log.timestamp.isoformat(),
                'user': _username(log.user),
                'type': 'parametres',
                'type_label': _TYPE_LABELS['parametres'],
                'object_ref': log.section,
                'object_type': None,
                'object_id': None,
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
        ['Mois', 'kWc installés'], rows, 'kWc par mois')
    if x:
        return x

    return Response({
        'avg_days_lead_to_signature': _avg(lead_to_sign_days),
        'lead_to_signature_count': len(lead_to_sign_days),
        'avg_days_signature_to_commissioning': _avg(sign_to_commission_days),
        'signature_to_commissioning_count': len(sign_to_commission_days),
        'kwc_by_month': kwc_series,
    })


@api_view(['GET'])
@permission_classes([IsAdminRole])
def commissions(request):
    """N99 — commissions commerciales (ADMIN UNIQUEMENT, donnée sensible).

    Configurable dans Paramètres (mode + valeur) : 'pct_devis' (% du HT des
    devis signés) ou 'par_kwc' (MAD par kWc installé des chantiers issus des
    devis signés). Désactivé par défaut (mode 'off') → aucune commission. Le
    commercial = le responsable du lead du devis, sinon son créateur. Période
    optionnelle sur la date d'acceptation : ?from=&to=.
    """
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    from apps.parametres.models import CompanyProfile
    from apps.ventes.models import Devis
    from apps.installations.models import Installation

    profile = CompanyProfile.get(getattr(request.user, 'company', None))
    mode = getattr(profile, 'commission_mode', 'off') or 'off'
    valeur = profile.commission_valeur
    if mode not in ('pct_devis', 'par_kwc') or valeur is None:
        return Response({
            'enabled': False, 'mode': mode,
            'valeur': str(valeur) if valeur is not None else None,
            'rows': [], 'total': '0',
        })
    valeur = Decimal(valeur)

    signed = (Devis.objects.filter(**co, statut=Devis.Statut.ACCEPTE)
              .select_related('lead', 'lead__owner', 'created_by')
              .prefetch_related('lignes'))
    start = _qdate(request.query_params.get('from'))
    end = _qdate(request.query_params.get('to'))
    if start:
        signed = signed.filter(date_acceptation__gte=start)
    if end:
        signed = signed.filter(date_acceptation__lte=end)

    # kWc installé par devis (chemin devis→chantier), si mode par_kwc.
    kwc_by_devis = defaultdict(Decimal)
    if mode == 'par_kwc':
        insts = (Installation.objects.filter(**co)
                 .exclude(devis__isnull=True)
                 .values_list('devis_id', 'puissance_installee_kwc'))
        for devis_id, kwc in insts:
            if kwc:
                kwc_by_devis[devis_id] += Decimal(kwc)

    agg = {}
    for d in signed:
        if d.lead_id and d.lead and d.lead.owner_id:
            owner = d.lead.owner
        else:
            owner = d.created_by
        uid = owner.id if owner else 0
        slot = agg.setdefault(uid, {
            'commercial': _username(owner) or '—', 'base': Decimal('0'),
            'commission': Decimal('0'), 'count': 0})
        slot['count'] += 1
        if mode == 'pct_devis':
            base = Decimal(d.total_ht)
            slot['base'] += base
            slot['commission'] += base * valeur / Decimal('100')
        else:
            kwc = kwc_by_devis.get(d.id, Decimal('0'))
            slot['base'] += kwc
            slot['commission'] += kwc * valeur

    rows = sorted(agg.values(),
                  key=lambda r: r['commission'], reverse=True)
    out = [{
        'commercial': r['commercial'], 'count': r['count'],
        'base': str(r['base']), 'commission': str(r['commission']),
    } for r in rows]
    total = sum((r['commission'] for r in rows), Decimal('0'))
    base_label = 'HT signé' if mode == 'pct_devis' else 'kWc installé'

    x = _maybe_xlsx(
        request, 'commissions.xlsx',
        ['Commercial', 'Devis signés', base_label, 'Commission'],
        [[r['commercial'], r['count'], r['base'], r['commission']]
         for r in out],
        'Commissions')
    if x:
        return x

    return Response({
        'enabled': True, 'mode': mode, 'valeur': str(valeur),
        'base_label': base_label, 'rows': out, 'total': str(total),
    })


# ── FG93 — Classement commerciaux ───────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def sales_leaderboard(request):
    """FG93 — Classement commerciaux (CA signé, taux de victoire, deal moyen,
    kWc par responsable).

    Responsable = owner du lead associé au devis, sinon created_by. Commission
    et prix d'achat EXCLUS — indicateurs purement commerciaux. Période
    optionnelle ?from=&to= sur la date d'acceptation du devis.
    """
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    from apps.ventes.models import Devis
    from apps.crm.models import Lead
    from apps.installations.models import Installation
    from decimal import Decimal

    # Devis signés (statut=accepte) bornés à la société.
    signed = (Devis.objects.filter(**co, statut=Devis.Statut.ACCEPTE)
              .select_related('lead', 'lead__owner', 'created_by'))
    start = _qdate(request.query_params.get('from'))
    end = _qdate(request.query_params.get('to'))
    if start:
        signed = signed.filter(date_acceptation__gte=start)
    if end:
        signed = signed.filter(date_acceptation__lte=end)

    # kWc installé par devis (chemin devis→chantier).
    kwc_by_devis = defaultdict(Decimal)
    insts = (Installation.objects.filter(**co)
             .exclude(devis__isnull=True)
             .values_list('devis_id', 'puissance_installee_kwc'))
    for devis_id, kwc in insts:
        if kwc:
            kwc_by_devis[devis_id] += Decimal(kwc)

    # Tous les leads de la société pour calculer le nb total par responsable.
    leads_qs = Lead.objects.filter(**co, is_archived=False)
    if start:
        leads_qs = leads_qs.filter(date_creation__gte=start)
    if end:
        leads_qs = leads_qs.filter(date_creation__lte=end)
    leads_by_owner = defaultdict(int)
    for row in leads_qs.values('owner_id').annotate(n=Count('id')):
        leads_by_owner[row['owner_id']] = row['n']

    agg = {}
    for d in signed:
        if d.lead_id and d.lead and d.lead.owner_id:
            owner = d.lead.owner
        else:
            owner = d.created_by
        uid = owner.id if owner else 0
        slot = agg.setdefault(uid, {
            'commercial': _username(owner) or '—',
            'ca_ht': Decimal('0'),
            'nb_devis': 0,
            'kwc': Decimal('0'),
        })
        # QX2 — CA sur le HT REMISÉ de l'option acceptée (chaîne canonique
        # QX1), jamais le HT brut (revenu réel signé, non gonflé).
        from apps.ventes.utils.options import option_totaux
        slot['ca_ht'] += Decimal(str(option_totaux(d)['ht']))
        slot['nb_devis'] += 1
        slot['kwc'] += kwc_by_devis.get(d.id, Decimal('0'))

    rows = []
    for uid, slot in agg.items():
        total_leads = leads_by_owner.get(uid, 0)
        win_rate = round(slot['nb_devis'] / total_leads * 100, 1) if total_leads else None
        avg_deal = round(float(slot['ca_ht']) / slot['nb_devis'], 2) if slot['nb_devis'] else 0
        rows.append({
            'commercial': slot['commercial'],
            'ca_ht': str(slot['ca_ht']),
            'nb_devis_signes': slot['nb_devis'],
            'avg_deal_ht': str(avg_deal),
            'kwc': str(slot['kwc']),
            'win_rate_pct': win_rate,
        })

    rows.sort(key=lambda r: float(r['ca_ht']), reverse=True)

    x = _maybe_xlsx(
        request, 'classement-commerciaux.xlsx',
        ['Commercial', 'CA HT signé', 'Devis signés', 'Deal moyen HT', 'kWc', 'Taux victoire %'],
        [[r['commercial'], r['ca_ht'], r['nb_devis_signes'],
          r['avg_deal_ht'], r['kwc'], r['win_rate_pct'] or '—']
         for r in rows],
        'Classement commerciaux')
    if x:
        return x

    return Response({'rows': rows, 'total_commerciaux': len(rows)})


# ── FG94 — Reporting des champs personnalisés ─────────────────────────────────
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def cf_group_by(request):
    """FG94 — Agrégation (group-by) sur un champ personnalisé.

    Paramètres :
      ?module=lead|client|produit|devis|installation|ticket
      ?code=<code_du_champ>
    Renvoie le compte d'enregistrements par valeur du champ personnalisé
    (depuis custom_data[code]), borné à la société. Seuls les champs avec
    `visible_liste=True` sont aggregables (dead flag activé). Les valeurs
    manquantes ou vides sont regroupées sous '(vide)'.
    """
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    module = request.query_params.get('module', '').strip()
    code = request.query_params.get('code', '').strip()

    if not module or not code:
        return Response(
            {'detail': 'Paramètres requis : ?module=<module>&code=<code>'},
            status=400)

    # Vérifier que le champ est bien visible_liste pour ce module.
    from apps.customfields.models import CustomFieldDef
    try:
        cf_def = CustomFieldDef.objects.get(
            company=request.user.company, module=module, code=code,
            actif=True, visible_liste=True)
    except CustomFieldDef.DoesNotExist:
        # Superuser sans company ou champ non visible_liste.
        if request.user.is_superuser:
            try:
                cf_def = CustomFieldDef.objects.get(
                    module=module, code=code, actif=True, visible_liste=True)
            except CustomFieldDef.DoesNotExist:
                return Response(
                    {'detail': 'Champ non trouvé ou non visible dans les listes.'},
                    status=404)
        else:
            return Response(
                {'detail': 'Champ non trouvé ou non visible dans les listes.'},
                status=404)

    # Résoudre le modèle cible.
    model = _cf_module_model(module)
    if model is None:
        return Response({'detail': f'Module {module!r} non supporté.'}, status=400)

    qs = model.objects.filter(**co)
    buckets = defaultdict(int)
    for row in qs.values_list('custom_data', flat=True).iterator():
        val = (row or {}).get(code)
        key = str(val).strip() if val not in (None, '') else '(vide)'
        buckets[key] += 1

    rows = sorted(
        [{'valeur': k, 'count': v} for k, v in buckets.items()],
        key=lambda r: -r['count'])

    x = _maybe_xlsx(
        request, f'cf-{module}-{code}.xlsx',
        [cf_def.libelle, 'Nombre'],
        [[r['valeur'], r['count']] for r in rows],
        f'{cf_def.libelle} par valeur')
    if x:
        return x

    return Response({
        'module': module, 'code': code, 'libelle': cf_def.libelle,
        'rows': rows, 'total': sum(r['count'] for r in rows),
    })


def _cf_module_model(module):
    """Résout un module CustomField vers le modèle Django porteur de custom_data."""
    if module == 'lead':
        from apps.crm.models import Lead
        return Lead
    if module == 'client':
        from apps.crm.models import Client
        return Client
    if module == 'produit':
        from apps.stock.models import Produit
        return Produit
    if module == 'devis':
        from apps.ventes.models import Devis
        return Devis
    if module == 'installation':
        from apps.installations.models import Installation
        return Installation
    if module == 'ticket':
        from apps.sav.models import Ticket
        return Ticket
    return None


# ── FG98 — Analyse cohortes / saisonnalité ────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def cohorts(request):
    """FG98 — Cohortes de leads par mois d'acquisition.

    Paramètres optionnels :
      ?from=YYYY-MM-DD  &to=YYYY-MM-DD  — fenêtre (défaut : 12 mois)
      ?group_by=canal   — dimension de regroupement secondaire (défaut : aucune)

    Retourne pour chaque mois d'acquisition :
      - nb_leads           : leads entrants dans la cohorte
      - nb_signes          : signés à terme (toute date de signature)
      - taux_signature     : %
      - avg_days_to_sign   : durée moyenne lead→SIGNED (en jours)

    Les données sont company-scopées côté serveur.
    """
    from apps.crm.models import Lead

    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    start = _qdate(request.query_params.get('from'))
    end = _qdate(request.query_params.get('to'))

    # Fenêtre par défaut : 12 mois glissants.
    today = date.today()
    if not start:
        start = (today.replace(day=1) - timedelta(days=365)).replace(day=1)
    if not end:
        end = today

    qs = Lead.objects.filter(
        **co, is_archived=False,
        date_creation__date__gte=start,
        date_creation__date__lte=end,
    )

    group_by = request.query_params.get('group_by', '').strip()
    valid_group_by = {'canal'}  # champs supportés pour le group-by secondaire

    # Buckets par mois d'acquisition.
    cohort_map: dict = defaultdict(lambda: {
        'leads': [], 'signes': 0, 'durees': []
    })

    for lead in qs.only('id', 'stage', 'date_creation', 'canal',
                        'date_modification').iterator():
        month_key = lead.date_creation.strftime('%Y-%m') if lead.date_creation else 'inconnu'
        dim_key = month_key
        if group_by in valid_group_by:
            canal = getattr(lead, 'canal', '') or ''
            dim_key = f'{month_key}/{canal or "—"}'

        cohort_map[dim_key]['leads'].append(lead.id)
        if lead.stage == 'SIGNED':
            cohort_map[dim_key]['signes'] += 1
            # Proxy : date_modification ≈ date de signature (auto_now).
            if lead.date_modification and lead.date_creation:
                sig_date = lead.date_modification.date()
                created_date = lead.date_creation.date()
                delta = (sig_date - created_date).days
                if delta >= 0:
                    cohort_map[dim_key]['durees'].append(delta)

    result = []
    for key in sorted(cohort_map.keys()):
        bucket = cohort_map[key]
        nb = len(bucket['leads'])
        signes = bucket['signes']
        durees = bucket['durees']
        taux = round(signes / nb * 100, 1) if nb > 0 else 0.0
        avg_days = round(sum(durees) / len(durees), 1) if durees else None
        entry = {
            'cohorte': key,
            'nb_leads': nb,
            'nb_signes': signes,
            'taux_signature': taux,
            'avg_days_to_sign': avg_days,
        }
        result.append(entry)

    x = _maybe_xlsx(
        request, 'cohortes.xlsx',
        ['Cohorte', 'Leads', 'Signés', 'Taux (%)', 'Délai moyen (j)'],
        [[r['cohorte'], r['nb_leads'], r['nb_signes'],
          r['taux_signature'], r['avg_days_to_sign'] or '']
         for r in result],
        'Cohortes')
    if x:
        return x

    return Response({
        'from': start.isoformat(),
        'to': end.isoformat(),
        'group_by': group_by or None,
        'cohorts': result,
    })


# ── FG99 — Rentabilité par segment ───────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAdminRole])
def profitability(request):
    """FG99 — Rentabilité agrégée par segment (ADMIN uniquement).

    Prix d'achat utilisé UNIQUEMENT en interne (marge).  Jamais exposé dans
    un export client, jamais dans un PDF.

    Paramètres optionnels :
      ?segment=type_installation|canal   (défaut : type_installation)
      ?from=YYYY-MM-DD  &to=YYYY-MM-DD
      ?export=xlsx

    Retourne pour chaque valeur de segment :
      - segment_value   : valeur du segment
      - count           : nombre de chantiers
      - revenue_ht      : CA facturé HT (somme Factures non annulées)
      - cost_estimate   : coût matière estimé (HT achat × qté)  [INTERNE]
      - margin          : marge brute  [INTERNE]
      - margin_pct      : taux de marge  [INTERNE]
    """
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    from apps.installations.models import Installation
    from apps.ventes.models import Facture

    segment_field = request.query_params.get('segment', 'type_installation')
    allowed = {'type_installation', 'canal'}
    if segment_field not in allowed:
        return Response(
            {'detail': f'?segment doit être parmi {sorted(allowed)}.'},
            status=400)

    start = _qdate(request.query_params.get('from'))
    end = _qdate(request.query_params.get('to'))

    chantiers_qs = Installation.objects.filter(**co).select_related(
        'devis', 'lead').prefetch_related('devis__lignes__produit')
    if start:
        chantiers_qs = chantiers_qs.filter(date_creation__date__gte=start)
    if end:
        chantiers_qs = chantiers_qs.filter(date_creation__date__lte=end)

    # Factures non annulées par devis_id.
    factures = (Facture.objects.filter(**co)
                .exclude(statut=Facture.Statut.ANNULEE)
                .exclude(devis__isnull=True)
                .prefetch_related('lignes'))
    invoiced_by_devis = defaultdict(Decimal)
    for f in factures:
        invoiced_by_devis[f.devis_id] += Decimal(f.total_ht)

    buckets: dict = defaultdict(lambda: {
        'count': 0, 'revenue': Decimal('0'), 'cost': Decimal('0')
    })

    for ch in chantiers_qs:
        if segment_field == 'type_installation':
            key = ch.type_installation or '—'
        else:  # canal
            key = (ch.lead.canal if ch.lead_id and ch.lead else '') or '—'

        invoiced = (invoiced_by_devis.get(ch.devis_id, Decimal('0'))
                    if ch.devis_id else Decimal('0'))
        cost = _devis_cost_estimate(ch.devis) if ch.devis_id else Decimal('0')
        buckets[key]['count'] += 1
        buckets[key]['revenue'] += invoiced
        buckets[key]['cost'] += cost

    rows = []
    for key in sorted(buckets.keys()):
        b = buckets[key]
        margin = b['revenue'] - b['cost']
        margin_pct = (float(margin / b['revenue'] * 100)
                      if b['revenue'] else 0.0)
        rows.append({
            'segment_value': key,
            'count': b['count'],
            'revenue_ht': str(b['revenue']),
            'cost_estimate': str(b['cost']),    # INTERNE
            'margin': str(margin),              # INTERNE
            'margin_pct': round(margin_pct, 1),  # INTERNE
        })
    rows.sort(key=lambda r: r['revenue_ht'], reverse=True)

    x = _maybe_xlsx(
        request, 'rentabilite-INTERNE.xlsx',
        ['Segment', 'Chantiers', 'CA facturé HT',
         'Coût estimé (interne)', 'Marge (interne)', 'Marge %'],
        [[r['segment_value'], r['count'], r['revenue_ht'],
          r['cost_estimate'], r['margin'], r['margin_pct']]
         for r in rows],
        'Rentabilité par segment (interne)')
    if x:
        return x

    total_rev = sum((Decimal(r['revenue_ht']) for r in rows), Decimal('0'))
    total_cost = sum((Decimal(r['cost_estimate']) for r in rows), Decimal('0'))

    return Response({
        'internal': True,
        'segment': segment_field,
        'from': start.isoformat() if start else None,
        'to': end.isoformat() if end else None,
        'total_revenue_ht': str(total_rev),
        'total_cost_estimate': str(total_cost),
        'total_margin': str(total_rev - total_cost),
        'rows': rows,
    })
