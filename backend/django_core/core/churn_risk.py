"""FG363 — Score de churn / risque client, fondation pure.

Comme :mod:`core.anomaly`, :mod:`core.forecast` et :mod:`core.win_probability`,
ce module reste une couche de BASE — contrat import-linter
``core-foundation-is-a-base-layer`` : il n'importe AUCUNE app métier. L'app
appelante (crm / sav / reporting…) extrait les CARACTÉRISTIQUES d'un client via
SA couche selectors (jours depuis la dernière activité, contrat actif ou non,
tickets SAV ouverts, âge de la dernière intervention…) et passe un simple dict
de features à :func:`churn_risk` ; core fournit uniquement le moteur de scoring
générique et ne touche jamais la base ni le réseau (librairie standard seulement).

Le score sert l'OUTREACH PROACTIF : repérer les clients maintenance/SAV à risque
(sans activité récente, contrat de maintenance lapsé, tickets SAV non résolus
qui traînent) AVANT qu'ils ne partent, pour relancer au bon moment. Le résultat
est un score de risque borné à ``[0, 1]`` (0 = client fidèle, 1 = très à risque)
et une BANDE lisible (``faible`` / ``moyen`` / ``élevé``).

Si les features ne contiennent rien d'exploitable, le score DÉGRADE PROPREMENT
vers un risque NEUTRE de base (``DEFAULT_RISK``) avec ``used_fallback=True`` —
l'appelant garde un résultat utilisable plutôt qu'une erreur. Pur, déterministe,
sans base de données ni réseau.
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

# ── Inactivité : jours depuis la dernière activité client ────────────────────
# Au-delà de ce nombre de jours, l'inactivité « sature » (contribution maximale).
INACTIVITY_SATURATION_DAYS = 365.0
# Poids de la composante inactivité dans le score final.
WEIGHT_INACTIVITY = 0.40

# ── Contrat de maintenance ───────────────────────────────────────────────────
# Un contrat actif RASSURE (risque réduit) ; un contrat lapsé depuis longtemps
# alarme. Poids de la composante contrat.
WEIGHT_CONTRACT = 0.30
# Bonus de risque (additif après pondération) quand le contrat est lapsé. On
# module ce bonus par l'ancienneté du lapse via ``CONTRACT_LAPSE_SATURATION_DAYS``.
CONTRACT_LAPSE_SATURATION_DAYS = 180.0
# Réduction de risque quand un contrat est explicitement ACTIF (fidélité).
CONTRACT_ACTIVE_RELIEF = 0.10

# ── Tickets SAV ouverts non résolus ──────────────────────────────────────────
# Des tickets SAV ouverts qui s'accumulent = insatisfaction = risque de départ.
WEIGHT_SAV = 0.20
# Au-delà de ce nombre de tickets ouverts, la contribution sature.
SAV_SATURATION_TICKETS = 5.0

# ── Ancienneté de la dernière intervention maintenance ───────────────────────
# Un client qu'on n'a pas vu depuis longtemps sur le terrain dérive. Poids.
WEIGHT_INTERVENTION = 0.10
INTERVENTION_SATURATION_DAYS = 540.0


@dataclass
class ChurnRiskResult:
    """Résultat de :func:`churn_risk`.

    ``score`` est le score de churn final borné à ``[0, 1]`` (0 = fidèle, 1 =
    très à risque). ``band`` est la bande lisible (``faible`` / ``moyen`` /
    ``élevé``). ``used_fallback`` vaut ``True`` si AUCUNE feature exploitable
    n'a été fournie (le score retombe sur ``DEFAULT_RISK``). ``factors`` détaille
    chaque contribution (explicabilité / tests / UI)."""

    score: float
    band: str
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
    transformer une quantité « plus c'est grand, plus c'est risqué » (jours
    d'inactivité, nombre de tickets…) en contribution normalisée."""
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


