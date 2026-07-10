"""QJ18 + QJ19 — Tableau de bord commercial (lecture seule, multi-tenant).

Deux aspects complémentaires :

  QJ18  commercial_dashboard :
        - Entonnoir de conversion % par étape (clés STAGES.py)
        - Temps moyen dans chaque étape (goulots d'étranglement)
        - Vélocité de vente (délai lead→devis accepté)
        - Taux de victoire global
        - Classement par commercial (CA signé, nb devis, deal moyen, win rate)

  QJ19  win_loss_by_source :
        - Taux de fermeture (won / total) par canal (Lead.canal)
        - Top motifs de perte (Lead.motif_perte + Lead.perdu)
        - Détail par source technique (Lead.source) — lecture seule

Les deux endpoints sont company-scopés côté serveur ; il est impossible de voir
la donnée d'une autre société.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from apps.crm import stages as stage_mod


def _co(user):
    """Filtre company (kwargs dict) ou None si l'utilisateur n'a pas accès."""
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


def _qdate(value):
    """Parse ?from= / ?to= au format ISO, ou None."""
    try:
        return date.fromisoformat((value or '').strip())
    except (ValueError, TypeError):
        return None


def _username(user):
    return getattr(user, 'username', '') if user else ''


def _lead_value(lead):
    """Valeur pipeline = total TTC du devis le plus récent du lead."""
    devis = max(lead.devis.all(), key=lambda d: d.id, default=None)
    if devis is None:
        return Decimal('0')
    try:
        return Decimal(str(devis.total_ttc or 0))
    except Exception:
        return Decimal('0')


# ── QJ18 — Tableau de bord commercial ────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def commercial_dashboard(request):
    """QJ18 — Tableau de bord commercial company-scopé.

    Paramètres optionnels :
      ?from=YYYY-MM-DD   début de fenêtre (date_creation du lead)
      ?to=YYYY-MM-DD     fin de fenêtre

    Retourne :
      funnel          : conversion % par étape (clés STAGES.py, non hardcodés)
      time_in_stage   : durée moyenne (jours) par étape (via LeadActivity)
      win_rate_pct    : taux de victoire global (SIGNED non perdus / total non perdus)
      sales_velocity  : délai moyen lead→devis accepté (jours)
      leaderboard     : classement par commercial (CA HT, nb signés, deal moyen, win rate)
    """
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    from apps.crm.models import Lead, LeadActivity
    from apps.ventes.models import Devis
    from apps.installations.models import Installation

    start = _qdate(request.query_params.get('from'))
    end = _qdate(request.query_params.get('to'))

    leads_qs = Lead.objects.filter(**co, is_archived=False).prefetch_related('devis')
    if start:
        leads_qs = leads_qs.filter(date_creation__date__gte=start)
    if end:
        leads_qs = leads_qs.filter(date_creation__date__lte=end)

    leads = list(leads_qs)

    # ── Entonnoir de conversion ───────────────────────────────────────────────
    total_active = len([le for le in leads if not le.perdu])
    funnel = []
    for key in stage_mod.STAGES:
        in_stage = [le for le in leads if le.stage == key and not le.perdu]
        count = len(in_stage)
        conversion_pct = (
            round(count / total_active * 100, 1) if total_active else 0.0
        )
        valeur = sum((_lead_value(le) for le in in_stage), Decimal('0'))
        funnel.append({
            'stage': key,
            'label': stage_mod.STAGE_LABELS.get(key, key),
            'count': count,
            'valeur': str(valeur),
            'conversion_pct': conversion_pct,
        })

    # ── Taux de victoire global ───────────────────────────────────────────────
    nb_signes = len([le for le in leads if le.stage == 'SIGNED' and not le.perdu])
    win_rate_pct = (
        round(nb_signes / total_active * 100, 1) if total_active else 0.0
    )

    # ── Temps moyen par étape (LeadActivity stage changes) ───────────────────
    stage_dwell = {key: [] for key in stage_mod.STAGES}
    activity_leads = Lead.objects.filter(**co, is_archived=False)
    if start:
        activity_leads = activity_leads.filter(date_creation__date__gte=start)
    if end:
        activity_leads = activity_leads.filter(date_creation__date__lte=end)

    for lead in activity_leads:
        changes = list(
            LeadActivity.objects
            .filter(lead=lead, kind=LeadActivity.Kind.MODIFICATION, field='stage')
            .order_by('created_at')
        )
        events = [(lead.date_creation, 'NEW')]
        for ch in changes:
            try:
                key = next(
                    (k for k, v in stage_mod.STAGE_LABELS.items() if v == ch.new_value),
                    ch.new_value
                )
                events.append((ch.created_at, key))
            except Exception:
                continue
        for i in range(len(events) - 1):
            t_in, stage = events[i]
            t_out, _ = events[i + 1]
            if stage in stage_dwell and t_in and t_out:
                try:
                    days = (t_out - t_in).total_seconds() / 86400
                    if 0 <= days <= 730:
                        stage_dwell[stage].append(days)
                except Exception:
                    pass

    time_in_stage = []
    for key in stage_mod.STAGES:
        dwells = stage_dwell[key]
        avg_days = round(sum(dwells) / len(dwells), 1) if dwells else None
        time_in_stage.append({
            'stage': key,
            'label': stage_mod.STAGE_LABELS.get(key, key),
            'avg_days': avg_days,
            'sample_count': len(dwells),
        })

    # ── Vélocité de vente : délai moyen lead→devis accepté ───────────────────
    signed_devis = (Devis.objects
                    .filter(**co, statut=Devis.Statut.ACCEPTE)
                    .exclude(lead__isnull=True)
                    .select_related('lead'))
    if start:
        signed_devis = signed_devis.filter(date_acceptation__gte=start)
    if end:
        signed_devis = signed_devis.filter(date_acceptation__lte=end)

    velocity_days = []
    for d in signed_devis:
        if d.lead and d.lead.date_creation and d.date_acceptation:
            created = d.lead.date_creation.date()
            days = (d.date_acceptation - created).days
            if 0 <= days <= 730:
                velocity_days.append(days)

    sales_velocity = {
        'avg_days': round(sum(velocity_days) / len(velocity_days), 1) if velocity_days else None,
        'sample_count': len(velocity_days),
    }

    # ── Classement par commercial ─────────────────────────────────────────────
    kwc_by_devis = defaultdict(Decimal)
    insts = (Installation.objects.filter(**co)
             .exclude(devis__isnull=True)
             .values_list('devis_id', 'puissance_installee_kwc'))
    for devis_id, kwc in insts:
        if kwc:
            kwc_by_devis[devis_id] += Decimal(kwc)

    # Nb de leads par responsable (pour win rate individuel).
    leads_by_owner = defaultdict(int)
    for le in leads:
        uid = le.owner_id or 0
        leads_by_owner[uid] += 1

    lb_agg = {}
    for d in signed_devis:
        if d.lead_id and d.lead and d.lead.owner_id:
            owner = d.lead.owner
        else:
            owner = d.created_by
        uid = owner.id if owner else 0
        slot = lb_agg.setdefault(uid, {
            'commercial': _username(owner) or '—',
            'ca_ht': Decimal('0'),
            'nb_devis': 0,
            'kwc': Decimal('0'),
        })
        # QX2 — CA sur le HT REMISÉ de l'option acceptée (chaîne canonique
        # QX1), jamais le HT brut : le classement/CA reflète le vrai revenu
        # signé, pas un montant gonflé par les remises ignorées.
        from apps.ventes.utils.options import option_totaux
        slot['ca_ht'] += Decimal(str(option_totaux(d)['ht']))
        slot['nb_devis'] += 1
        slot['kwc'] += kwc_by_devis.get(d.id, Decimal('0'))

    leaderboard = []
    for uid, slot in lb_agg.items():
        total_leads_owner = leads_by_owner.get(uid, 0)
        win_rate = (
            round(slot['nb_devis'] / total_leads_owner * 100, 1)
            if total_leads_owner else None
        )
        avg_deal = (
            round(float(slot['ca_ht']) / slot['nb_devis'], 2)
            if slot['nb_devis'] else 0
        )
        leaderboard.append({
            'commercial': slot['commercial'],
            'ca_ht': str(slot['ca_ht']),
            'nb_devis_signes': slot['nb_devis'],
            'avg_deal_ht': str(avg_deal),
            'kwc': str(slot['kwc']),
            'win_rate_pct': win_rate,
        })

    leaderboard.sort(key=lambda r: float(r['ca_ht']), reverse=True)

    # ── QX31be — délai jusqu'au PREMIER contact (speed-to-lead) ──────────────
    # De la création du lead à la première activité SORTANTE (appel/e-mail),
    # par commercial. MIT/Oldroyd : contacter < 5 min = 21× de qualification.
    ttft = _time_to_first_touch(co, leads, start, end, LeadActivity)

    return Response({
        'funnel': funnel,
        'win_rate_pct': win_rate_pct,
        'time_in_stage': time_in_stage,
        'sales_velocity': sales_velocity,
        'leaderboard': leaderboard,
        'time_to_first_touch': ttft,
        'total_leads': len(leads),
        'total_signes': nb_signes,
    })


def _time_to_first_touch(co, leads, start, end, LeadActivity):
    """QX31be — minutes moyennes lead→1er contact sortant, global + par
    commercial. Le premier contact = 1ʳᵉ ``LeadActivity`` de type appel/e-mail
    sur le lead. Best-effort : jamais d'exception (renvoie des valeurs vides)."""
    try:
        lead_ids = [le.id for le in leads]
        created = {le.id: le.date_creation for le in leads}
        # Propriétaire du lead (fallback créateur du lead).
        owner_of = {}
        for le in leads:
            owner_of[le.id] = getattr(le, 'owner_id', None) or 0
        acts = (LeadActivity.objects
                .filter(lead_id__in=lead_ids,
                        kind__in=[LeadActivity.Kind.APPEL,
                                  LeadActivity.Kind.EMAIL])
                .order_by('lead_id', 'created_at')
                .values('lead_id', 'created_at', 'user_id'))
        first_touch = {}
        for a in acts:
            if a['lead_id'] not in first_touch:
                first_touch[a['lead_id']] = a
        per_owner = {}
        global_minutes = []
        for lid, a in first_touch.items():
            c = created.get(lid)
            if not c:
                continue
            delta = (a['created_at'] - c).total_seconds() / 60.0
            if delta < 0 or delta > 60 * 24 * 30:  # borne défensive
                continue
            global_minutes.append(delta)
            uid = a.get('user_id') or owner_of.get(lid) or 0
            per_owner.setdefault(uid, []).append(delta)
    except Exception:  # noqa: BLE001 — métrique best-effort
        return {'avg_minutes': None, 'sample_count': 0, 'by_seller': []}

    def _avg(vals):
        return round(sum(vals) / len(vals), 1) if vals else None

    by_seller = [
        {'seller_id': uid, 'avg_minutes': _avg(vals), 'sample_count': len(vals)}
        for uid, vals in per_owner.items()
    ]
    by_seller.sort(key=lambda r: (r['avg_minutes'] is None, r['avg_minutes']))
    return {
        'avg_minutes': _avg(global_minutes),
        'sample_count': len(global_minutes),
        'by_seller': by_seller,
    }


