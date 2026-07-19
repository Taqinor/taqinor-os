"""SIG2 — Quadrant de garde-fous DURS (Layer 0 « constrained-bandit »).

dd-assumption-engine §11 / fa-signals §2.3 : quatre garde-fous durs — fréquence,
``quality_ranking``, CPL, qualité de compte — qui **ne font QUE freiner**. C'est
la couche 0 : elle est sûre à automatiser PRÉCISÉMENT parce qu'elle ne peut
JAMAIS que réduire la dépense ou mettre en pause, jamais accélérer (elle respecte
la règle « les campagnes naissent PAUSED », extension de la règle #3).

**INVARIANT DUR (testé, ``tests/test_signal_guards.py``) : aucune fonction de ce
module ne peut émettre une action d'ACCÉLÉRATION** (augmenter le budget, activer,
dé-pauser, scaler…). L'ensemble EXHAUSTIF des actions qu'un garde-fou peut rendre
est ``BRAKE_ACTIONS`` — pause / rotation créative / réduction de budget / alerte.
Toute autre action est structurellement impossible.

Ce module est **PUR** comme ``health.py`` : ZÉRO I/O, ZÉRO import de ``models``.
Il reçoit un dict de signaux déjà agrégés + une config (``GuardrailConfig`` ou
tout objet portant les mêmes attributs) et rend des VERDICTS (drapeaux + action
de freinage). Il ne matérialise ni ``EngineAction`` ni ``EngineAlert`` — la
persistance/alerte reste au service appelant (via ``alerts.py``/``guardrails``).
Comme les scores de santé (SIG1), un verdict est AFFICHAGE/ALERTE/FREIN — il
n'est JAMAIS une récompense lue par le bandit ou l'allocation.

Seuils : quand ``GuardrailConfig`` porte déjà le champ (fréquence future…), on le
lit ; sinon on retombe sur une CONSTANTE de module RÉVISÉE TRIMESTRIELLEMENT (pas
de migration ici — SIG2 n'ajoute AUCUN champ). ``getattr`` rend l'ajout futur
d'un champ config trivial et rétro-compatible.
"""
from __future__ import annotations

from collections import namedtuple

# ── Vocabulaire d'ACTIONS — STRICTEMENT « freiner » (révisé trimestriellement) ─
# Chaque valeur reflète une transition de sécurité descendante ou neutre. Elles
# s'alignent sur ``EngineAction.Kind`` (pause / rotate_creative) et sur une
# réduction de budget (jamais REBALANCE, ambigu). ``alert`` = pur signalement.
GUARD_ACTION_PAUSE = 'pause'
GUARD_ACTION_ROTATE = 'rotate_creative'
GUARD_ACTION_REDUCE = 'reduce_budget'
GUARD_ACTION_ALERT = 'alert'

#: Ensemble EXHAUSTIF des actions qu'un garde-fou peut émettre. L'invariant testé
#: vérifie que ``all_guard_actions()`` ⊆ ``BRAKE_ACTIONS`` — aucune accélération.
BRAKE_ACTIONS = frozenset({
    GUARD_ACTION_PAUSE, GUARD_ACTION_ROTATE, GUARD_ACTION_REDUCE,
    GUARD_ACTION_ALERT,
})

#: Actions d'ACCÉLÉRATION explicitement INTERDITES — un garde-fou ne doit jamais
#: en produire. Sert de garde négative dans le test d'invariant (et de
#: documentation vivante de ce que ce module ne fera JAMAIS).
FORBIDDEN_ACCELERATE_ACTIONS = frozenset({
    'increase_budget', 'raise_budget', 'scale', 'scale_up', 'boost',
    'accelerate', 'activate', 'unpause', 'resume', 'enable',
    'create_campaign', 'create_adset', 'create_ad', 'rebalance_budget',
})

# ── Sévérités (mêmes libellés que ``rules.py`` — évite un import croisé pour
# rester PUR ; ce sont de simples chaînes). ─────────────────────────────────────
SEVERITY_CRITICAL = 'critical'
SEVERITY_WARNING = 'warning'

