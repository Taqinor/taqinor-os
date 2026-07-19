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

from django.utils import timezone

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
# Pas d'échantillonnage = fenêtre : les fenêtres consécutives ne se CHEVAUCHENT
# donc PAS. La convergence « soutenue » (deux derniers pas) porte alors sur deux
# échantillons INDÉPENDANTS — un ``noisy_tie`` ne peut pas paraître converger deux
# fenêtres de suite par corrélation de bruit partagé.
SIM_STEP_DAYS = 14
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


# ═══════════════════════════════════════════════════════════════════════════
# ASG7 — Harnais de simulation de l'ORDONNANCEUR de l'arbre d'hypothèses.
#
# Rejoue la mécanique décay (ASG2) / VoI (ASG3) / cascade (ASG4) sur des nœuds
# SYNTHÉTIQUES déterministes (seed figé) et prouve les quatre comportements-clés
# de l'arbre vivant (dd-assumption-engine §3.2/§3.3/§3.5, §1 correction n°1) contre
# une vérité terrain CONNUE — SANS aucun test calendaire, SANS toucher Meta :
#
#   * ``peremption_retest_auto`` — un nœud validé s'oublie (décay hebdo) jusqu'à
#     ce que son incertitude U regonfle et qu'il RE-SURFACE en tête de file VoI,
#     par U SEUL, sans qu'aucun retest calendaire ne soit déclenché (§3.2/§3.3) ;
#   * ``saison_revient`` — un nœud saisonnier (``tags_saison``) est EXCLU de
#     l'horloge hebdomadaire : son posterior in-saison est préservé intact (jamais
#     oublié) pour quand la saison revient, alors qu'un frère non saisonnier, lui,
#     s'oublie (§3.2 dernière phrase) ;
#   * ``cascade_invalidation`` — la bascule d'un parent marque ses enfants PÉRIMÉS
#     (stale) en cascade, et AUCUN n'est re-testé automatiquement : le re-test ne
#     passe QUE par la file VoI (§3.5) ;
#   * ``famine_testabilite`` — quand la file ne contient que des barreaux
#     INTESTABLES (T≈0), le moteur ne BRÛLE PAS le slot dessus : il PROPOSE à un
#     humain (§1 correction n°1 — jamais viser l'intestable).
#
# Chaque scénario est déterministe sous ``seed`` (le seul aléa est le Monte-Carlo
# Thompson de ``bandit.prob_best``, seedé ; le décay est pur, la cascade est
# purement structurelle). Ce harnais N'OUVRE JAMAIS d'``Experiment`` ni ne touche
# ``last_tested_at`` : « re-test auto » y désigne la RE-PRIORISATION par la file,
# jamais un test réellement lancé.
# ═══════════════════════════════════════════════════════════════════════════

# Verdict attendu par scénario d'ordonnanceur (la « vérité terrain » assert).
ASSUMPTION_EXPECTED_VERDICT = {
    'peremption_retest_auto': 'resurfaced',
    'saison_revient': 'season_preserved',
    'cascade_invalidation': 'cascade_stale',
    'famine_testabilite': 'proposed_to_human',
}

# Nombre de semaines d'oubli appliquées au nœud périmé : 3 demi-vies de la classe
# créatif (H=8) → distance au prior /8, U passe de ~0.18 à ~0.33 (marge robuste
# au-dessus d'un frère resté net à ~0.18). Figé pour le déterminisme.
_PEREMPTION_WEEKS = 24
# En dessous de ce T, un barreau est jugé INTESTABLE : le moteur propose à un
# humain plutôt que de brûler le slot (§1 correction n°1). Le contexte MDE
# ``_UNTESTABLE`` ci-dessous donne T≈0.03 (barreau signature).
_FAMINE_T_FLOOR = 0.05

# Contextes MDE/coût figés (mêmes barreaux que les tests VoI dorés) : un contexte
# pleinement testable (T=1) et un contexte intestable (MDE infaisable, T≈0.03).
_TESTABLE_CTX = {'delta_plausible': 0.5, 'p': 0.02, 'n': 25200, 'cost': 1.0}
_UNTESTABLE_CTX = {'delta_plausible': 0.02, 'p': 0.06, 'n': 2, 'cost': 1.0}