# ── QJ19 — Win/loss par source et motifs de perte ────────────────────────────

@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def win_loss_by_source(request):
    """QJ19 — Taux de clôture par canal/source + top motifs de perte.

    Paramètres optionnels :
      ?from=YYYY-MM-DD  / ?to=YYYY-MM-DD  fenêtre sur date_creation du lead.

    Retourne :
      by_canal           : taux de fermeture par Lead.canal (won / total par canal)
      by_source_technique: idem pour Lead.source (os_native / site_web / import)
      top_loss_reasons   : top motifs de perte (Lead.motif_perte, leads perdus)
      summary            : nb total, nb won, nb lost, overall close rate %
    """
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    from apps.crm.models import Lead

    start = _qdate(request.query_params.get('from'))
    end = _qdate(request.query_params.get('to'))

    leads_qs = Lead.objects.filter(**co, is_archived=False)
    if start:
        leads_qs = leads_qs.filter(date_creation__date__gte=start)
    if end:
        leads_qs = leads_qs.filter(date_creation__date__lte=end)

    leads = list(leads_qs.only(
        'stage', 'perdu', 'canal', 'source', 'motif_perte'))

    # ── Par canal marketing ───────────────────────────────────────────────────
    canal_labels = dict(Lead.Canal.choices)
    canal_buckets = {}  # canal_key → {total, won}
    for le in leads:
        canal = le.canal or 'autre'
        b = canal_buckets.setdefault(canal, {'total': 0, 'won': 0})
        b['total'] += 1
        if le.stage == 'SIGNED' and not le.perdu:
            b['won'] += 1

    by_canal = []
    for canal_key, b in sorted(
            canal_buckets.items(), key=lambda kv: -kv[1]['total']):
        close_rate = (
            round(b['won'] / b['total'] * 100, 1) if b['total'] else 0.0
        )
        by_canal.append({
            'canal': canal_key,
            'label': canal_labels.get(canal_key, canal_key),
            'total': b['total'],
            'won': b['won'],
            'close_rate_pct': close_rate,
        })

    # ── Par source technique ──────────────────────────────────────────────────
    source_labels = dict(Lead.Source.choices)
    source_buckets = {}
    for le in leads:
        src = le.source or 'os_native'
        b = source_buckets.setdefault(src, {'total': 0, 'won': 0})
        b['total'] += 1
        if le.stage == 'SIGNED' and not le.perdu:
            b['won'] += 1

    by_source_technique = []
    for src_key, b in sorted(
            source_buckets.items(), key=lambda kv: -kv[1]['total']):
        close_rate = (
            round(b['won'] / b['total'] * 100, 1) if b['total'] else 0.0
        )
        by_source_technique.append({
            'source': src_key,
            'label': source_labels.get(src_key, src_key),
            'total': b['total'],
            'won': b['won'],
            'close_rate_pct': close_rate,
        })

    # ── Top motifs de perte ───────────────────────────────────────────────────
    perdus = [le for le in leads if le.perdu]
    motif_buckets = {}
    for le in perdus:
        motif = (le.motif_perte or '').strip() or 'Non précisé'
        motif_buckets[motif] = motif_buckets.get(motif, 0) + 1

    top_loss_reasons = sorted(
        [{'motif': k, 'count': v} for k, v in motif_buckets.items()],
        key=lambda r: -r['count']
    )

    # ── Récapitulatif global ──────────────────────────────────────────────────
    nb_total = len(leads)
    nb_won = sum(1 for le in leads if le.stage == 'SIGNED' and not le.perdu)
    nb_lost = len(perdus)
    overall_close_rate = (
        round(nb_won / nb_total * 100, 1) if nb_total else 0.0
    )

    return Response({
        'by_canal': by_canal,
        'by_source_technique': by_source_technique,
        'top_loss_reasons': top_loss_reasons,
        'summary': {
            'nb_total': nb_total,
            'nb_won': nb_won,
            'nb_lost': nb_lost,
            'overall_close_rate_pct': overall_close_rate,
        },
    })
