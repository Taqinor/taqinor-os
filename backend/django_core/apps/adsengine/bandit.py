"""ADSENG8 — Bandit beta-binomial (Thompson sampling), cœur statistique.

Le cœur mathématique du moteur de décision (P1, dd-science-core §2). Un bandit
Thompson beta-binomial : par bras, un postérieur conjugué Beta(α, β) mis à jour
depuis les stats quotidiennes (``ArmDailyStat``), puis une allocation par la
**probabilité d'être le meilleur** estimée par 10 000 tirages Monte-Carlo (la
méthode GrowthBook — RÉFÉRENCE, jamais vendue : ``docs.growthbook.io/bandits``).

Ce module est **pur** : fonctions déterministes, ZÉRO I/O (aucun accès base,
aucun import de ``models``). Il reçoit des agrégats simples ``{'impressions',
'conversions'}`` et rend des nombres. Le déterminisme est garanti par la graine
RNG (``seed``) — les mêmes données produisent TOUJOURS la même allocation
(auditabilité, mandat « moteur déterministe, pas d'IA dans la boucle »).

Récompense (Bernoulli) : ``success`` = une impression ayant mené à une
conversation CTWA démarrée. ``trials`` = impressions ; ``successes`` =
conversations. Prior : Beta(1, 1) (uniforme, le défaut bayésien faible de
GrowthBook).

La politique d'allocation en MAD (plancher d'exploration) et les règles
kill/promote vivent dans ``allocation.py`` (ADSENG10) — ce fichier ne porte que
les primitives statistiques (postérieurs + probabilité-d'être-le-meilleur).
"""
from __future__ import annotations

import numpy as np

# Défauts (dd-science-core §7 « Config defaults »).
DEFAULT_K = 10_000          # tirages Monte-Carlo (§2.3)
DEFAULT_PRIOR_ALPHA = 1.0   # Beta(1, 1) — prior uniforme (§2.2)
DEFAULT_PRIOR_BETA = 1.0
DEFAULT_SEED = 0            # graine → reproductible / déterministe


def posteriors(arms, alpha0=DEFAULT_PRIOR_ALPHA, beta0=DEFAULT_PRIOR_BETA):
    """Postérieurs Beta conjugués par bras (exact, sans MCMC ; dd §2.2).

    ``arms`` : itérable de dicts agrégés sur la fenêtre, chacun avec
    ``impressions`` et ``conversions`` (entiers ≥ 0). Renvoie une liste de
    tuples ``(alpha, beta)`` :

        alpha_i = alpha0 + Σ conversions_i
        beta_i  = beta0  + Σ (impressions_i − conversions_i)

    Les échecs sont bornés à ≥ 0 (une conversion ne peut dépasser une
    impression ; on ne fabrique jamais un β négatif). Fonction pure.
    """
    result = []
    for a in arms:
        conv = max(int(a.get('conversions', 0)), 0)
        imp = max(int(a.get('impressions', 0)), 0)
        failures = max(imp - conv, 0)
        result.append((alpha0 + conv, beta0 + failures))
    return result


def prob_best(post, k=DEFAULT_K, seed=DEFAULT_SEED, rng=None):
    """Probabilité que chaque bras soit le MEILLEUR (Thompson, Monte-Carlo).

    Tire ``k`` échantillons ``θ_i ~ Beta(α_i, β_i)`` par bras et renvoie, pour
    chaque bras, la fraction de tirages où il est le maximum ::

        w_i = P(bras i est le meilleur) ≈ (1/k) Σ_k 1[ θ_i = max_j θ_j ]

    C'est exactement la méthode GrowthBook (« Thompson sampling allocates
    traffic proportionally to the probability that an arm is best »). Les poids
    ``w_i`` somment à 1 (propriété testée). Déterministe sous ``seed`` : le même
    ``post`` + même graine rend toujours le même vecteur.

    ``post`` : liste de tuples ``(alpha, beta)`` (sortie de :func:`posteriors`).
    ``rng`` : un ``numpy.random.Generator`` optionnel (sinon dérivé de ``seed``).
    Renvoie un ``numpy.ndarray`` de longueur ``len(post)``. Fonction pure.
    """
    n = len(post)
    if n == 0:
        return np.zeros(0)
    if n == 1:
        return np.ones(1)
    generator = rng if rng is not None else np.random.default_rng(seed)
    draws = np.column_stack([generator.beta(a, b, k) for a, b in post])
    winners = draws.argmax(axis=1)
    return np.bincount(winners, minlength=n) / k


def probability_best(arms, k=DEFAULT_K, seed=DEFAULT_SEED,
                     alpha0=DEFAULT_PRIOR_ALPHA, beta0=DEFAULT_PRIOR_BETA,
                     rng=None):
    """Raccourci : ``prob_best(posteriors(arms))`` en une passe.

    Reçoit directement les agrégats de bras (``impressions``/``conversions``) et
    rend le vecteur de probabilité-d'être-le-meilleur. Fonction pure,
    déterministe sous ``seed``.
    """
    return prob_best(posteriors(arms, alpha0=alpha0, beta0=beta0),
                     k=k, seed=seed, rng=rng)
