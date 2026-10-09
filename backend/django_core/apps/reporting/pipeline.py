"""T7 — tableau de bord valeur du pipeline (lecture seule, multi-tenant).

Total MAD par étape, prévision pondérée (probabilité par étape × valeur),
devis par statut (avec expiration à la volée), et gains/pertes par motif.
Tout est calculé à la lecture ; rien n'est persisté.
"""
from datetime import date, datetime
from decimal import Decimal

from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from apps.crm import stages as stage_mod
from core.win_probability import (
    base_probability_for_stage,
    win_probability,
)
from drf_spectacular.utils import extend_schema
from rest_framework import serializers as drf_serializers
from drf_spectacular.utils import inline_serializer


def _co_filter(user):
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


# Probabilité de conversion heuristique par étape (prévision pondérée).
# COLD = quasi nul (parking) ; SIGNED = acquis.
#
# FG362 — cette table STATIQUE par étape reste le REPLI : la prévision pondérée
# utilise désormais le scorer par lead `core.win_probability.win_probability`
# (probabilité PAR lead à partir de ses features), et ne retombe sur cette table
# d'étape que si les features sont absentes (dégradation propre). La table de
# base du scorer reproduit ces mêmes poids, donc le repli est identique 1:1.
# AANA44 — clés lues dans `apps.crm.stages` (STAGES.py, règle #2), jamais en
# littéral.
_STAGE_WEIGHTS = {
    stage_mod.NEW: Decimal('0.10'),
    stage_mod.CONTACTED: Decimal('0.20'),
    stage_mod.QUOTE_SENT: Decimal('0.40'),
    stage_mod.FOLLOW_UP: Decimal('0.60'),
    stage_mod.SIGNED: Decimal('1.00'),
    stage_mod.COLD: Decimal('0.05'),
}


def _lead_age_days(lead):
    """Jours depuis la dernière activité du lead (fraîcheur).

    Préfère ``relance_date`` (dernière relance planifiée) si disponible, sinon
    ``date_creation``. Renvoie ``None`` si rien d'exploitable (le scorer ignore
    alors la recency)."""
    now = timezone.now()
    ref = getattr(lead, 'relance_date', None) or getattr(
        lead, 'date_creation', None)
    if ref is None:
        return None
    try:
        if isinstance(ref, datetime):
            delta = now - ref
        elif isinstance(ref, date):
            delta = now.date() - ref
            return max(0.0, float(delta.days))
        else:
            return None
        return max(0.0, delta.total_seconds() / 86400.0)
    except Exception:
        return None


def _lead_win_weight(lead):
    """Probabilité de gain d'un lead (FG362), en :class:`Decimal`.

    Construit les FEATURES du lead (étape, perdu, fraîcheur, priorité, canal)
    et délègue au scorer pur `core.win_probability`. Tout échec retombe sur la
    probabilité d'étape statique (repli identique à l'ancien comportement)."""
    stage = getattr(lead, 'stage', None)
    try:
        features = {
            'stage': stage,
            'perdu': bool(getattr(lead, 'perdu', False)),
            'age_days': _lead_age_days(lead),
            'priorite': getattr(lead, 'priorite', None),
            'canal': getattr(lead, 'canal', None),
        }
        prob = win_probability(features).probability
        return Decimal(str(prob))
    except Exception:
        # Repli : table d'étape statique (via le scorer, sinon poids historique).
        fallback = _STAGE_WEIGHTS.get(stage)
        if fallback is not None:
            return fallback
        return Decimal(str(base_probability_for_stage(stage)))


def _lead_value(lead):
    """Valeur pipeline d'un lead = total TTC de son devis le plus récent.

    APRF14 (C-APRF-004) — calculée UNE fois par lead : quand ses devis sont
    préchargés (``leads_avec_devis_totaux``), la valeur est mémoïsée sur
    l'instance — ``pipeline`` la relisait 2 à 3 fois par lead (étape,
    prévision, gagnés/perdus), chaque fois au prix de ``total_ttc``. Sans
    préchargement, aucun mémo (une instance dont les devis changent entre deux
    appels relit la base, comme avant). Survivant unique : ``commercial.py``
    importe celui-ci."""
    prefetch = getattr(lead, '_prefetched_objects_cache', None) or {}
    memo = 'devis' in prefetch
    if memo and hasattr(lead, '_aprf14_valeur'):
        return lead._aprf14_valeur
    devis = max(lead.devis.all(), key=lambda d: d.id, default=None)
    if devis is None:
        valeur = Decimal('0')
    else:
        try:
            valeur = Decimal(str(devis.total_ttc or 0))
        except Exception:
            valeur = Decimal('0')
    if memo:
        lead._aprf14_valeur = valeur
    return valeur


