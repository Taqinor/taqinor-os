"""ADSENG36 — Harnais de SIMULATION (l'artefact de confiance).

Rejoue le ``FlightRunner`` sur les comptes SYNTHÉTIQUES ADSENG7 en **temps
accéléré** (des mois en secondes, via l'horloge injectée du runner) et produit un
rapport LISIBLE que la console P7 (ADSENG44) visualise. Le fondateur regarde le
moteur décider contre une vérité terrain CONNUE avant tout dirham réel.

Quatre scénarios dorés, chacun avec un verdict attendu DÉTERMINISTE (seed figé) :

  * ``clear_winner``      — un bras nettement gagnant → le moteur **converge** ;
  * ``noisy_tie``         — deux bras quasi égaux → le moteur **ne conclut PAS** ;
  * ``mid_flight_drift``  — le gagnant change à mi-vol → **dérive détectée** ;
  * ``delivery_collapse`` — la delivery d'un bras s'effondre → **le gardien
    propose une pause + alerte**.

Le harnais NE TOUCHE JAMAIS Meta (aucun client réseau) : il rejoue la boucle
quotidienne (repondération bandit + ``DecisionLog``) sur des ``ArmDailyStat``
pré-alimentés, en avançant une horloge injectée jour après jour ; à chaque pas il
lit la croyance courante du bandit. La détection d'effondrement de delivery
s'appuie sur la série d'impressions (chute brutale) et lève une pause proposée +
une alerte via le gardien réel (propose-only — jamais appliquée, jamais activée).
"""
from __future__ import annotations

import datetime
import logging

from . import guardrails, services
from .flightrunner import FlightRunner
from .management.commands.seed_synthetic_account import (
    _ANCHOR as SYNTH_ANCHOR,
    generate_synthetic_account,
)
from .models import (
    ArmDailyStat, DecisionLog, EngineAction, Experiment, ExperimentArm,
    FlightPlan, GuardrailConfig,
)

logger = logging.getLogger(__name__)

# Fenêtre glissante (jours) de repondération pendant la simulation : ~2 semaines
# = la cadence d'une phase (dd-science-core), assez pour que le bandit voie la
# PERFORMANCE RÉCENTE (indispensable pour révéler une dérive de mi-vol).
SIM_WINDOW_DAYS = 14
# Pas d'échantillonnage de l'horloge accélérée (hebdomadaire).
SIM_STEP_DAYS = 7
# Seuil de « conclusion » : P(best) au-dessus ⇒ le moteur a un gagnant décisif.
# On exige la convergence SOUTENUE (les DEUX derniers pas au-dessus du seuil sur
# le MÊME bras) : un pic de bruit ponctuel ne suffit pas à « conclure » — c'est ce
# qui garde ``noisy_tie`` robustement en « aucun signal » (le gagnant apparent y
# oscille au gré du bruit, jamais deux fenêtres de suite sur le même bras).
CONVERGENCE_PROB = 0.85
# Détection d'effondrement : la moyenne d'impressions du dernier quart tombe
# sous cette fraction de la moyenne de la première moitié (delivery écroulée).
COLLAPSE_RATIO = 0.20
COLLAPSE_MIN_BASELINE = 50  # impressions/jour minimales pour parler d'écroulement

# Verdict attendu par scénario (la « vérité terrain » que le test assert).
EXPECTED_VERDICT = {
    'clear_winner': 'converged',
    'noisy_tie': 'no_signal',
    'mid_flight_drift': 'drift_detected',
    'delivery_collapse': 'collapse_handled',
}


