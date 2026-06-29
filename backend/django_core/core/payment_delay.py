"""FG365 — Prédiction de retard de paiement, fondation pure.

Comme :mod:`core.anomaly`, :mod:`core.forecast`, :mod:`core.win_probability`,
:mod:`core.churn_risk` et :mod:`core.stock_reorder`, ce module reste une couche
de BASE — contrat import-linter ``core-foundation-is-a-base-layer`` : il
n'importe AUCUNE app métier. L'app appelante (ventes / reporting…) extrait les
CARACTÉRISTIQUES d'une facture ouverte via SA couche ``selectors`` (jours de
retard, montant dû, retard moyen historique du client, nombre d'impayés tardifs
passés, relances déjà envoyées…) et passe un simple dict de features à
:func:`payment_delay_risk` ; core fournit uniquement le moteur de scoring
générique et ne touche jamais la base ni le réseau (librairie standard seulement).

Le score sert la PRIORISATION DU RECOUVREMENT : repérer, parmi toutes les
factures ouvertes, lesquelles risquent le plus de payer en retard (ou de ne pas
payer), pour reléancer en premier les plus à risque et les plus lourdes. Le
résultat est un score de risque de retard borné à ``[0, 1]`` (0 = paiera à
l'heure, 1 = très probablement en retard) et une BANDE lisible
(``faible`` / ``moyen`` / ``élevé``).

Si les features ne contiennent rien d'exploitable, le score DÉGRADE PROPREMENT
vers un risque NEUTRE de base (``DEFAULT_RISK``) avec ``used_fallback=True`` —
l'appelant garde un résultat utilisable plutôt qu'une erreur. Toute date utile
(``today``) et toute échéance sont passées en ENTRÉE : le module reste pur et
déterministe, sans base de données ni réseau (``date.today()`` n'est jamais
appelé ici).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ── Bandes de risque (libellés FR, ordre du moins au plus à risque) ──────────
BAND_FAIBLE = 'faible'
BAND_MOYEN = 'moyen'
BAND_ELEVE = 'élevé'

# Seuils de bande appliqués au score final ``[0, 1]`` :
#   score < MOYEN              → faible
#   MOYEN <= score < ELEVE     → moyen
#   score >= ELEVE             → élevé
BAND_THRESHOLD_MOYEN = 0.34
BAND_THRESHOLD_ELEVE = 0.67

# Risque NEUTRE de repli quand aucune feature exploitable n'est fournie : on ne
# part pas de 0 (faussement rassurant) ni de 1 (faux positif), mais d'un milieu
# bas signalant « inconnu, à surveiller ».
DEFAULT_RISK = 0.30

# ── Jours de retard (facture déjà échue impayée) ─────────────────────────────
# Au-delà de ce nombre de jours de retard, la composante « sature » (la facture
# est manifestement en souffrance, contribution maximale).
OVERDUE_SATURATION_DAYS = 90.0
WEIGHT_OVERDUE = 0.40

# ── Retard moyen historique du client ────────────────────────────────────────
# Un client qui paie en moyenne très en retard rejouera ce comportement.
CLIENT_AVG_DELAY_SATURATION_DAYS = 60.0
WEIGHT_CLIENT_HISTORY = 0.25

# ── Impayés / retards tardifs passés du client ───────────────────────────────
# Plus le client a accumulé de factures payées tardivement par le passé, plus le
# risque grimpe.
PRIOR_LATE_SATURATION_COUNT = 5.0
WEIGHT_PRIOR_LATE = 0.20

# ── Relances déjà envoyées sans paiement ─────────────────────────────────────
# Une facture relancée plusieurs fois sans résultat est un mauvais signal : le
# client ne réagit pas. Plus on a relancé en vain, plus le risque monte.
RELANCE_SATURATION_COUNT = 4.0
WEIGHT_RELANCE = 0.15


@dataclass
class PaymentDelayResult:
    """Résultat de :func:`payment_delay_risk`.

    ``score`` est le score de risque de retard final borné à ``[0, 1]`` (0 =
    paiera à l'heure, 1 = très probablement en retard). ``band`` est la bande
    lisible (``faible`` / ``moyen`` / ``élevé``). ``amount`` est le montant dû
    repris tel quel (informatif, sert à pondérer la file de recouvrement côté
    appelant ; n'altère PAS le score). ``used_fallback`` vaut ``True`` si AUCUNE
    feature exploitable n'a été fournie (le score retombe sur ``DEFAULT_RISK``).
    ``factors`` détaille chaque contribution (explicabilité / tests / UI)."""

    score: float
    band: str
    amount: float = 0.0
    used_fallback: bool = False
    factors: dict = field(default_factory=dict)


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


def _ramp(value: float | None, saturation: float) -> float | None:
    """Rampe linéaire ``[0, 1]`` : 0 à ``value=0``, 1 dès ``value>=saturation``.

    ``None`` ou valeur négative → ``None`` (composante absente, ignorée). Sert à
    transformer une quantité « plus c'est grand, plus c'est risqué » (jours de
    retard, nombre d'impayés…) en contribution normalisée. ``saturation`` <= 0
    est gardé contre la division par zéro (toute valeur positive sature alors)."""
    if value is None or value < 0:
        return None
    if saturation <= 0:
        return 1.0
    return min(value, saturation) / saturation


def band_for_score(score: float) -> str:
    """Bande de risque (``faible`` / ``moyen`` / ``élevé``) d'un score ``[0, 1]``."""
    if score >= BAND_THRESHOLD_ELEVE:
        return BAND_ELEVE
    if score >= BAND_THRESHOLD_MOYEN:
        return BAND_MOYEN
    return BAND_FAIBLE


def days_overdue_from_dates(due_date, today) -> float | None:
    """Jours de retard à partir d'une échéance et de ``today`` (entrées).

    Helper optionnel : si l'appelant n'a pas déjà calculé ``days_overdue``, il
    peut passer ``due_date`` et ``today`` (deux :class:`datetime.date`) et
    obtenir le nombre de jours de retard (>= 0 ; ``0`` si pas encore échue ou
    échue aujourd'hui). ``None`` si l'une des dates manque. ``today`` reste une
    ENTRÉE — ce module n'appelle jamais ``date.today()``."""
    if due_date is None or today is None:
        return None
    try:
        delta = (today - due_date).days
    except (TypeError, AttributeError):
        return None
    return float(delta) if delta > 0 else 0.0


def payment_delay_risk(features) -> PaymentDelayResult:
    """Risque de retard de paiement ``[0, 1]`` d'une facture ouverte.

    ``features`` : un mapping (dict) fourni par l'app appelante depuis SES
    selectors — JAMAIS un import d'app métier ici. Clés reconnues (toutes
    optionnelles) :

      * ``days_overdue``            — jours de retard de la facture (déjà échue) ;
        si absent et que ``due_date`` + ``today`` sont fournis, il est dérivé via
        :func:`days_overdue_from_dates` ;
      * ``due_date`` / ``today``    — échéance et date de référence (entrées),
        utilisées seulement si ``days_overdue`` n'est pas fourni ;
      * ``client_avg_delay_days``   — retard moyen historique du client (jours) ;
      * ``client_prior_late_count`` — nombre de factures passées payées en
        retard pour ce client ;
      * ``relance_count``           — nombre de relances déjà envoyées sans
        paiement sur cette facture ;
      * ``montant_du`` / ``amount`` — montant restant dû (informatif : repris
        dans le résultat pour pondérer la file de recouvrement, n'altère PAS le
        score).

    Le score combine des composantes pondérées (retard courant, historique
    client, impayés passés, relances vaines), chacune normalisée à ``[0, 1]``
    puis pondérée, et calculée en MOYENNE PONDÉRÉE sur les SEULES composantes
    présentes (les features absentes ne diluent pas le score vers 0). Plus de
    jours de retard, un retard moyen client plus élevé, plus d'impayés passés, ou
    plus de relances sans effet → score PLUS élevé (monotone). Tout reste borné à
    ``[0, 1]``.

    Si AUCUNE feature exploitable n'est fournie, le résultat est ``DEFAULT_RISK``
    avec ``used_fallback=True`` — dégradation propre. Pur, déterministe, sans
    base de données ni réseau.
    """
    feats = features or {}
    if not isinstance(feats, dict):
        feats = {}

    # Montant dû (informatif) — accepte ``montant_du`` ou ``amount``.
    amount = _coerce_float(feats.get('montant_du'))
    if amount is None:
        amount = _coerce_float(feats.get('amount'), 0.0)
    if amount is None or amount < 0:
        amount = 0.0

    factors: dict = {}
    weighted_sum = 0.0
    weight_total = 0.0
    used_any = False

    # ── Jours de retard de la facture ───────────────────────────────────────
    days_overdue = _coerce_float(feats.get('days_overdue'))
    if days_overdue is None:
        days_overdue = days_overdue_from_dates(
            feats.get('due_date'), feats.get('today'),
        )
    overdue = _ramp(days_overdue, OVERDUE_SATURATION_DAYS)
    if overdue is not None:
        weighted_sum += overdue * WEIGHT_OVERDUE
        weight_total += WEIGHT_OVERDUE
        factors['overdue'] = round(overdue, 4)
        used_any = True

    # ── Retard moyen historique du client ───────────────────────────────────
    history = _ramp(
        _coerce_float(feats.get('client_avg_delay_days')),
        CLIENT_AVG_DELAY_SATURATION_DAYS,
    )
    if history is not None:
        weighted_sum += history * WEIGHT_CLIENT_HISTORY
        weight_total += WEIGHT_CLIENT_HISTORY
        factors['client_history'] = round(history, 4)
        used_any = True

    # ── Impayés / retards tardifs passés du client ──────────────────────────
    prior_late = _ramp(
        _coerce_float(feats.get('client_prior_late_count')),
        PRIOR_LATE_SATURATION_COUNT,
    )
    if prior_late is not None:
        weighted_sum += prior_late * WEIGHT_PRIOR_LATE
        weight_total += WEIGHT_PRIOR_LATE
        factors['prior_late'] = round(prior_late, 4)
        used_any = True

    # ── Relances déjà envoyées sans paiement ────────────────────────────────
    relance = _ramp(
        _coerce_float(feats.get('relance_count')),
        RELANCE_SATURATION_COUNT,
    )
    if relance is not None:
        weighted_sum += relance * WEIGHT_RELANCE
        weight_total += WEIGHT_RELANCE
        factors['relance'] = round(relance, 4)
        used_any = True

    # ── Repli propre : aucune feature exploitable ───────────────────────────
    if not used_any:
        score = _clamp01(DEFAULT_RISK)
        return PaymentDelayResult(
            score=round(score, 4),
            band=band_for_score(score),
            amount=round(amount, 2),
            used_fallback=True,
            factors={'default': round(DEFAULT_RISK, 4)},
        )

    # Moyenne pondérée sur les SEULES composantes présentes (garde-fou contre la
    # division par zéro : ``used_any`` implique ``weight_total > 0``).
    score = weighted_sum / weight_total if weight_total > 0 else DEFAULT_RISK
    score = _clamp01(score)

    return PaymentDelayResult(
        score=round(score, 4),
        band=band_for_score(score),
        amount=round(amount, 2),
        used_fallback=False,
        factors=factors,
    )