def leads_avec_devis_totaux(qs):
    """APRF14 — précharge les devis des leads AVEC ce que lit ``total_ttc``
    (``ventes.selectors.devis_avec_totaux`` : ``lignes__produit``) et la
    société (lue par l'expiration à la volée). Prend et rend un queryset de
    leads ; aucun montant ne change."""
    from django.db.models import Prefetch

    from apps.ventes.models import Devis
    from apps.ventes.selectors import devis_avec_totaux
    return qs.prefetch_related(Prefetch(
        'devis',
        queryset=devis_avec_totaux(Devis.objects.select_related('company'))))


def durees_par_etape(leads):
    """APRF14 (C-APRF-026) — durées de séjour (jours) par étape pour ``leads``,
    lues en UNE requête ``LeadActivity`` (et non une par lead).

    Helper unique partagé par ``funnel_velocity`` et
    ``commercial.commercial_dashboard`` : même reconstitution qu'avant (entrée
    en NEW à la création, puis chaque changement d'étape du chatter, libellé →
    clé STAGES.py ; durées hors [0, 730] j ignorées). Rend
    ``{clé d'étape: [jours, ...]}`` pour toutes les clés de ``STAGES``."""
    from apps.crm.models import LeadActivity

    leads = list(leads)
    stage_dwell = {key: [] for key in stage_mod.STAGES}
    if not leads:
        return stage_dwell
    label_vers_cle = {v: k for k, v in stage_mod.STAGE_LABELS.items()}
    changements = {}
    lignes = (LeadActivity.objects
              .filter(lead_id__in=[le.pk for le in leads],
                      kind=LeadActivity.Kind.MODIFICATION, field='stage')
              .order_by('lead_id', 'created_at', 'id')
              .values_list('lead_id', 'created_at', 'new_value'))
    for lead_id, created_at, new_value in lignes:
        changements.setdefault(lead_id, []).append(
            (created_at, label_vers_cle.get(new_value, new_value)))
    for lead in leads:
        events = [(lead.date_creation, stage_mod.NEW)]
        events.extend(changements.get(lead.pk, []))
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
    return stage_dwell


def _lead_has_devis_actif(lead):
    """XSAL7 — True si le lead a AU MOINS un devis actif (is_active, ni
    refusé ni expiré). Sert de garde anti-double-comptage : un lead AVEC
    devis actif contribue via ``_lead_value`` (le devis) ; un lead SANS devis
    actif contribue via ``montant_estime`` — jamais les deux à la fois."""
    from apps.ventes.utils.expiry import is_expired
    for devis in lead.devis.all():
        if not devis.is_active:
            continue
        if devis.statut == 'refuse':
            continue
        try:
            if is_expired(devis):
                continue
        except Exception:
            pass
        return True
    return False


def _devis_signes(co):
    """AANA19 / D-AANA-5 — LE queryset unique des devis « signés » du pilotage.

    « Signé » = ``statut=accepte`` ET ``is_active=True`` : réviser un devis
    accepté (``ventes.domain.cycle_vie.reviser_devis``) laisse la V1 acceptée
    mais INACTIVE ; la compter en plus de la V2 doublait commissions,
    classement, vélocité et tableau de bord. Même règle que
    ``_lead_has_devis_actif`` ci-dessus. Tous les sites du reporting passent
    par ici (commissions, classement, vélocité, analytics, tableau de bord) —
    ne jamais réécrire ce filtre en local.
    """
    from apps.ventes.models import Devis
    return Devis.objects.filter(
        **co, statut=Devis.Statut.ACCEPTE, is_active=True)