# ── Seuils par défaut (CONSTANTES révisées TRIMESTRIELLEMENT — fa-signals §6).
# Aucun n'existe encore sur ``GuardrailConfig`` ; lus via ``getattr`` pour qu'un
# champ futur les remplace sans changer ce module. AUCUNE migration ici. ────────
DEFAULT_FREQUENCY_CAP = 3.0            # fatigue créative (fa-signals §6)
DEFAULT_CPL_CEILING_MULTIPLIER = 1.5   # CPL > 1.5× cible (règle CPA adlibrary)
DEFAULT_CPL_MATURATION_DAYS = 14       # cohorte ≥14 j (filigrane SIG3 — §4.3)
QUALITY_RANKING_MIN_IMPRESSIONS = 500  # diagnostics n'apparaissent qu'après ~500
QUALITY_RANKING_WINDOW_DAYS = 35       # fenêtre glissante Meta [VÉRIFIÉ]

# ``quality_ranking`` est ORDINAL 3 niveaux (Meta) — le SEUL proxy négatif
# utilisable, JAMAIS une récompense. « below_average » soutenu = plancher franchi.
QR_ABOVE = 'above_average'
QR_AVERAGE = 'average'
QR_BELOW = 'below_average'
_QR_ALIASES = {
    'above': QR_ABOVE, 'above_average': QR_ABOVE,
    'average': QR_AVERAGE, 'avg': QR_AVERAGE,
    'below': QR_BELOW, 'below_average': QR_BELOW,
}


# ``triggered`` : garde-fou franchi ? ``action`` : action de FREIN (∈
# BRAKE_ACTIONS) ou ``None`` si non déclenché. ``computed`` : nombres observés.
GuardVerdict = namedtuple(
    'GuardVerdict', ['guard', 'triggered', 'action', 'severity', 'reason',
                     'computed'])


def _not_triggered(guard, computed=None):
    return GuardVerdict(guard, False, None, None, '', computed or {})


def _cfg(config, attr, default):
    """Lit le seuil sur la config si présent, sinon la constante de module."""
    value = getattr(config, attr, None)
    return default if value is None else value


def frequency_guard(signals, config=None):
    """Fatigue — fréquence (ad-set) > plafond → **rotation créative** (frein).

    Ne réduit pas la dépense en soi ; propose de RENOUVELER la création (une
    action descendante côté fatigue, jamais une accélération)."""
    freq = signals.get('frequency')
    cap = _cfg(config, 'frequency_cap', DEFAULT_FREQUENCY_CAP)
    computed = {'frequency': freq, 'cap': cap}
    if freq is None or float(freq) <= float(cap):
        return _not_triggered('frequency', computed)
    return GuardVerdict(
        'frequency', True, GUARD_ACTION_ROTATE, SEVERITY_WARNING,
        f"Fréquence {float(freq):.2f} > plafond {float(cap):.2f} "
        f"(lassitude créative) — roter la création.", computed)


def quality_ranking_guard(signals, config=None):
    """``quality_ranking`` = « below_average » soutenu → **pause + alerte**.

    DRAPEAU, jamais une récompense (§11). Le diagnostic n'existe qu'après
    ≥500 impressions et sur une fenêtre de 35 j : sous ce seuil (ou classement
    absent), on ne déclenche RIEN (donnée indisponible ≠ mauvaise). Un
    classement « above »/« average » ne déclenche pas non plus."""
    raw = signals.get('quality_ranking')
    impressions = signals.get('impressions')
    ranking = _QR_ALIASES.get(str(raw).strip().lower()) if raw else None
    computed = {'quality_ranking': ranking, 'impressions': impressions,
                'min_impressions': QUALITY_RANKING_MIN_IMPRESSIONS,
                'window_days': QUALITY_RANKING_WINDOW_DAYS}
    # Indisponible : pas de classement, ou pas assez d'impressions pour qu'il
    # apparaisse → aucun garde-fou (on ne freine pas sur une absence de donnée).
    if ranking is None:
        return _not_triggered('quality_ranking', computed)
    if impressions is None or float(impressions) < QUALITY_RANKING_MIN_IMPRESSIONS:
        return _not_triggered('quality_ranking', computed)
    if ranking != QR_BELOW:
        return _not_triggered('quality_ranking', computed)
    return GuardVerdict(
        'quality_ranking', True, GUARD_ACTION_PAUSE, SEVERITY_CRITICAL,
        "Classement de qualité « inférieur à la moyenne » sur "
        f"{QUALITY_RANKING_WINDOW_DAYS} j (≥{QUALITY_RANKING_MIN_IMPRESSIONS} "
        "impr.) — pause + alerte (proxy négatif, jamais une récompense).",
        computed)