def _mk_node(company, **kw):
    """Fabrique un ``AssumptionNode`` synthétique déterministe (défauts créatif
    H=8, prior Beta(1,1)). Aucun aléa : tous les champs sont posés explicitement."""
    from .models import AssumptionNode
    defaults = dict(
        company=company, classe=AssumptionNode.Classe.CREATIF,
        enonce_fr='Hypothèse synthétique.', enjeux_s=0.5, pertinence_r=0.5,
        alpha=1.0, beta=1.0, alpha0=1.0, beta0=1.0, demi_vie_semaines=8)
    defaults.update(kw)
    return AssumptionNode.objects.create(**defaults)


def _scenario_peremption(company, *, seed):
    """Un nœud validé net s'oublie N semaines → U regonfle → il RE-SURFACE en
    tête de file VoI, par U SEUL, sans retest calendaire (§3.2/§3.3)."""
    from . import assumption_decay, voi
    from .models import AssumptionNode, Experiment

    # Nœud validé, posterior net (U bas) ; dernier test « il y a longtemps ».
    long_ago = timezone.now() - datetime.timedelta(days=90)
    stale = _mk_node(
        company, enonce_fr='Le hook « facture » gagne.', alpha=60.0, beta=6.0,
        statut=AssumptionNode.Statut.VALIDATED, last_tested_at=long_ago)
    # Frère resté FRAIS : même posterior net, jamais oublié (comparaison).
    fresh = _mk_node(
        company, enonce_fr='Le hook « toiture » gagne.', alpha=60.0, beta=6.0,
        statut=AssumptionNode.Statut.VALIDATED, last_tested_at=timezone.now())

    params = {stale.pk: _TESTABLE_CTX, fresh.pk: _TESTABLE_CTX}
    before = {n.pk: s for n, s in voi.rank_candidates(company, params, seed=seed)}
    u_before = before[stale.pk]['U']

    # Horloge HEBDOMADAIRE : à chaque tick, le nœud périmé (dernier test ancien)
    # est éligible et s'oublie d'un cran ; le frais ne l'est jamais. On avance
    # l'horloge d'une semaine à chaque pas — le décay ne touche PAS last_tested_at,
    # donc le nœud périmé reste éligible tick après tick (péremption cumulative).
    anchor = timezone.now()
    for wk in range(1, _PEREMPTION_WEEKS + 1):
        now = anchor + datetime.timedelta(days=7 * wk)
        # Garde le frère hors éligibilité en le « retestant » virtuellement à
        # l'horloge courante (son posterior N'EST PAS touché — juste sa fraîcheur).
        AssumptionNode.objects.filter(pk=fresh.pk).update(last_tested_at=now)
        assumption_decay.run_weekly_decay(company, now=now)

    stale.refresh_from_db()
    fresh.refresh_from_db()
    ranking = voi.rank_candidates(company, params, seed=seed)
    after = {n.pk: s for n, s in ranking}
    winner = ranking[0][0]
    u_after = after[stale.pk]['U']

    resurfaced = (
        winner.pk == stale.pk               # re-surface EN TÊTE de file
        and u_after > u_before              # U a regonflé (§3.3)
        and u_after > after[fresh.pk]['U']  # dépasse le frère resté net
        # AUCUN retest calendaire : la fraîcheur du nœud périmé n'a pas bougé.
        and stale.last_tested_at == long_ago
        # Posterior FRÈRE intact (jamais oublié — seule sa fraîcheur a bougé).
        and (fresh.alpha, fresh.beta) == (60.0, 6.0))

    # Invariant : aucun test réellement ouvert (re-surface ≠ retest lancé).
    no_experiment = not Experiment.objects.filter(company=company).exists()

    verdict = 'resurfaced' if (resurfaced and no_experiment) else 'stuck'
    return {
        'verdict': verdict,
        'winner_node_id': winner.pk,
        'u_before': round(u_before, 4),
        'u_after': round(u_after, 4),
        'weeks_decayed': _PEREMPTION_WEEKS,
        'retest_triggered': not no_experiment,
        'summary_fr': (
            f"Nœud validé oublié {_PEREMPTION_WEEKS} sem : incertitude "
            f"{u_before:.2f}→{u_after:.2f}, re-surface en tête de file par U "
            "seul — aucun retest calendaire."),
    }


