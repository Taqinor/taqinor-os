"""XRH31 — Score de risque d'attrition employé, fondation pure.

Comme :mod:`core.churn_risk`, :mod:`core.anomaly`, :mod:`core.forecast` et
:mod:`core.win_probability`, ce module reste une couche de BASE — contrat
import-linter ``core-foundation-is-a-base-layer`` : il n'importe AUCUNE app
métier (jamais ``apps.rh``). ``apps.rh`` assemble les FEATURES via SES propres
selectors (ancienneté, incidents de présence récents, absences non
planifiées, dernière note d'évaluation, temps depuis la dernière
augmentation, sanctions) et passe un simple dict à :func:`attrition_risk` ;
core fournit uniquement le moteur de scoring générique, sans base de données
ni réseau.

Le score sert le SUIVI RH PROACTIF : repérer les collaborateurs à risque de
départ (désengagement, incidents répétés, stagnation salariale, absences
imprévues) AVANT qu'ils ne démissionnent. Le résultat est un score de risque
borné à ``[0, 100]`` (0 = aucun signal de risque, 100 = risque maximal) et une
BANDE lisible (``faible`` / ``moyen`` / ``élevé``).

Si les features ne contiennent rien d'exploitable, le score DÉGRADE PROPREMENT
vers un risque NEUTRE de base (``DEFAULT_RISK``) avec ``used_fallback=True``.
Pur, déterministe, sans base de données ni réseau.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ── Bandes de risque (libellés FR, ordre du moins au plus à risque) ──────────
BAND_FAIBLE = 'faible'
BAND_MOYEN = 'moyen'
BAND_ELEVE = 'élevé'

# Seuils de bande appliqués au score final ``[0, 100]`` :
#   score < MOYEN              → faible
#   MOYEN <= score < ELEVE     → moyen
#   score >= ELEVE             → élevé
BAND_THRESHOLD_MOYEN = 34.0
BAND_THRESHOLD_ELEVE = 67.0

# Risque NEUTRE de repli quand aucune feature exploitable n'est fournie.
DEFAULT_RISK = 30.0

# ── Ancienneté (plus l'ancienneté est FAIBLE, plus le risque est élevé) ──────
# En-deçà de ce seuil (mois), l'ancienneté sature la composante de risque
# (nouvel arrivant = risque de départ précoce plus élevé, statistiquement).
SENIORITY_LOW_SATURATION_MONTHS = 6.0
# Au-delà de ce seuil, l'ancienneté est jugée stabilisante (risque nul pour
# cette composante) — entre les deux, dégressif linéairement.
SENIORITY_HIGH_SATURATION_MONTHS = 36.0
WEIGHT_SENIORITY = 0.20

# ── Incidents de présence récents (FG171) ────────────────────────────────────
WEIGHT_INCIDENTS = 0.20
INCIDENTS_SATURATION = 5.0

# ── Absences non planifiées ───────────────────────────────────────────────────
WEIGHT_ABSENCES = 0.20
ABSENCES_SATURATION = 5.0

# ── Dernière note d'évaluation (échelle 1-5 ; note BASSE = risque élevé) ─────
WEIGHT_EVALUATION = 0.20
EVALUATION_SCALE_MAX = 5.0

# ── Temps depuis la dernière augmentation (mois) ─────────────────────────────
WEIGHT_TENURE_SANS_AUGMENTATION = 0.10
TENURE_SATURATION_MONTHS = 36.0

# ── Sanctions (nombre) ────────────────────────────────────────────────────────
WEIGHT_SANCTIONS = 0.10
SANCTIONS_SATURATION = 3.0


@dataclass
class AttritionRiskResult:
    """Résultat de :func:`attrition_risk`.

    ``score`` est le score d'attrition final borné à ``[0, 100]`` (0 = aucun
    signal, 100 = risque maximal). ``band`` est la bande lisible (``faible`` /
    ``moyen`` / ``élevé``). ``used_fallback`` vaut ``True`` si AUCUNE feature
    exploitable n'a été fournie (le score retombe sur ``DEFAULT_RISK``).
    ``factors`` détaille chaque contribution (explicabilité / tests / UI)."""

    score: float
    band: str
    used_fallback: bool = False
    factors: dict = field(default_factory=dict)


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Borne un réel à ``[lo, hi]``."""
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _coerce_float(raw, default=None):
    """Convertit en ``float`` ou renvoie ``default`` si non numérique/absent."""
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _ramp(value: float | None, saturation: float) -> float | None:
    """Rampe linéaire ``[0, 1]`` : 0 à ``value=0``, 1 dès ``value>=saturation``.

    ``None`` ou valeur négative → ``None`` (composante absente, ignorée)."""
    if value is None or value < 0:
        return None
    if saturation <= 0:
        return 1.0
    return min(value, saturation) / saturation


def _seniority_component(months: float | None) -> float | None:
    """Composante ancienneté : risque DÉCROISSANT avec l'ancienneté.

    ``months <= SENIORITY_LOW_SATURATION_MONTHS`` → risque maximal (1.0) ;
    ``months >= SENIORITY_HIGH_SATURATION_MONTHS`` → risque nul (0.0) ;
    dégressif linéaire entre les deux."""
    if months is None or months < 0:
        return None
    if months <= SENIORITY_LOW_SATURATION_MONTHS:
        return 1.0
    if months >= SENIORITY_HIGH_SATURATION_MONTHS:
        return 0.0
    span = SENIORITY_HIGH_SATURATION_MONTHS - SENIORITY_LOW_SATURATION_MONTHS
    return 1.0 - (months - SENIORITY_LOW_SATURATION_MONTHS) / span


