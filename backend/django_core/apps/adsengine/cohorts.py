"""SIG3 — Filigrane de cohorte (« cohort watermark », fa-signals §4.3 / dd §11).

STATUT (PUB25, 2026-07-19) — NON CÂBLÉ en production (SIG3 non pris par PUB1) :
aucun appelant hors tests. Pas un doublon (le ``signature_cohorts`` de
``reporting.py`` est une AUTRE fonction — cohortes de signatures de reporting, pas
le filigrane de maturité de ce module). EN ATTENTE DE : la lecture du filigrane de
maturité par l'allocation/les garde-fous ; à noter, ``signal_guards.cpl_guard``
porte DÉJÀ sa propre garde de maturation de cohorte (14 j). Capacité prête + testée ;
jamais mort silencieux.

Les signaux MÛRISSENT à des vitesses différentes (proxy 7 j → CPL 14-28 j →
signature 60-90 j). La règle : **ancrer chaque signal sur la date d'impression /
clic et n'INTÉGRER un signal au score QUE pour les cohortes plus VIEILLES que la
fenêtre de maturation de ce signal.** On ne compare JAMAIS un nombre mûr à une
cohorte immature — sinon le bruit d'un CPL à 3 jours saliraient le score.

Mécanique (§4.3) : pour une cohorte plus jeune que la maturation d'un signal, ce
signal n'entre PAS → on **renormalise les poids sur les signaux MÛRS** et on
marque le score « provisoire ». Les échelons argent lents (signature) sortent sur
leur propre cadence (trimestrielle), jamais forcés dans le nombre hebdomadaire.

**INVARIANT DUR (testé, ``tests/test_cohorts.py``) : un signal IMMATURE n'est
JAMAIS compté comme mûr.** Sa valeur est ignorée, son poids renormalisé hors du
score, et le score est marqué provisoire.

Module **PUR** comme ``health.py`` / ``signal_guards.py`` : ZÉRO I/O, ZÉRO import
de ``models``. Il reçoit des dicts de signaux normalisés (0..1) + des dates, rend
un score et des drapeaux. Un score de cohorte est AFFICHAGE/ALERTE — jamais lu
par le bandit (le bandit tourne, lui, sur le seul proxy 7 j).
"""
from __future__ import annotations

import datetime
from collections import namedtuple

# ── Âges de maturation PAR signal (jours) — fa-signals §4.3. Un signal est MÛR
# pour une cohorte dont l'âge (jours depuis l'impression) est ≥ à cette valeur.
# Révisé trimestriellement ; aucune migration (constantes de module). ───────────
MATURATION_DAYS = {
    # ~0-1 j : instantanés (dénominateur/dénombrements du jour même).
    'impressions': 1,
    'ctr': 1,
    'frequency': 1,
    'quality_ranking': 1,
    # 7 j : fenêtre d'attribution CTWA (conversations).
    'ctwa_conversations': 7,
    # 14 j : lead qualifié / CPL (cohorte 14-28 j).
    'qualified_lead': 14,
    'cpl': 14,
    # 21 j : devis envoyé / ouvert (cohorte 21-28 j) — score OPÉRATIONS.
    'devis_sent': 21,
    'devis_opened': 21,
    # 60-90 j : signature (cadence TRIMESTRIELLE, jamais hebdomadaire).
    'signature': 60,
}

#: Signaux LENTS — jamais intégrés au score HEBDOMADAIRE, seulement à la cadence
#: trimestrielle (§4.3 : « la signature apparaît sur son propre rythme lent »).
SLOW_SIGNALS = frozenset({'signature'})

#: Maturation d'un signal INCONNU : traité comme JAMAIS mûr (conservateur —
#: respecte l'invariant « un immature n'est jamais compté mûr »). On ne devine
#: pas la maturité d'un signal qu'on ne connaît pas.
UNKNOWN_MATURATION_DAYS = float('inf')


def _clamp01(value):
    return max(0.0, min(1.0, float(value)))


def _as_date(value):
    """Normalise ``date``/``datetime`` en ``date`` (pour un delta en jours)."""
    if isinstance(value, datetime.datetime):
        return value.date()
    return value


def cohort_age_days(impression_date, as_of=None):
    """Âge (jours) d'une cohorte = jours écoulés depuis la date d'impression /
    clic. ``as_of`` par défaut = aujourd'hui. Négatif borné à 0 (impression dans
    le futur → cohorte d'âge 0)."""
    impression = _as_date(impression_date)
    ref = _as_date(as_of) if as_of is not None else datetime.date.today()
    delta = (ref - impression).days
    return max(0, delta)