def simulate(company, *, scenario='clear_winner', seed=42, months=2,
             step_days=SIM_STEP_DAYS, window_days=SIM_WINDOW_DAYS):
    """Rejoue le runner sur un compte synthétique et renvoie un rapport lisible.

    Déterministe sous ``seed`` : mêmes données synthétiques ⇒ même timeline ⇒
    même verdict. Renvoie un dict JSON-stable (voir la clé ``verdict`` + la
    ``timeline`` pour P7)."""
    if scenario not in EXPECTED_VERDICT:
        raise ValueError(
            f"Scénario de simulation inconnu : {scenario!r}. "
            f"Choix : {', '.join(EXPECTED_VERDICT)}.")

    summary = generate_synthetic_account(
        company=company, scenario=scenario, months=months, seed=seed,
        create_leads=False)
    GuardrailConfig.objects.get_or_create(company=company)
    experiment = Experiment.objects.get(pk=summary['experiment_id'])

    days = summary['days']
    plan = FlightPlan.objects.create(
        company=company, name=f'[SIM:{scenario}]',
        status=FlightPlan.Statut.ACTIF, start_date=SYNTH_ANCHOR,
        end_date=SYNTH_ANCHOR + datetime.timedelta(days=days - 1))

    timeline = []
    guardian_events = []
    seen_collapse = set()
    for offset in range(step_days, days + 1, step_days):
        as_of = SYNTH_ANCHOR + datetime.timedelta(days=offset)
        runner = FlightRunner(plan, clock=(lambda d=as_of: d))
        runner.run_daily(today=as_of, window_days=window_days)
        timeline.append(_snapshot(experiment, as_of))

        # Gardien : effondrement de delivery (chute brutale d'impressions) →
        # pause PROPOSÉE + alerte (propose-only, jamais appliquée/activée).
        collapses = _detect_delivery_collapse(company, experiment, as_of)
        for label, ad_id in collapses:
            if label in seen_collapse:
                continue
            seen_collapse.add(label)
            _raise_collapse_pause(company, label, ad_id, as_of)
            guardian_events.append({'arm': label, 'as_of': as_of.isoformat()})

    verdict = _verdict(scenario, summary, timeline, guardian_events)
    logger.info('simulator: scénario=%s verdict=%s (attendu %s)',
                scenario, verdict['verdict'], EXPECTED_VERDICT[scenario])
    return {
        'scenario': scenario,
        'seed': seed,
        'months': months,
        'days': days,
        'winning_arm_truth': summary.get('winning_arm'),
        'timeline': timeline,
        'guardian_events': guardian_events,
        **verdict,
    }


def _snapshot(experiment, as_of):
    """Instantané de la croyance du bandit à ``as_of`` (dernière ``DecisionLog``
    écrite par ``run_daily``)."""
    log = (DecisionLog.objects
           .filter(company=experiment.company, experiment=experiment)
           .order_by('-id').first())
    prob, allocs, reweighted = {}, {}, False
    if log and isinstance(log.allocations, dict):
        prob = log.allocations.get('prob_best') or {}
        allocs = log.allocations.get('budget_mad') or {}
        reweighted = bool(log.allocations.get('reweighted'))
    leader = (max(prob, key=lambda k: prob[k]) if prob else None)
    return {
        'as_of': as_of.isoformat(),
        'prob_best': prob,
        'allocations': allocs,
        'reweighted': reweighted,
        'leader': leader,
    }


