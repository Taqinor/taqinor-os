"""ADSENG12 — Hook DecisionLog systématique (l'audit « pourquoi le moteur a X »).

Chaque sortie du bandit/allocation (P1) DOIT laisser une ligne ``DecisionLog`` :
l'instantané des entrées (stats des bras au moment T), les postérieurs Beta
calculés, l'allocation produite, et le lien vers l'``EngineAction`` éventuelle.
« Aucune décision sans ligne de log » est un INVARIANT (test dédié).

Le hook vit dans CE module (lane ``backend/adsengine-stats``), PAS dans le
``services.py`` partagé. :func:`decide_and_log` est le point d'entrée canonique de
la repondération quotidienne : il calcule ET journalise en un seul appel, si bien
qu'un appelant ne peut PAS obtenir l'allocation sans que la ligne de log soit
écrite — c'est là l'invariant, garanti par construction.

Le calcul reste déterministe (graine RNG) ; seul l'écriture ``DecisionLog`` fait
de l'I/O. ``company`` est TOUJOURS dérivée de l'expérience (jamais reçue de
l'extérieur — discipline multi-tenant).
"""
from __future__ import annotations

from . import allocation, bandit


def _snapshot_arms(arms):
    """Copie JSON-sûre des stats de bras (l'instantané des entrées au moment T)."""
    snap = []
    for a in arms:
        snap.append({
            'label': str(a.get('label', '')),
            'impressions': int(a.get('impressions', 0)),
            'conversions': int(a.get('conversions', 0)),
        })
    return snap


def log_decision(experiment, *, inputs, posteriors, allocations,
                 summary_fr='', action=None):
    """Écrit UNE ligne ``DecisionLog`` (company dérivée de l'expérience).

    ``inputs`` / ``posteriors`` / ``allocations`` sont des structures JSON-sûres.
    ``action`` (optionnel) relie l'``EngineAction`` produite. Renvoie l'objet
    ``DecisionLog`` créé. Aucune valeur numpy n'est stockée telle quelle : la
    sérialisation est du Python natif.
    """
    from .models import DecisionLog
    return DecisionLog.objects.create(
        company=experiment.company,
        experiment=experiment,
        inputs=inputs,
        posteriors=posteriors,
        allocations=allocations,
        summary_fr=summary_fr,
        action=action,
    )


def decide_and_log(experiment, arms, daily_budget_mad, *,
                   impressions_per_arm=None, seed=bandit.DEFAULT_SEED,
                   k=bandit.DEFAULT_K, floor_pct=allocation.DEFAULT_FLOOR_PCT,
                   min_arm_mad=allocation.DEFAULT_MIN_ARM_MAD,
                   window_days=None, action=None, summary_fr=''):
    """Repondération quotidienne : calcule (bandit + allocation) ET journalise.

    ``arms`` : liste de dicts ``{'label', 'impressions', 'conversions'}`` agrégés
    sur la fenêtre. Étapes (dd-science-core §6) :

      1. postérieurs Beta conjugués (:func:`bandit.posteriors`) ;
      2. probabilité d'être le meilleur (:func:`bandit.prob_best`, déterministe) ;
      3. allocation MAD gatée par la porte de repondération
         (:func:`allocation.allocate_daily`) ;
      4. écriture d'une ligne ``DecisionLog`` (instantané + postérieurs +
         allocation + lien action).

    Renvoie ``(result, decision_log)`` où ``result`` porte
    ``prob_best`` / ``posteriors`` / ``allocations`` / ``reweighted``. L'invariant
    « pas de décision sans log » tient parce que la ligne est écrite AVANT le
    retour — impossible d'obtenir l'allocation sans le log.
    """
    labels = [str(a.get('label', f'arm-{i}')) for i, a in enumerate(arms)]
    imps = (impressions_per_arm
            if impressions_per_arm is not None
            else [int(a.get('impressions', 0)) for a in arms])

    post = bandit.posteriors(arms)
    prob = bandit.prob_best(post, k=k, seed=seed)
    reweighted = allocation.can_reweight(imps)
    allocs = allocation.allocate_daily(
        prob, imps, daily_budget_mad,
        floor_pct=floor_pct, min_arm_mad=min_arm_mad)

    # Structures JSON-sûres (Python natif ; jamais de ndarray/np.float).
    prob_list = [float(w) for w in prob]
    post_list = [[float(a), float(b)] for a, b in post]
    alloc_map = {labels[i]: round(float(allocs[i]), 4)
                 for i in range(len(labels))}
    prob_map = {labels[i]: prob_list[i] for i in range(len(labels))}

    inputs = {
        'arms': _snapshot_arms(arms),
        'daily_budget_mad': float(daily_budget_mad),
        'impressions_per_arm': [int(i) for i in imps],
        'seed': int(seed),
        'k': int(k),
        'window_days': window_days,
        'floor_pct': float(floor_pct),
        'min_arm_mad': float(min_arm_mad),
    }
    posteriors = {'alpha_beta': post_list, 'labels': labels}
    allocations = {
        'budget_mad': alloc_map,
        'prob_best': prob_map,
        'reweighted': reweighted,
    }
    if not summary_fr:
        summary_fr = _summary_fr(labels, prob_map, alloc_map, reweighted)

    log = log_decision(
        experiment, inputs=inputs, posteriors=posteriors,
        allocations=allocations, summary_fr=summary_fr, action=action)

    result = {
        'prob_best': prob_map,
        'posteriors': post_list,
        'allocations': alloc_map,
        'reweighted': reweighted,
    }
    return result, log


def _summary_fr(labels, prob_map, alloc_map, reweighted):
    """Phrase FR déterministe (template, jamais de LLM) résumant la décision."""
    if not labels:
        return "Aucun bras vivant : aucune allocation."
    best = max(labels, key=lambda label: prob_map.get(label, 0.0))
    if not reweighted:
        return ("Données insuffisantes (< 100 impressions/bras) : partage égal "
                "maintenu, poids du bandit non appliqués.")
    return (f"Bras le plus probable « {best} » "
            f"(P={prob_map[best] * 100:.0f}%), "
            f"budget {alloc_map[best]:.0f} MAD/jour.")