def maturation_of(signal_key):
    """Fenêtre de maturation (jours) d'un signal, ou ``UNKNOWN_MATURATION_DAYS``
    (∞) pour un signal inconnu — jamais mûr par défaut."""
    return MATURATION_DAYS.get(signal_key, UNKNOWN_MATURATION_DAYS)


def is_mature(signal_key, age_days):
    """``True`` SEULEMENT si la cohorte est assez vieille pour ce signal
    (``age_days`` ≥ maturation). Un signal inconnu ou une cohorte trop jeune →
    ``False`` (INVARIANT : jamais compté mûr)."""
    return float(age_days) >= float(maturation_of(signal_key))


def mature_signal_keys(age_days, signal_keys, *, include_slow=False):
    """Sous-ensemble des ``signal_keys`` MÛRS pour une cohorte de cet âge. Par
    défaut exclut les signaux LENTS (signature) — ils ne sont jamais dans le
    score hebdomadaire ; ``include_slow=True`` pour un score trimestriel."""
    result = []
    for key in signal_keys:
        if not include_slow and key in SLOW_SIGNALS:
            continue
        if is_mature(key, age_days):
            result.append(key)
    return result


def renormalize_weights(weights, age_days, *, include_slow=False):
    """Renormalise ``weights`` (dict signal→poids) sur les seuls signaux MÛRS
    d'une cohorte de cet âge : les immatures sont EXCLUS (poids 0) et la somme
    des poids restants est ramenée à 1.0.

    Renvoie ``(poids_renormalisés, provisoire)`` — ``provisoire=True`` si au
    moins un signal a été exclu (immature/lent) : le score n'est pas encore
    complet. Si aucun signal mûr (ou somme de poids nulle) → dict vide,
    provisoire True."""
    mature = set(mature_signal_keys(
        age_days, list(weights.keys()), include_slow=include_slow))
    kept = {k: float(w) for k, w in weights.items()
            if k in mature and float(w) > 0}
    total = sum(kept.values())
    dropped_any = len(kept) < len(weights)
    if total <= 0:
        return {}, True
    renormalized = {k: w / total for k, w in kept.items()}
    return renormalized, dropped_any


# ``score`` : moyenne pondérée sur les seuls signaux MÛRS (0..1). ``provisional``
# : au moins un signal encore immature (score incomplet). ``mature_keys`` /
# ``dropped_keys`` : ce qui est entré / a été écarté. ``weights_used`` : poids
# renormalisés effectivement appliqués.
CohortScore = namedtuple(
    'CohortScore',
    ['score', 'provisional', 'mature_keys', 'dropped_keys', 'weights_used'])


def integrate_cohort(signals, weights, age_days, *, include_slow=False):
    """Intègre une cohorte À MATURATION : score = moyenne pondérée des signaux
    MÛRS (valeurs 0..1), poids renormalisés sur les mûrs (§4.3).

    La valeur d'un signal IMMATURE est IGNORÉE même si elle est présente dans
    ``signals`` — invariant dur. Score marqué provisoire tant que tous les
    signaux pondérés ne sont pas mûrs."""
    weights_used, provisional = renormalize_weights(
        weights, age_days, include_slow=include_slow)
    all_keys = set(weights.keys())
    mature_keys = set(weights_used.keys())
    dropped_keys = sorted(all_keys - mature_keys)
    score = 0.0
    for key, weight in weights_used.items():
        score += weight * _clamp01(signals.get(key, 0.0))
    return CohortScore(
        score=_clamp01(score), provisional=provisional,
        mature_keys=sorted(mature_keys), dropped_keys=dropped_keys,
        weights_used=weights_used)


# ── Ancrage sur la date d'impression : un helper cohorte anchoré. ──────────────
Cohort = namedtuple('Cohort', ['impression_date', 'signals'])


def score_cohort(cohort, weights, *, as_of=None, include_slow=False):
    """Score d'une ``Cohort`` (ancrée sur sa date d'impression) à la date
    ``as_of`` — calcule l'âge PUIS intègre à maturation. Sucre pour
    ``integrate_cohort`` avec l'âge dérivé de l'ancrage."""
    age = cohort_age_days(cohort.impression_date, as_of)
    return integrate_cohort(
        cohort.signals or {}, weights, age, include_slow=include_slow)