def _scenario_saison(company, *, seed):
    """Un nœud saisonnier est EXCLU de l'oubli hebdo : son posterior in-saison est
    préservé pour quand la saison revient, alors qu'un frère non saisonnier
    s'oublie (§3.2)."""
    from . import assumption_decay

    seasonal = _mk_node(
        company, enonce_fr='Le hook « Ramadan » gagne en Ramadan.',
        alpha=40.0, beta=8.0, tags_saison=['ramadan'], last_tested_at=None)
    ordinary = _mk_node(
        company, enonce_fr='Le hook générique gagne.',
        alpha=40.0, beta=8.0, tags_saison=[], last_tested_at=None)

    before_seasonal = (seasonal.alpha, seasonal.beta)
    before_ordinary = (ordinary.alpha, ordinary.beta)

    # Éligibilité : le saisonnier ne doit JAMAIS être oublié ; l'ordinaire, si.
    seasonal_eligible = assumption_decay.needs_weekly_decay(seasonal)
    ordinary_eligible = assumption_decay.needs_weekly_decay(ordinary)

    # Douze semaines d'horloge hebdomadaire (jamais de retest → tous deux
    # « une semaine sans test »). Le saisonnier reste intact ; l'ordinaire s'oublie.
    anchor = timezone.now()
    for wk in range(1, 13):
        assumption_decay.run_weekly_decay(
            company, now=anchor + datetime.timedelta(days=7 * wk))

    seasonal.refresh_from_db()
    ordinary.refresh_from_db()

    season_preserved = (
        (seasonal.alpha, seasonal.beta) == before_seasonal  # intact
        and not seasonal_eligible                            # jamais éligible
        and ordinary_eligible                                # l'ordinaire, si
        and (ordinary.alpha, ordinary.beta) != before_ordinary)  # a oublié

    verdict = 'season_preserved' if season_preserved else 'season_lost'
    return {
        'verdict': verdict,
        'seasonal_posterior': [seasonal.alpha, seasonal.beta],
        'ordinary_posterior': [round(ordinary.alpha, 4), round(ordinary.beta, 4)],
        'seasonal_eligible': seasonal_eligible,
        'summary_fr': (
            "Le nœud saisonnier a gardé son posterior in-saison intact "
            f"({before_seasonal[0]:.0f},{before_seasonal[1]:.0f}) — prêt au "
            "retour de saison ; le frère non saisonnier, lui, s'est oublié."),
    }


def _scenario_cascade(company, *, seed):
    """La bascule d'un parent marque ses enfants PÉRIMÉS (stale) en cascade ;
    AUCUN n'est re-testé automatiquement (re-test via la file VoI seulement,
    §3.5)."""
    from . import assumption_graph
    from .models import (
        AssumptionNode, DecisionLog, EngineAlert, Experiment,
    )

    parent = _mk_node(
        company, classe=AssumptionNode.Classe.ANGLE,
        enonce_fr='Angle « économies » porteur.',
        statut=AssumptionNode.Statut.VALIDATED, alpha=30.0, beta=5.0)
    child_a = _mk_node(
        company, enonce_fr='Variante hook A de l\'angle économies.',
        parent=parent, statut=AssumptionNode.Statut.VALIDATED,
        last_tested_at=None)
    child_b = _mk_node(
        company, enonce_fr='Variante hook B de l\'angle économies.',
        parent=parent, statut=AssumptionNode.Statut.VALIDATED,
        last_tested_at=None)
    # Arête NON hiérarchique (DAG) : un nœud lié devient suspect lui aussi.
    linked = _mk_node(
        company, enonce_fr='Hook « autoconsommation » interagissant.',
        statut=AssumptionNode.Statut.VALIDATED, last_tested_at=None)
    parent.invalidation_links.add(linked)

    # Le parent BASCULE (un test le contredit / un humain l'invalide) : l'appelant
    # pose son statut, la cascade propage aux dépendants.
    parent.statut = AssumptionNode.Statut.STALE
    parent.save(update_fields=['statut', 'updated_at'])
    result = assumption_graph.invalidate_cascade(
        parent, reason_fr='Parent contredit par un test.')

    for node in (child_a, child_b, linked):
        node.refresh_from_db()

    all_stale = all(
        n.statut == AssumptionNode.Statut.STALE
        for n in (child_a, child_b, linked))
    # AUCUN re-test automatique : aucune fraîcheur touchée, aucun Experiment /
    # DecisionLog ouvert par la cascade (§3.5 — re-test via la file VoI seulement).
    no_retest = all(
        n.last_tested_at is None for n in (child_a, child_b, linked))
    no_experiment = not Experiment.objects.filter(company=company).exists()
    no_decisionlog = not DecisionLog.objects.filter(company=company).exists()
    alerts = EngineAlert.objects.filter(
        company=company, severity=EngineAlert.Severity.INFO).count()

    cascade_ok = (
        all_stale and no_retest and no_experiment and no_decisionlog
        and result['alerts'] == 3 and alerts == 3)

    verdict = 'cascade_stale' if cascade_ok else 'cascade_incomplete'
    return {
        'verdict': verdict,
        'invalidated': result['invalidated'],
        'alerts': result['alerts'],
        'retest_triggered': not no_retest,
        'summary_fr': (
            f"Parent basculé : {len(result['invalidated'])} dépendant(s) marqué(s) "
            "périmé(s) en cascade (2 enfants + 1 lien DAG), aucun re-testé "
            "automatiquement — re-test via la file VoI uniquement."),
    }