def _lead_forecast_value(lead):
    """XSAL7 — Valeur pipeline pondérable d'un lead pour le forecast :
    ``_lead_value`` (son devis) s'il a un devis actif, SINON
    ``montant_estime`` (saisie libre pré-devis) — jamais les deux (pas de
    double comptage)."""
    if _lead_has_devis_actif(lead):
        return _lead_value(lead)
    if lead.montant_estime is not None:
        try:
            return Decimal(str(lead.montant_estime))
        except Exception:
            return Decimal('0')
    return Decimal('0')


_PIPELINE_PIPELINE_REPONSE = inline_serializer('PipelinePipelineReponse', {
    'par_etape': drf_serializers.JSONField(allow_null=True),
    'prevision_ponderee': drf_serializers.JSONField(allow_null=True),
    'devis_par_statut': drf_serializers.JSONField(allow_null=True),
    'gagnes': drf_serializers.JSONField(allow_null=True),
    'perdus_par_motif': drf_serializers.JSONField(allow_null=True),
})


@extend_schema(
    responses={200: _PIPELINE_PIPELINE_REPONSE})
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def pipeline(request):
    co = _co_filter(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    from apps.crm.models import Lead
    from apps.ventes.models import Devis
    from apps.ventes.utils.expiry import is_expired

    # APRF14 — devis préchargés AVEC leurs totaux (requêtes constantes).
    leads = list(leads_avec_devis_totaux(
        Lead.objects.filter(**co, is_archived=False)))

    # ── Valeur par étape + prévision pondérée ────────────────────────────
    par_etape = []
    forecast = Decimal('0')
    for key in stage_mod.STAGES:
        in_stage = [le for le in leads if le.stage == key and not le.perdu]
        valeur = sum((_lead_value(le) for le in in_stage), Decimal('0'))
        # FG362 — prévision pondérée par lead : chaque lead contribue sa valeur
        # × SA probabilité de gain (scorer pur), pas un poids fixe d'étape.
        # XSAL7 — la valeur pondérée utilise ``_lead_forecast_value`` : un lead
        # SANS devis actif contribue son ``montant_estime`` (saisie libre
        # pré-devis) au lieu de peser zéro ; un lead AVEC devis actif contribue
        # toujours la valeur du devis (jamais les deux — pas de double compte).
        forecast += sum(
            (_lead_forecast_value(le) * _lead_win_weight(le) for le in in_stage),
            Decimal('0'),
        )
        par_etape.append({
            'stage': key,
            'label': stage_mod.STAGE_LABELS.get(key, key),
            'count': len(in_stage),
            'valeur': str(valeur),
        })

    # ── Devis par statut (expiration à la volée) ─────────────────────────
    # AANA19 — seules les versions ACTIVES : une révision remplacée n'est pas
    # un second devis (ni une seconde vente si elle était acceptée).
    statut_labels = dict(Devis.Statut.choices)
    buckets = {}
    # APRF14 — ``devis_avec_totaux`` (lignes__produit) + la société lue par
    # ``is_expired`` : plus aucune requête par devis.
    from apps.ventes.selectors import devis_avec_totaux
    devis_actifs = devis_avec_totaux(
        Devis.objects.filter(**co, is_active=True).select_related('company'))
    for d in devis_actifs:
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
    gagnes = [le for le in leads
              if le.stage == stage_mod.SIGNED and not le.perdu]
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

_PIPELINE_FUNNEL_VELOCITY_REPONSE = inline_serializer('PipelineFunnelVelocityReponse', {
    'velocity': drf_serializers.JSONField(allow_null=True),
})


@extend_schema(
    responses={200: _PIPELINE_FUNNEL_VELOCITY_REPONSE})
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def funnel_velocity(request):
    """Temps moyen de séjour par étape du pipeline (FG29).

    Calcule, pour chaque étape de l'historique chatter, le délai moyen entre
    l'entrée dans l'étape et la sortie (basé sur LeadActivity stage changes).
    Inclut aussi les leads actuellement dans chaque étape (stalled).
    """
    co = _co_filter(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    from apps.crm.models import Lead

    # APRF14 — durées par étape en UNE requête LeadActivity (helper partagé
    # avec commercial_dashboard), au lieu d'une requête par lead.
    leads = list(Lead.objects.filter(**co, is_archived=False))
    stage_dwell = durees_par_etape(leads)
    stalled = {key: 0 for key in stage_mod.STAGES}
    for lead in leads:
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