def cpl_guard(signals, config=None):
    """CPL > X× cible, tenu sur une cohorte MÛRE (≥14 j) → **réduction de budget**.

    Filigrane de cohorte (SIG3) respecté ici même : une cohorte plus jeune que la
    maturation du CPL (14 j) est IGNORÉE — on ne freine jamais sur un CPL immature
    (bruit Poisson). Sans ``cpl_target`` (>0), aucun ratio calculable → rien."""
    cpl = signals.get('cpl')
    target = signals.get('cpl_target')
    cohort_age = signals.get('cohort_age_days')
    mult = _cfg(config, 'cpl_ceiling_multiplier',
                DEFAULT_CPL_CEILING_MULTIPLIER)
    maturation = _cfg(config, 'cpl_maturation_days',
                      DEFAULT_CPL_MATURATION_DAYS)
    ratio = None
    if cpl is not None and target not in (None, 0):
        ratio = float(cpl) / float(target)
    computed = {'cpl': cpl, 'cpl_target': target, 'ratio': ratio,
                'multiplier': mult, 'cohort_age_days': cohort_age,
                'maturation_days': maturation}
    if ratio is None:
        return _not_triggered('cpl', computed)
    # Cohorte immature → jamais de frein sur un CPL pas encore fiable.
    if cohort_age is None or float(cohort_age) < float(maturation):
        return _not_triggered('cpl', computed)
    if ratio <= float(mult):
        return _not_triggered('cpl', computed)
    return GuardVerdict(
        'cpl', True, GUARD_ACTION_REDUCE, SEVERITY_WARNING,
        f"CPL {float(cpl):.0f} MAD = {ratio:.2f}× la cible {float(target):.0f} "
        f"MAD (plafond {float(mult):.2f}×) sur une cohorte ≥{maturation} j — "
        "réduire le budget.", computed)


def account_quality_guard(signals, config=None):
    """Chute de la qualité de compte (intégrité/conformité) → **pause + alerte**.

    « Account Quality » Meta mesure la CONFORMITÉ (adhérence aux règles, taux de
    refus), pas la performance : une baisse menace la DIFFUSION → on freine
    (pause + alerte), on ne copie jamais rien de « performant » d'elle."""
    dropped = signals.get('account_quality_dropped')
    computed = {'account_quality_dropped': bool(dropped),
                'account_quality': signals.get('account_quality')}
    if not dropped:
        return _not_triggered('account_quality', computed)
    return GuardVerdict(
        'account_quality', True, GUARD_ACTION_PAUSE, SEVERITY_CRITICAL,
        "Qualité de compte en baisse (intégrité/conformité) — pause + alerte "
        "pour protéger la diffusion.", computed)


#: Les quatre garde-fous du quadrant, dans un ordre stable.
GUARDS = (frequency_guard, quality_ranking_guard, cpl_guard,
          account_quality_guard)


def evaluate_guards(signals, config=None):
    """Exécute les quatre garde-fous ; renvoie la liste des verdicts DÉCLENCHÉS
    (chacun portant une action de FREIN ∈ ``BRAKE_ACTIONS``). Liste vide = rien
    à freiner. N'écrit rien : le service appelant matérialise pause/alerte."""
    verdicts = []
    for guard in GUARDS:
        verdict = guard(signals or {}, config)
        if verdict.triggered:
            verdicts.append(verdict)
    return verdicts


def all_guard_actions():
    """Ensemble EXHAUSTIF des actions que les garde-fous PEUVENT émettre — utilisé
    par le test d'invariant pour prouver ⊆ ``BRAKE_ACTIONS`` (aucune accélération
    possible, structurellement)."""
    return {GUARD_ACTION_ROTATE, GUARD_ACTION_PAUSE, GUARD_ACTION_REDUCE,
            GUARD_ACTION_ALERT}


def is_brake_only(action):
    """``True`` si l'action est une action de FREIN autorisée (jamais None non
    plus). Une action absente de ``BRAKE_ACTIONS`` est refusée."""
    return action in BRAKE_ACTIONS
