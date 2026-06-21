"""T7 — tableau de bord valeur du pipeline (lecture seule, multi-tenant).

Total MAD par étape, prévision pondérée (probabilité par étape × valeur),
devis par statut (avec expiration à la volée), et gains/pertes par motif.
Tout est calculé à la lecture ; rien n'est persisté.
"""
from decimal import Decimal

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from apps.crm import stages as stage_mod


def _co_filter(user):
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


# Probabilité de conversion heuristique par étape (prévision pondérée).
# COLD = quasi nul (parking) ; SIGNED = acquis.
_STAGE_WEIGHTS = {
    'NEW': Decimal('0.10'),
    'CONTACTED': Decimal('0.20'),
    'QUOTE_SENT': Decimal('0.40'),
    'FOLLOW_UP': Decimal('0.60'),
    'SIGNED': Decimal('1.00'),
    'COLD': Decimal('0.05'),
}


def _lead_value(lead):
    """Valeur pipeline d'un lead = total TTC de son devis le plus récent."""
    devis = max(lead.devis.all(), key=lambda d: d.id, default=None)
    if devis is None:
        return Decimal('0')
    try:
        return Decimal(str(devis.total_ttc or 0))
    except Exception:
        return Decimal('0')


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def pipeline(request):
    co = _co_filter(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    from apps.crm.models import Lead
    from apps.ventes.models import Devis
    from apps.ventes.utils.expiry import is_expired

    leads = list(
        Lead.objects.filter(**co, is_archived=False)
        .prefetch_related('devis'))

    # ── Valeur par étape + prévision pondérée ────────────────────────────
    par_etape = []
    forecast = Decimal('0')
    for key in stage_mod.STAGES:
        in_stage = [le for le in leads if le.stage == key and not le.perdu]
        valeur = sum((_lead_value(le) for le in in_stage), Decimal('0'))
        weight = _STAGE_WEIGHTS.get(key, Decimal('0'))
        forecast += valeur * weight
        par_etape.append({
            'stage': key,
            'label': stage_mod.STAGE_LABELS.get(key, key),
            'count': len(in_stage),
            'valeur': str(valeur),
        })

    # ── Devis par statut (expiration à la volée) ─────────────────────────
    statut_labels = dict(Devis.Statut.choices)
    buckets = {}
    for d in Devis.objects.filter(**co).prefetch_related('lignes'):
        statut = 'expire' if is_expired(d) else d.statut
        b = buckets.setdefault(statut, {'count': 0, 'valeur': Decimal('0')})
        b['count'] += 1
        try:
            b['valeur'] += Decimal(str(d.total_ttc or 0))
        except Exception:
            pass
    devis_par_statut = [
        {'statut': k, 'label': statut_labels.get(k, k),
         'count': v['count'], 'valeur': str(v['valeur'])}
        for k, v in buckets.items()
    ]

    # ── Gains / pertes ───────────────────────────────────────────────────
    gagnes = [le for le in leads if le.stage == 'SIGNED' and not le.perdu]
    perdus = [le for le in leads if le.perdu]
    perte_par_motif = {}
    for le in perdus:
        motif = le.motif_perte or 'Non précisé'
        m = perte_par_motif.setdefault(motif, {'count': 0, 'valeur': Decimal('0')})
        m['count'] += 1
        m['valeur'] += _lead_value(le)

    return Response({
        'par_etape': par_etape,
        'prevision_ponderee': str(forecast),
        'devis_par_statut': devis_par_statut,
        'gagnes': {
            'count': len(gagnes),
            'valeur': str(sum((_lead_value(le) for le in gagnes), Decimal('0'))),
        },
        'perdus_par_motif': [
            {'motif': k, 'count': v['count'], 'valeur': str(v['valeur'])}
            for k, v in sorted(perte_par_motif.items(),
                               key=lambda kv: -kv[1]['count'])
        ],
    })


# FG29 — Vélocité du funnel (jours moyens par étape) ─────────────────────────

@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def funnel_velocity(request):
    """Temps moyen de séjour par étape du pipeline (FG29).

    Calcule, pour chaque étape de l'historique chatter, le délai moyen entre
    l'entrée dans l'étape et la sortie (basé sur LeadActivity stage changes).
    Inclut aussi les leads actuellement dans chaque étape (stalled).
    """
    from django.utils import timezone
    co = _co_filter(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    from apps.crm.models import Lead, LeadActivity

    # Pour chaque lead, reconstituer la séquence de changements d'étape
    leads = Lead.objects.filter(**co, is_archived=False)
    stage_dwell = {key: [] for key in stage_mod.STAGES}
    stalled = {key: 0 for key in stage_mod.STAGES}

    for lead in leads:
        changes = list(
            LeadActivity.objects
            .filter(lead=lead, kind=LeadActivity.Kind.MODIFICATION, field='stage')
            .order_by('created_at')
        )
        # Ajouter l'entrée depuis la création (étape initiale = NEW)
        events = [(lead.date_creation, 'NEW')]
        for ch in changes:
            try:
                new_stage = ch.new_value  # label FR — cherchons la clé
                # Retrouver la clé depuis le label
                key = next(
                    (k for k, v in stage_mod.STAGE_LABELS.items() if v == ch.new_value),
                    ch.new_value
                )
                events.append((ch.created_at, key))
            except Exception:
                continue
        # Calculer les durées entre événements consécutifs
        for i in range(len(events) - 1):
            t_in, stage = events[i]
            t_out, _ = events[i + 1]
            if stage in stage_dwell and t_in and t_out:
                try:
                    days = (t_out - t_in).total_seconds() / 86400
                    if 0 <= days <= 730:  # ignore les valeurs aberrantes
                        stage_dwell[stage].append(days)
                except Exception:
                    pass
        # Lead actuellement dans son étape (comptage stalled)
        current_stage = lead.stage
        if current_stage in stalled:
            stalled[current_stage] += 1

    result = []
    for key in stage_mod.STAGES:
        dwells = stage_dwell[key]
        avg_days = round(sum(dwells) / len(dwells), 1) if dwells else None
        result.append({
            'stage': key,
            'label': stage_mod.STAGE_LABELS.get(key, key),
            'avg_days': avg_days,
            'sample_count': len(dwells),
            'currently_in_stage': stalled[key],
        })

    return Response({'velocity': result})
