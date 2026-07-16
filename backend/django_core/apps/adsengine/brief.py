"""ENG11 — Générateur de brief hebdomadaire déterministe (v1, SANS LLM).

Le brief agrège les chiffres RÉELS de la semaine (dépense, résultats, CPL,
fréquence vs seuil de fatigue, coût-par-signature cumulé, conformité SLA) et les
rend en phrases template FR. **Aucun LLM en v1** : chaque phrase n'insère que des
NOMBRES calculés — jamais de prose générée (motif anti-hallucination).

Il propose 0 à 3 ``EngineAction`` (chacune avec une ``reason_fr`` obligatoire),
dédupliquées contre les propositions déjà ouvertes pour ne pas spammer la boîte
d'approbation. La métrique coût-par-signature réutilise ``metrics`` (réconciliée
avec les miroirs, traçable) ; les chiffres opérationnels (dépense/fréquence/CPL)
sont calculés sur la FENÊTRE de la semaine.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Sum

from . import metrics
from .models import AdCampaignMirror, EngineAction, InsightSnapshot, WeeklyBrief

# Seuil de fatigue créative (fréquence moyenne). En dessous de 2.0 = sain ;
# 2.0–2.5 = attention ; au-delà de 2.5 = fatigue forte (rotation conseillée).
FATIGUE_THRESHOLD_LOW = Decimal('2.0')
FATIGUE_THRESHOLD_HIGH = Decimal('2.5')

MAX_PROPOSALS = 3


def weekly_window(now=None):
    """Fenêtre de 7 jours se terminant à ``now`` (date). Retourne (début, fin)."""
    end = now if isinstance(now, datetime.date) else datetime.date.today()
    start = end - datetime.timedelta(days=6)
    return start, end


def _fatigue_level(freq):
    """Niveau de fatigue à partir de la fréquence moyenne (Decimal|None)."""
    if freq is None:
        return 'inconnu'
    if freq >= FATIGUE_THRESHOLD_HIGH:
        return 'forte'
    if freq >= FATIGUE_THRESHOLD_LOW:
        return 'attention'
    return 'ok'


def _window_aggregate(company, start, end):
    """Agrège dépense / résultats / fréquence des campagnes sur la fenêtre.

    Renvoie ``(spend, results, freq_avg, last_date, per_campaign)`` où
    ``per_campaign`` = ``[(mirror, spend, results, freq_avg), ...]``."""
    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    campaigns = list(
        AdCampaignMirror.objects.filter(company=company).order_by('meta_id'))
    per_campaign = []
    total_spend = Decimal('0')
    total_results = 0
    freqs = []
    last_date = None
    for camp in campaigns:
        agg = (InsightSnapshot.objects
               .filter(company=company, content_type=ct, object_id=camp.pk,
                       date__gte=start, date__lte=end)
               .aggregate(spend=Sum('spend'), results=Sum('results'),
                          freq=Avg('frequency')))
        spend = agg['spend'] or Decimal('0')
        results = agg['results'] or 0
        freq = agg['freq']
        max_date = (InsightSnapshot.objects
                    .filter(company=company, content_type=ct,
                            object_id=camp.pk, date__lte=end)
                    .order_by('-date').values_list('date', flat=True).first())
        if max_date and (last_date is None or max_date > last_date):
            last_date = max_date
        total_spend += spend
        total_results += results
        if freq is not None:
            freqs.append(freq)
        per_campaign.append((camp, spend, results, freq))
    freq_avg = (sum(freqs) / len(freqs)) if freqs else None
    return total_spend, total_results, freq_avg, last_date, per_campaign


def _existing_open_kinds(company):
    """Ensemble (kind, target_object_id) des propositions déjà OUVERTES, pour
    dédupliquer les propositions du brief (jamais deux fois la même)."""
    open_qs = EngineAction.objects.filter(
        company=company, status=EngineAction.Statut.PROPOSEE)
    seen = set()
    for a in open_qs:
        seen.add((a.kind, (a.payload or {}).get('target_object_id')))
    return seen


def _build_proposals(company, per_campaign):
    """Crée 0-3 ``EngineAction`` proposées à partir de règles déterministes.

    * fréquence de campagne ≥ 2.5 (fatigue forte) → rotation créative ;
    * dépense > 0 ET 0 résultat sur la fenêtre → mise en pause.
    Déduplique contre les propositions déjà ouvertes ; plafonne à 3.
    """
    from . import services

    seen = _existing_open_kinds(company)
    proposals = []
    for camp, spend, results, freq in per_campaign:
        if len(proposals) >= MAX_PROPOSALS:
            break
        if freq is not None and freq >= FATIGUE_THRESHOLD_HIGH:
            key = (EngineAction.Kind.ROTATE_CREATIVE, camp.pk)
            if key not in seen:
                proposals.append(services.propose_action(
                    company, kind=EngineAction.Kind.ROTATE_CREATIVE,
                    reason_fr=(
                        f"Fréquence {freq:.1f} sur {camp.meta_id} (≥ 2,5) : "
                        f"roter le créatif pour combattre la fatigue."),
                    payload={'target_type': 'campaign',
                             'target_meta_id': camp.meta_id,
                             'target_object_id': camp.pk}))
                seen.add(key)
                continue
        if spend > 0 and results == 0:
            key = (EngineAction.Kind.PAUSE, camp.pk)
            if key not in seen:
                proposals.append(services.propose_action(
                    company, kind=EngineAction.Kind.PAUSE,
                    reason_fr=(
                        f"{camp.meta_id} a dépensé {spend} MAD pour 0 résultat "
                        f"cette semaine : mise en pause conseillée."),
                    payload={'target_type': 'campaign',
                             'target_meta_id': camp.meta_id,
                             'target_object_id': camp.pk}))
                seen.add(key)
    return proposals[:MAX_PROPOSALS]


def build_brief(company, *, now=None, create_proposals=True):
    """ENG11 — Construit (ou met à jour) le brief hebdomadaire de la société.

    Idempotent par ``(company, period_start)``. Renvoie l'instance
    ``WeeklyBrief`` persistée (avec ``data`` + ``markdown``).
    """
    start, end = weekly_window(now)
    spend, results, freq_avg, last_date, per_campaign = _window_aggregate(
        company, start, end)

    cpl = (spend / results) if results else None
    summary = metrics.cost_per_signature_summary(company)

    proposals = _build_proposals(company, per_campaign) if create_proposals else []

    data = {
        'periode': {'debut': start.isoformat(), 'fin': end.isoformat()},
        'spend_semaine': str(spend),
        'resultats_semaine': results,
        'cpl_semaine': (str(cpl) if cpl is not None else None),
        'frequence_moyenne': (str(freq_avg) if freq_avg is not None else None),
        'fatigue': {
            'seuil_bas': str(FATIGUE_THRESHOLD_LOW),
            'seuil_haut': str(FATIGUE_THRESHOLD_HIGH),
            'niveau': _fatigue_level(freq_avg),
        },
        'cout_par_signature_cumule': summary['cost_per_signature'],
        'signatures_cumulees': summary['total_signed'],
        'sla_ok': bool(last_date is not None and last_date >= start),
        'derniere_sync': (last_date.isoformat() if last_date else None),
        'propositions': [
            {'id': p.id, 'kind': p.kind, 'reason_fr': p.reason_fr}
            for p in proposals
        ],
    }
    markdown = render_markdown(data)

    brief, _ = WeeklyBrief.objects.update_or_create(
        company=company, period_start=start,
        defaults={'period_end': end, 'data': data, 'markdown': markdown})
    return brief


def render_markdown(data):
    """Rend le brief en markdown FR — uniquement des NOMBRES dans des phrases
    template (aucun texte généré). Déterministe."""
    p = data['periode']
    lines = [
        f"# Brief hebdomadaire ({p['debut']} → {p['fin']})",
        '',
        '## Ce qui s\'est passé',
        f"- Dépense de la semaine : {data['spend_semaine']} MAD "
        f"pour {data['resultats_semaine']} résultat(s).",
    ]
    if data['cpl_semaine'] is not None:
        lines.append(f"- Coût par lead (semaine) : {data['cpl_semaine']} MAD.")
    if data['frequence_moyenne'] is not None:
        fat = data['fatigue']['niveau']
        lines.append(
            f"- Fréquence moyenne : {data['frequence_moyenne']} "
            f"(seuil de fatigue {data['fatigue']['seuil_bas']}–"
            f"{data['fatigue']['seuil_haut']}) → {fat}.")
    if data['cout_par_signature_cumule'] is not None:
        lines.append(
            f"- Coût par signature (cumulé) : "
            f"{data['cout_par_signature_cumule']} MAD "
            f"pour {data['signatures_cumulees']} signature(s).")
    lines.append(
        f"- SLA de synchronisation : "
        f"{'à jour' if data['sla_ok'] else 'EN RETARD'}"
        f"{' (dernière sync ' + data['derniere_sync'] + ')' if data['derniere_sync'] else ''}.")
    lines.append('')
    lines.append('## Suggestions')
    if data['propositions']:
        for prop in data['propositions']:
            lines.append(f"- {prop['reason_fr']}")
    else:
        lines.append('- Aucune action proposée cette semaine.')
    return '\n'.join(lines)
