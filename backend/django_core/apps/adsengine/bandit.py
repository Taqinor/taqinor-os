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


# ── PUB93 — Variante à DÉCOTE EXPONENTIELLE (non-stationnarité), derrière un flag ─
# Les impressions d'il y a 6 semaines pèsent aujourd'hui comme celles d'hier —
# mais la fatigue créative solaire se joue EN SEMAINES : une variante saturée hier
# ne l'était pas il y a un mois. Cette variante PURE, À CÔTÉ de :func:`posteriors`
# (jamais un remplacement), pondère chaque période par une décote exponentielle de
# son ÂGE : les buckets récents dominent. Elle vit derrière un flag (``decay``) :
# **OFF ⇒ BYTE-IDENTIQUE** à ``posteriors`` sur les totaux (poids tous = 1, somme
# entière, aucun flottant), garanti par golden test. Le flag applicatif
# (GuardrailConfig / feature-flag) est câblé PLUS TARD par le service ; ici c'est
# un simple argument déterministe.
DEFAULT_DECAY_HALF_LIFE_PERIODS = 3.0   # demi-vie de la décote (en périodes/sem)


def _decay_rho(half_life_periods):
    """Facteur de décote par période ``ρ = 0.5^(1/H)`` (miroir assumption_decay).

    À ``H`` périodes, ``ρ^H = 0.5`` : le poids d'une observation est divisé par 2
    toutes les ``H`` périodes d'âge. Fonction pure ; ``H`` doit être > 0.
    """
    if half_life_periods <= 0:
        raise ValueError('La demi-vie de décote doit être strictement positive.')
    return 0.5 ** (1.0 / half_life_periods)


def decayed_posteriors(arm_series, *, decay=False,
                       half_life_periods=DEFAULT_DECAY_HALF_LIFE_PERIODS,
                       alpha0=DEFAULT_PRIOR_ALPHA, beta0=DEFAULT_PRIOR_BETA):
    """Postérieurs Beta à décote exponentielle par période. Fonction PURE.

    ``arm_series`` : par bras, une LISTE de buckets de période ordonnés du plus
    ANCIEN au plus RÉCENT, chacun ``{'impressions', 'conversions'}``. Le bucket le
    plus récent a l'âge 0 (poids 1) ; un bucket d'âge ``a`` pèse ``ρ^a`` avec
    ``ρ = 0.5^(1/H)`` ::

        alpha_i = alpha0 + Σ_p ρ^age_p · conversions_p
        beta_i  = beta0  + Σ_p ρ^age_p · (impressions_p − conversions_p)

    **Flag ``decay`` :**

    * ``decay=False`` (OFF, défaut) — AUCUNE décote : poids tous égaux à 1, somme
      entière → résultat **byte-identique** à ``posteriors`` appliqué aux totaux
      cumulés du bras (propriété garantie par golden test) ;
    * ``decay=True`` (ON) — décote exponentielle : les périodes récentes dominent.

    Renvoie une liste de tuples ``(alpha, beta)``.
    """
    rho = _decay_rho(half_life_periods) if decay else None
    result = []
    for buckets in arm_series:
        buckets = list(buckets or [])
        n = len(buckets)
        conv_acc = 0.0 if decay else 0
        fail_acc = 0.0 if decay else 0
        for idx, bucket in enumerate(buckets):
            conv = max(int(bucket.get('conversions', 0)), 0)
            imp = max(int(bucket.get('impressions', 0)), 0)
            failures = max(imp - conv, 0)
            if decay:
                age = n - 1 - idx            # 0 = période la plus récente
                weight = rho ** age
                conv_acc += weight * conv
                fail_acc += weight * failures
            else:
                conv_acc += conv             # somme entière → byte-identique
                fail_acc += failures
        result.append((alpha0 + conv_acc, beta0 + fail_acc))
    return result


def decayed_probability_best(arm_series, *, decay=False,
                             half_life_periods=DEFAULT_DECAY_HALF_LIFE_PERIODS,
                             k=DEFAULT_K, seed=DEFAULT_SEED,
                             alpha0=DEFAULT_PRIOR_ALPHA,
                             beta0=DEFAULT_PRIOR_BETA, rng=None):
    """Probabilité d'être le meilleur sur des postérieurs à décote. Pure.

    Enchaîne :func:`decayed_posteriors` (flag ``decay``) et :func:`prob_best`.
    ``decay=False`` ⇒ mêmes postérieurs que ``posteriors`` sur les totaux, donc
    même vecteur que ``probability_best`` sur les agrégats cumulés.
    """
    post = decayed_posteriors(
        arm_series, decay=decay, half_life_periods=half_life_periods,
        alpha0=alpha0, beta0=beta0)
    return prob_best(post, k=k, seed=seed, rng=rng)
