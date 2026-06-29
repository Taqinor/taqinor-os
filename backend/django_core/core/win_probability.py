"""FG362 — Score de probabilité de gain (win-probability), fondation pure.

Comme :mod:`core.anomaly` et :mod:`core.forecast`, ce module reste une couche de
BASE — contrat import-linter ``core-foundation-is-a-base-layer`` : il n'importe
AUCUNE app métier. L'app appelante (reporting/crm…) extrait les CARACTÉRISTIQUES
d'un lead via SA couche selectors et passe un simple dict de features à
:func:`win_probability` ; core fournit uniquement le moteur de scoring générique
et ne touche jamais la base ni le réseau (librairie standard seulement).

Le score remplace l'heuristique d'ÉTAPE statique (une probabilité fixe par
étape) par une probabilité PAR LEAD : on part de la base d'étape puis on ajuste
avec des signaux continus (fraîcheur, relances, priorité, canal). Tout reste
borné à ``[0, 1]``. Si les features ne contiennent rien d'exploitable, le score
DÉGRADE PROPREMENT vers la base d'étape statique — l'appelant garde un résultat
identique à l'ancien comportement.

Les noms d'étapes canoniques (``NEW``, ``CONTACTED``…) restent ceux de
``STAGES.py`` : core n'en HARDCODE aucune nouvelle liste — il accepte la clé
d'étape déjà résolue par l'appelant et associe une probabilité de base par clé.
La table de base reproduit l'ancienne heuristique de ``pipeline.py`` (NEW=0.10 …
SIGNED=1.00, COLD=0.05) ; toute clé inconnue retombe sur ``DEFAULT_BASE``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Probabilité de conversion de BASE par clé d'étape — reprise 1:1 de
# l'heuristique statique historique de ``apps/reporting/pipeline.py``. Les clés
# sont les clés canoniques de ``STAGES.py`` (résolues par l'appelant) ; core
# n'invente ni ne renomme aucune étape. Une clé absente → ``DEFAULT_BASE``.
STAGE_BASE_PROBABILITY: dict[str, float] = {
    'NEW': 0.10,
    'CONTACTED': 0.20,
    'QUOTE_SENT': 0.40,
    'FOLLOW_UP': 0.60,
    'SIGNED': 1.00,
    'COLD': 0.05,
}

# Repli pour une étape inconnue (jamais négatif, jamais 0 dur).
DEFAULT_BASE: float = 0.10

# Étapes terminales : probabilité figée, aucun ajustement de feature ne s'y
# applique (un lead SIGNED est gagné = 1.0 ; un lead marqué perdu = 0.0).
_TERMINAL_WON = 'SIGNED'

# Priorités reconnues → multiplicateur appliqué à la base (>1 = remonte la
# proba, <1 = la descend). Insensible à la casse ; valeur inconnue = neutre.
_PRIORITY_FACTOR: dict[str, float] = {
    'haute': 1.20,
    'high': 1.20,
    'moyenne': 1.00,
    'medium': 1.00,
    'normale': 1.00,
    'basse': 0.80,
    'low': 0.80,
}

# Canaux d'acquisition → multiplicateur. Un canal entrant/qualifié convertit
# mieux qu'un canal froid. Insensible à la casse ; canal inconnu = neutre.
_CANAL_FACTOR: dict[str, float] = {
    'recommandation': 1.25,
    'referral': 1.25,
    'site': 1.10,
    'web': 1.10,
    'formulaire': 1.10,
    'whatsapp': 1.05,
    'telephone': 1.00,
    'phone': 1.00,
    'salon': 1.00,
    'meta': 0.95,
    'facebook': 0.95,
    'ads': 0.90,
    'achat': 0.85,
    'liste': 0.85,
}

# Au-delà de ce nombre de jours sans avancer, la fraîcheur est totalement
# « consommée » (pénalité de recency maximale).
_STALE_DAYS = 60.0

# Bornes de l'ajustement de recency : un lead tout frais garde 100 % de sa base ;
# un lead complètement périmé tombe à ``_RECENCY_FLOOR`` × base.
_RECENCY_FLOOR = 0.55

# Chaque relance enregistrée signale de l'engagement → petit bonus, plafonné.
_RELANCE_BONUS_EACH = 0.04
_RELANCE_BONUS_CAP = 0.12


@dataclass
class WinProbabilityResult:
    """Résultat de :func:`win_probability`.

    ``probability`` est le score final borné à ``[0, 1]``. ``base`` est la proba
    d'étape de départ (avant ajustements). ``factors`` détaille chaque
    contribution (utile pour l'explicabilité / les tests / l'UI)."""

    probability: float
    base: float
    stage: str = ''
    used_fallback: bool = False        # True = aucune feature exploitable
    factors: dict = field(default_factory=dict)


def base_probability_for_stage(stage) -> float:
    """Probabilité de base d'une clé d'étape (repli ``DEFAULT_BASE``)."""
    if stage is None:
        return DEFAULT_BASE
    return STAGE_BASE_PROBABILITY.get(str(stage), DEFAULT_BASE)


def _clamp01(x: float) -> float:
    """Borne un réel à ``[0, 1]``."""
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _coerce_float(raw, default=None):
    """Convertit en ``float`` ou renvoie ``default`` si non numérique/absent."""
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _recency_factor(age_days: float | None) -> float | None:
    """Multiplicateur de fraîcheur ``[_RECENCY_FLOOR, 1.0]``.

    ``age_days`` = jours depuis la dernière activité/avancée du lead. Un lead
    frais (0 j) garde 1.0 ; à ``_STALE_DAYS`` jours et au-delà il atteint le
    plancher. Décroissance linéaire. ``None``/négatif → pas d'ajustement."""
    if age_days is None or age_days < 0:
        return None
    ratio = min(age_days, _STALE_DAYS) / _STALE_DAYS  # 0..1
    return 1.0 - ratio * (1.0 - _RECENCY_FLOOR)