def band_for_score(score: float) -> str:
    """Bande de risque (``faible`` / ``moyen`` / ``élevé``) d'un score
    ``[0, 100]``."""
    if score >= BAND_THRESHOLD_ELEVE:
        return BAND_ELEVE
    if score >= BAND_THRESHOLD_MOYEN:
        return BAND_MOYEN
    return BAND_FAIBLE


def attrition_risk(features) -> AttritionRiskResult:
    """Score de risque d'attrition ``[0, 100]`` à partir de features employé.

    ``features`` : un mapping (dict) fourni par ``apps.rh`` depuis SES
    selectors — JAMAIS un import d'app domaine ici. Clés reconnues (toutes
    optionnelles) :

      * ``seniority_months``           — ancienneté en mois ;
      * ``recent_attendance_incidents`` — incidents de présence récents (FG171) ;
      * ``unplanned_absences``         — absences non planifiées (compte) ;
      * ``last_evaluation_score``      — dernière note d'évaluation (1–5,
        note BASSE = risque élevé) ;
      * ``months_since_last_raise``    — mois depuis la dernière augmentation
        (``Remuneration``) ;
      * ``sanctions_count``            — nombre de sanctions.

    Chaque composante est normalisée à ``[0, 1]`` puis pondérée ; le score
    final est la moyenne pondérée sur les SEULES composantes présentes
    (features absentes n'entraînent PAS le score vers 0), mise à l'échelle
    ``[0, 100]``. Monotone : plus d'incidents/absences/sanctions, une note
    d'évaluation plus basse, une ancienneté plus faible ou un délai plus long
    depuis la dernière augmentation → score PLUS élevé.

    Si AUCUNE feature exploitable n'est fournie, le résultat est
    ``DEFAULT_RISK`` avec ``used_fallback=True``. Pur, déterministe, sans base
    de données ni réseau.
    """
    feats = features or {}
    if not isinstance(feats, dict):
        feats = {}

    factors: dict = {}
    weighted_sum = 0.0
    weight_total = 0.0
    used_any = False

    # ── Ancienneté ───────────────────────────────────────────────────────────
    seniority = _seniority_component(
        _coerce_float(feats.get('seniority_months')))
    if seniority is not None:
        weighted_sum += seniority * WEIGHT_SENIORITY
        weight_total += WEIGHT_SENIORITY
        factors['seniority'] = round(seniority, 4)
        used_any = True

    # ── Incidents de présence récents ───────────────────────────────────────
    incidents = _ramp(
        _coerce_float(feats.get('recent_attendance_incidents')),
        INCIDENTS_SATURATION,
    )
    if incidents is not None:
        weighted_sum += incidents * WEIGHT_INCIDENTS
        weight_total += WEIGHT_INCIDENTS
        factors['incidents'] = round(incidents, 4)
        used_any = True

    # ── Absences non planifiées ─────────────────────────────────────────────
    absences = _ramp(
        _coerce_float(feats.get('unplanned_absences')),
        ABSENCES_SATURATION,
    )
    if absences is not None:
        weighted_sum += absences * WEIGHT_ABSENCES
        weight_total += WEIGHT_ABSENCES
        factors['absences'] = round(absences, 4)
        used_any = True

    # ── Dernière note d'évaluation (basse = risque élevé, donc INVERSÉE) ────
    eval_score = _coerce_float(feats.get('last_evaluation_score'))
    if eval_score is not None and eval_score >= 0:
        normalized = min(eval_score, EVALUATION_SCALE_MAX) / EVALUATION_SCALE_MAX
        evaluation_component = 1.0 - normalized
        weighted_sum += evaluation_component * WEIGHT_EVALUATION
        weight_total += WEIGHT_EVALUATION
        factors['evaluation'] = round(evaluation_component, 4)
        used_any = True

    # ── Temps depuis la dernière augmentation ───────────────────────────────
    tenure_sans_augmentation = _ramp(
        _coerce_float(feats.get('months_since_last_raise')),
        TENURE_SATURATION_MONTHS,
    )
    if tenure_sans_augmentation is not None:
        weighted_sum += (
            tenure_sans_augmentation * WEIGHT_TENURE_SANS_AUGMENTATION)
        weight_total += WEIGHT_TENURE_SANS_AUGMENTATION
        factors['tenure_sans_augmentation'] = round(
            tenure_sans_augmentation, 4)
        used_any = True

    # ── Sanctions ────────────────────────────────────────────────────────────
    sanctions = _ramp(
        _coerce_float(feats.get('sanctions_count')),
        SANCTIONS_SATURATION,
    )
    if sanctions is not None:
        weighted_sum += sanctions * WEIGHT_SANCTIONS
        weight_total += WEIGHT_SANCTIONS
        factors['sanctions'] = round(sanctions, 4)
        used_any = True

    # ── Repli propre : aucune feature exploitable ───────────────────────────
    if not used_any:
        score = _clamp(DEFAULT_RISK)
        return AttritionRiskResult(
            score=round(score, 2),
            band=band_for_score(score),
            used_fallback=True,
            factors={'default': round(DEFAULT_RISK, 2)},
        )

    # Moyenne pondérée sur les SEULES composantes présentes, mise à l'échelle
    # [0, 100].
    ratio = weighted_sum / weight_total if weight_total > 0 else 0.0
    score = _clamp(ratio * 100.0)

    return AttritionRiskResult(
        score=round(score, 2),
        band=band_for_score(score),
        used_fallback=False,
        factors=factors,
    )