def _scenario_famine(company, *, seed):
    """La file ne contient que des barreaux INTESTABLES (T≈0) : le moteur ne brûle
    pas le slot, il PROPOSE à un humain (§1 correction n°1)."""
    from . import guardrails, voi
    from .models import EngineAlert, Experiment

    # Nœud à FORT enjeu (S,R élevés) mais structurellement intestable (barreau
    # « signature » : MDE infaisable → T≈0). Sans le clip T, il gagnerait la file.
    untestable = _mk_node(
        company, enonce_fr='La signature du contrat suit-elle le hook ?',
        enjeux_s=1.0, pertinence_r=1.0, alpha=2.0, beta=2.0)

    ranking = voi.rank_candidates(
        company, {untestable.pk: _UNTESTABLE_CTX}, seed=seed)
    top_node, top_score = ranking[0]
    starving = top_score['T'] < _FAMINE_T_FLOOR

    proposed = False
    if starving:
        # On NE brûle PAS le slot (aucun Experiment ouvert) : on propose à un
        # humain via une alerte moteur (signal, jamais un test auto).
        guardrails.emit_alert(
            company, alert_type=guardrails.ALERT_INOPERATIVE,
            message=(
                "🟠 Famine de testabilité : le nœud le plus à enjeu de la file "
                f"« {top_node.enonce_fr[:50]} » est intestable "
                f"(T={top_score['T']:.2f} au MDE courant) — PROPOSÉ à un humain, "
                "slot NON consommé (jamais viser l'intestable)."),
            detail={'node_id': top_node.pk, 'T': round(top_score['T'], 4),
                    'reason': 'testability_famine', 'proposed_to_human': True})
        proposed = True

    # Invariant : aucun test réellement ouvert sur le barreau intestable.
    no_experiment = not Experiment.objects.filter(company=company).exists()
    alert = EngineAlert.objects.filter(
        company=company, alert_type=guardrails.ALERT_INOPERATIVE,
        detail__proposed_to_human=True).first()

    verdict = ('proposed_to_human'
               if (proposed and no_experiment and alert is not None)
               else 'slot_burned')
    return {
        'verdict': verdict,
        'top_node_id': top_node.pk,
        'top_testability': round(top_score['T'], 4),
        'slot_burned': not no_experiment,
        'summary_fr': (
            f"Barreau le plus à enjeu intestable (T={top_score['T']:.2f}) : "
            "proposé à un humain, slot NON brûlé — le moteur ne vise jamais "
            "l'intestable."),
    }


_ASSUMPTION_DRIVERS = {
    'peremption_retest_auto': _scenario_peremption,
    'saison_revient': _scenario_saison,
    'cascade_invalidation': _scenario_cascade,
    'famine_testabilite': _scenario_famine,
}


def simulate_assumption_scheduler(company, *, scenario='peremption_retest_auto',
                                  seed=42):
    """ASG7 — Rejoue l'ordonnanceur de l'arbre sur des nœuds synthétiques.

    Déterministe sous ``seed`` (le seul aléa, le Monte-Carlo Thompson de la file
    VoI, est seedé ; décay et cascade sont purs/structurels). Renvoie un rapport
    JSON-stable avec la clé ``verdict`` + son ``expected_verdict``. N'OUVRE JAMAIS
    d'``Experiment`` ni ne touche Meta."""
    if scenario not in ASSUMPTION_EXPECTED_VERDICT:
        raise ValueError(
            f"Scénario d'ordonnanceur inconnu : {scenario!r}. "
            f"Choix : {', '.join(ASSUMPTION_EXPECTED_VERDICT)}.")

    from .models import GuardrailConfig
    GuardrailConfig.objects.get_or_create(company=company)

    report = _ASSUMPTION_DRIVERS[scenario](company, seed=seed)
    expected = ASSUMPTION_EXPECTED_VERDICT[scenario]
    logger.info('simulator[asg7]: scénario=%s verdict=%s (attendu %s)',
                scenario, report['verdict'], expected)
    return {'scenario': scenario, 'seed': seed,
            'expected_verdict': expected, **report}