def win_probability(features) -> WinProbabilityResult:
    """Probabilité de gain ``[0, 1]`` d'un lead à partir de ses features.

    ``features`` : un mapping (dict) fourni par l'app appelante depuis SES
    selectors — JAMAIS un import d'app métier ici. Clés reconnues (toutes
    optionnelles) :

      * ``stage``     — clé d'étape canonique (``'NEW'``…``'COLD'``) ;
      * ``perdu``     — booléen ; ``True`` ⇒ probabilité forcée à 0.0 ;
      * ``age_days``  — jours depuis la dernière activité (fraîcheur) ;
      * ``priorite``  — ``'haute'`` / ``'moyenne'`` / ``'basse'`` (ou EN) ;
      * ``canal``     — canal d'acquisition (``'recommandation'``, ``'meta'``…) ;
      * ``relances``  — nombre de relances effectuées (engagement) ;
      * ``montant``   — valeur TTC du devis (informative, n'altère pas la proba).

    On part de la base d'étape (table statique historique) puis on applique les
    ajustements multiplicatifs disponibles. Si AUCUNE feature exploitable n'est
    fournie (au-delà de l'étape), le résultat est exactement la base d'étape —
    dégradation propre, comportement identique à l'ancienne heuristique.

    Pur, déterministe, sans base de données ni réseau.
    """
    feats = features or {}
    if not isinstance(feats, dict):
        feats = {}

    stage = feats.get('stage')
    stage_key = '' if stage is None else str(stage)
    base = base_probability_for_stage(stage)

    factors: dict = {'stage_base': round(base, 4)}

    # ── Cas terminaux : court-circuit, aucun ajustement ─────────────────────
    if feats.get('perdu') is True:
        return WinProbabilityResult(
            probability=0.0, base=base, stage=stage_key,
            used_fallback=False, factors={**factors, 'perdu': 0.0},
        )
    if stage_key == _TERMINAL_WON:
        return WinProbabilityResult(
            probability=1.0, base=base, stage=stage_key,
            used_fallback=False, factors={**factors, 'gagne': 1.0},
        )

    prob = base
    used_any = False

    # ── Recency (fraîcheur) ─────────────────────────────────────────────────
    rec = _recency_factor(_coerce_float(feats.get('age_days')))
    if rec is not None:
        prob *= rec
        factors['recency'] = round(rec, 4)
        used_any = True

    # ── Priorité ────────────────────────────────────────────────────────────
    prio_raw = feats.get('priorite')
    if prio_raw is not None:
        pf = _PRIORITY_FACTOR.get(str(prio_raw).strip().lower())
        if pf is not None:
            prob *= pf
            factors['priorite'] = round(pf, 4)
            used_any = True

    # ── Canal d'acquisition ─────────────────────────────────────────────────
    canal_raw = feats.get('canal')
    if canal_raw is not None:
        cf = _CANAL_FACTOR.get(str(canal_raw).strip().lower())
        if cf is not None:
            prob *= cf
            factors['canal'] = round(cf, 4)
            used_any = True

    # ── Relances (engagement) — bonus additif plafonné ──────────────────────
    relances = _coerce_float(feats.get('relances'))
    if relances is not None and relances > 0:
        bonus = min(relances * _RELANCE_BONUS_EACH, _RELANCE_BONUS_CAP)
        prob += bonus
        factors['relances_bonus'] = round(bonus, 4)
        used_any = True

    prob = _clamp01(prob)

    return WinProbabilityResult(
        probability=round(prob, 4),
        base=base,
        stage=stage_key,
        used_fallback=not used_any,
        factors=factors,
    )