def _detect_delivery_collapse(company, experiment, as_of):
    """Détecte un effondrement de delivery par bras : la moyenne d'impressions du
    dernier quart de la série tombe sous ``COLLAPSE_RATIO`` de celle de la
    première moitié. Renvoie ``[(label, ad_id), ...]`` des bras écroulés."""
    collapsed = []
    for arm in ExperimentArm.objects.filter(
            company=company, experiment=experiment, is_active=True):
        series = list(
            ArmDailyStat.objects
            .filter(company=company, arm=arm, date__lte=as_of)
            .order_by('date').values_list('impressions', flat=True))
        if len(series) < 8:
            continue
        half = max(1, len(series) // 2)
        last_q = series[-max(1, len(series) // 4):]
        first_avg = sum(series[:half]) / half
        last_avg = sum(last_q) / len(last_q)
        if first_avg >= COLLAPSE_MIN_BASELINE \
                and last_avg < COLLAPSE_RATIO * first_avg:
            collapsed.append((arm.label, arm.ad_id))
    return collapsed


def _raise_collapse_pause(company, label, ad_id, as_of):
    """Lève une PAUSE proposée + une alerte pour un effondrement de delivery
    (gardien propose-only : approbation humaine requise, jamais d'activation)."""
    reason_fr = (
        f"Effondrement de delivery détecté sur « {label} » au "
        f"{as_of.isoformat()} : impressions quasi nulles alors que la "
        "dépense courait — pause proposée (sécurité).")
    action = services.propose_action(
        company, kind=EngineAction.Kind.PAUSE, reason_fr=reason_fr,
        payload={'target_type': 'ad', 'target_meta_id': ad_id,
                 'delivery_collapse': True})
    guardrails.emit_alert(
        company, alert_type=guardrails.ALERT_ANOMALY, message=reason_fr,
        action=action, detail={'arm': label, 'as_of': as_of.isoformat()})
    return action


def _sustained_convergence(timeline):
    """Convergence SOUTENUE : les deux derniers pas repondérés au-dessus du seuil
    sur le MÊME bras. Robuste au bruit (un pic ponctuel ne conclut pas). Renvoie
    ``(converged, winner_or_None)``."""
    tail = timeline[-2:] if len(timeline) >= 2 else timeline[-1:]
    if not tail:
        return False, None
    leaders = set()
    for step in tail:
        prob = step.get('prob_best') or {}
        if not (step.get('reweighted') and prob):
            return False, None
        if max(prob.values()) < CONVERGENCE_PROB:
            return False, None
        leaders.add(max(prob, key=lambda k: prob[k]))
    if len(leaders) != 1:
        return False, None
    return True, next(iter(leaders))


def _verdict(scenario, summary, timeline, guardian_events):
    """Calcule le verdict déterministe à partir de la timeline + du gardien."""
    empty = {'prob_best': {}, 'leader': None, 'reweighted': False}
    final = timeline[-1] if timeline else empty
    prob = final.get('prob_best') or {}
    ordered = sorted(prob.values(), reverse=True)
    max_p = ordered[0] if ordered else 0.0
    second_p = ordered[1] if len(ordered) > 1 else 0.0

    converged, converged_winner = _sustained_convergence(timeline)
    winner = converged_winner or final.get('leader')

    first_leader = next(
        (s['leader'] for s in timeline if s.get('leader')), None)
    final_leader = final.get('leader')
    leader_changed = bool(first_leader and final_leader
                          and first_leader != final_leader)

    guardian_pauses = len(guardian_events)
    collapse_detected = guardian_pauses > 0

    if scenario == 'clear_winner':
        verdict = 'converged' if converged else 'inconclusive'
    elif scenario == 'noisy_tie':
        verdict = 'no_signal' if not converged else 'unexpected_convergence'
    elif scenario == 'mid_flight_drift':
        verdict = 'drift_detected' if leader_changed else 'no_drift'
    else:  # delivery_collapse
        verdict = ('collapse_handled'
                   if (collapse_detected and guardian_pauses >= 1)
                   else 'collapse_missed')

    return {
        'verdict': verdict,
        'expected_verdict': EXPECTED_VERDICT[scenario],
        'converged': converged,
        'winner': winner,
        'max_prob_best': round(float(max_p), 4),
        'separation': round(float(max_p - second_p), 4),
        'leader_changed': leader_changed,
        'collapse_detected': collapse_detected,
        'guardian_pauses': guardian_pauses,
        'summary_fr': _summary_fr(scenario, verdict, winner, max_p,
                                  leader_changed, guardian_pauses),
    }


def _summary_fr(scenario, verdict, winner, max_p, leader_changed, pauses):
    """Phrase FR lisible (jamais de jargon stats) résumant le run."""
    if verdict == 'converged':
        return (f"Le moteur a convergé sur « {winner} » "
                f"(confiance {max_p * 100:.0f}%).")
    if verdict == 'no_signal':
        return ("Aucun gagnant net : le moteur n'a PAS conclu (partage "
                "prudent maintenu) — exactement le bon comportement.")
    if verdict == 'drift_detected':
        return (f"Dérive détectée : le meilleur bras a changé en cours de "
                f"vol (bascule vers « {winner} »).")
    if verdict == 'collapse_handled':
        return (f"Effondrement de delivery géré : {pauses} pause(s) proposée(s) "
                "par le gardien + alerte(s).")
    return (f"Résultat inattendu ({verdict}) — à inspecter avant tout budget "
            "réel.")