def churn_risk(features) -> ChurnRiskResult:
    """Score de churn ``[0, 1]`` d'un client à partir de ses features.

    ``features`` : un mapping (dict) fourni par l'app appelante depuis SES
    selectors — JAMAIS un import d'app métier ici. Clés reconnues (toutes
    optionnelles) :

      * ``days_since_last_activity`` — jours depuis la dernière activité/contact ;
      * ``contract_active``          — booléen ; contrat de maintenance actif ;
      * ``days_since_contract_end``  — jours depuis l'expiration du contrat
        (contrat lapsé) ;
      * ``open_sav_tickets``         — nombre de tickets SAV ouverts non résolus ;
      * ``last_intervention_age``    — jours depuis la dernière intervention
        terrain.

    Le score combine des composantes pondérées (inactivité, contrat, SAV,
    intervention), chacune normalisée à ``[0, 1]`` puis pondérée. Un contrat
    explicitement ACTIF réduit le risque ; un contrat lapsé l'augmente
    proportionnellement à l'ancienneté du lapse. Plus d'inactivité, un contrat
    lapsé depuis plus longtemps, ou plus de tickets SAV ouverts → score PLUS
    élevé (monotone). Tout reste borné à ``[0, 1]``.

    Si AUCUNE feature exploitable n'est fournie, le résultat est ``DEFAULT_RISK``
    avec ``used_fallback=True`` — dégradation propre. Pur, déterministe, sans
    base de données ni réseau.
    """
    feats = features or {}
    if not isinstance(feats, dict):
        feats = {}

    factors: dict = {}
    weighted_sum = 0.0
    weight_total = 0.0
    used_any = False

    # ── Inactivité (jours depuis la dernière activité) ──────────────────────
    inact = _ramp(
        _coerce_float(feats.get('days_since_last_activity')),
        INACTIVITY_SATURATION_DAYS,
    )
    if inact is not None:
        weighted_sum += inact * WEIGHT_INACTIVITY
        weight_total += WEIGHT_INACTIVITY
        factors['inactivity'] = round(inact, 4)
        used_any = True

    # ── Contrat de maintenance ──────────────────────────────────────────────
    contract_active = feats.get('contract_active')
    lapse_days = _coerce_float(feats.get('days_since_contract_end'))
    contract_component: float | None = None
    if lapse_days is not None and lapse_days > 0:
        # Contrat lapsé : risque proportionnel à l'ancienneté du lapse.
        contract_component = _ramp(lapse_days, CONTRACT_LAPSE_SATURATION_DAYS)
    elif contract_active is True:
        # Contrat actif et non lapsé : composante de risque faible.
        contract_component = 0.0
    elif contract_active is False:
        # Pas de contrat actif, lapse inconnu : risque modéré attribué.
        contract_component = 0.5
    if contract_component is not None:
        weighted_sum += contract_component * WEIGHT_CONTRACT
        weight_total += WEIGHT_CONTRACT
        factors['contract'] = round(contract_component, 4)
        used_any = True

    # ── Tickets SAV ouverts ─────────────────────────────────────────────────
    sav = _ramp(
        _coerce_float(feats.get('open_sav_tickets')),
        SAV_SATURATION_TICKETS,
    )
    if sav is not None:
        weighted_sum += sav * WEIGHT_SAV
        weight_total += WEIGHT_SAV
        factors['sav'] = round(sav, 4)
        used_any = True

    # ── Ancienneté de la dernière intervention ──────────────────────────────
    interv = _ramp(
        _coerce_float(feats.get('last_intervention_age')),
        INTERVENTION_SATURATION_DAYS,
    )
    if interv is not None:
        weighted_sum += interv * WEIGHT_INTERVENTION
        weight_total += WEIGHT_INTERVENTION
        factors['intervention'] = round(interv, 4)
        used_any = True

    # ── Repli propre : aucune feature exploitable ───────────────────────────
    if not used_any:
        score = _clamp01(DEFAULT_RISK)
        return ChurnRiskResult(
            score=round(score, 4),
            band=band_for_score(score),
            used_fallback=True,
            factors={'default': round(DEFAULT_RISK, 4)},
        )

    # Moyenne pondérée sur les SEULES composantes présentes (les features
    # absentes ne diluent pas le score vers 0).
    score = weighted_sum / weight_total if weight_total > 0 else DEFAULT_RISK

    # Bonus de fidélité : un contrat explicitement actif RÉDUIT le risque.
    if contract_active is True and (lapse_days is None or lapse_days <= 0):
        score -= CONTRACT_ACTIVE_RELIEF
        factors['active_relief'] = -round(CONTRACT_ACTIVE_RELIEF, 4)

    score = _clamp01(score)

    return ChurnRiskResult(
        score=round(score, 4),
        band=band_for_score(score),
        used_fallback=False,
        factors=factors,
    )
