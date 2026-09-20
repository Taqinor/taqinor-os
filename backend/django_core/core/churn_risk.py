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

from .score_factors import facteurs_ponderes, jours, nombre, top_facteurs
from .score_params import NOM_CHURN, resoudre

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


# NTAI27 — hyperparamètres VERSIONNABLES par société. Les constantes
# ci-dessus restent LA référence (les défauts du code) ; une société qui a
# activé une version de paramètres dans le registre de modèles voit ses
# valeurs se substituer, clé par clé, via ``core.score_params.resoudre``.
# Toute clé absente de cette table est refusée : la liste blanche est ici.
DEFAUTS_PARAMS = {
    'INACTIVITY_SATURATION_DAYS': INACTIVITY_SATURATION_DAYS,
    'WEIGHT_INACTIVITY': WEIGHT_INACTIVITY,
    'WEIGHT_CONTRACT': WEIGHT_CONTRACT,
    'CONTRACT_LAPSE_SATURATION_DAYS': CONTRACT_LAPSE_SATURATION_DAYS,
    'CONTRACT_ACTIVE_RELIEF': CONTRACT_ACTIVE_RELIEF,
    'WEIGHT_SAV': WEIGHT_SAV,
    'SAV_SATURATION_TICKETS': SAV_SATURATION_TICKETS,
    'WEIGHT_INTERVENTION': WEIGHT_INTERVENTION,
    'INTERVENTION_SATURATION_DAYS': INTERVENTION_SATURATION_DAYS,
    'DEFAULT_RISK': DEFAULT_RISK,
    'BAND_THRESHOLD_MOYEN': BAND_THRESHOLD_MOYEN,
    'BAND_THRESHOLD_ELEVE': BAND_THRESHOLD_ELEVE,
}


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
    # NTAI31 — les TROIS signaux les plus déterminants, en langage clair, avec
    # leur contribution SIGNÉE au score rendu. ``factors`` garde le détail
    # normalisé de TOUTES les composantes : rien n'est perdu, on ajoute la
    # lecture humaine par-dessus.
    facteurs: list = field(default_factory=list)


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


def band_for_score(score: float, params=None) -> str:
    """Bande de risque (``faible`` / ``moyen`` / ``élevé``) d'un score ``[0, 1]``.

    NTAI27 — ``params`` (optionnel) porte les seuils résolus pour une société ;
    sans lui, les seuils du CODE s'appliquent, comportement inchangé."""
    params = params or DEFAUTS_PARAMS
    if score >= params['BAND_THRESHOLD_ELEVE']:
        return BAND_ELEVE
    if score >= params['BAND_THRESHOLD_MOYEN']:
        return BAND_MOYEN
    return BAND_FAIBLE


def churn_risk(features, *, company=None) -> ChurnRiskResult:
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
    avec ``used_fallback=True`` — dégradation propre.

    NTAI27 — ``company`` (optionnel) fait lire les poids et seuils dans la
    version d'hyperparamètres ACTIVE de cette société, avec repli sur les
    défauts du code clé par clé. Sans ``company``, la fonction reste PURE et
    déterministe (aucune base, aucun réseau) et son résultat est identique à
    celui d'avant NTAI27.
    """
    feats = features or {}
    if not isinstance(feats, dict):
        feats = {}

    # NTAI27 — seuils de CETTE société, à défaut ceux du code. Sans ``company``
    # (le cas de tous les appels existants) la fonction reste PURE : aucun
    # résolveur n'est consulté, aucune requête n'est émise.
    params = resoudre(company, NOM_CHURN, DEFAUTS_PARAMS)

    factors: dict = {}
    # NTAI31 — ``(cle, libellé clair, valeur normalisée, poids)`` de chaque
    # composante PRÉSENTE : la contribution ne peut être calculée qu'une fois
    # ``weight_total`` connu, donc on collecte d'abord.
    composantes: list = []
    weighted_sum = 0.0
    weight_total = 0.0
    used_any = False

    # ── Inactivité (jours depuis la dernière activité) ──────────────────────
    jours_inactifs = _coerce_float(feats.get('days_since_last_activity'))
    inact = _ramp(jours_inactifs, params['INACTIVITY_SATURATION_DAYS'])
    if inact is not None:
        weighted_sum += inact * params['WEIGHT_INACTIVITY']
        weight_total += params['WEIGHT_INACTIVITY']
        factors['inactivity'] = round(inact, 4)
        composantes.append((
            'inactivity',
            ('Activité récente' if not jours_inactifs
             else f'Sans activité depuis {jours(jours_inactifs)}'),
            inact, params['WEIGHT_INACTIVITY']))
        used_any = True

    # ── Contrat de maintenance ──────────────────────────────────────────────
    contract_active = feats.get('contract_active')
    lapse_days = _coerce_float(feats.get('days_since_contract_end'))
    contract_component: float | None = None
    contract_libelle = ''
    if lapse_days is not None and lapse_days > 0:
        # Contrat lapsé : risque proportionnel à l'ancienneté du lapse.
        contract_component = _ramp(
            lapse_days, params['CONTRACT_LAPSE_SATURATION_DAYS'])
        contract_libelle = ('Contrat de maintenance expiré depuis '
                            f'{jours(lapse_days)}')
    elif contract_active is True:
        # Contrat actif et non lapsé : composante de risque faible.
        contract_component = 0.0
        contract_libelle = 'Contrat de maintenance actif'
    elif contract_active is False:
        # Pas de contrat actif, lapse inconnu : risque modéré attribué.
        contract_component = 0.5
        contract_libelle = 'Aucun contrat de maintenance actif'
    if contract_component is not None:
        weighted_sum += contract_component * params['WEIGHT_CONTRACT']
        weight_total += params['WEIGHT_CONTRACT']
        factors['contract'] = round(contract_component, 4)
        composantes.append((
            'contract', contract_libelle, contract_component,
            params['WEIGHT_CONTRACT']))
        used_any = True

    # ── Tickets SAV ouverts ─────────────────────────────────────────────────
    tickets = _coerce_float(feats.get('open_sav_tickets'))
    sav = _ramp(tickets, params['SAV_SATURATION_TICKETS'])
    if sav is not None:
        weighted_sum += sav * params['WEIGHT_SAV']
        weight_total += params['WEIGHT_SAV']
        factors['sav'] = round(sav, 4)
        composantes.append((
            'sav',
            ('Aucun ticket SAV ouvert' if not tickets
             else f'{nombre(tickets)} ticket(s) SAV non résolu(s)'),
            sav, params['WEIGHT_SAV']))
        used_any = True

    # ── Ancienneté de la dernière intervention ──────────────────────────────
    age_intervention = _coerce_float(feats.get('last_intervention_age'))
    interv = _ramp(age_intervention, params['INTERVENTION_SATURATION_DAYS'])
    if interv is not None:
        weighted_sum += interv * params['WEIGHT_INTERVENTION']
        weight_total += params['WEIGHT_INTERVENTION']
        factors['intervention'] = round(interv, 4)
        composantes.append((
            'intervention',
            f'Dernière intervention terrain il y a {jours(age_intervention)}',
            interv, params['WEIGHT_INTERVENTION']))
        used_any = True

    # ── Repli propre : aucune feature exploitable ───────────────────────────
    if not used_any:
        score = _clamp01(params['DEFAULT_RISK'])
        return ChurnRiskResult(
            score=round(score, 4),
            band=band_for_score(score, params),
            used_fallback=True,
            factors={'default': round(params['DEFAULT_RISK'], 4)},
            facteurs=[],
        )

    # Moyenne pondérée sur les SEULES composantes présentes (les features
    # absentes ne diluent pas le score vers 0).
    score = (weighted_sum / weight_total if weight_total > 0
             else params['DEFAULT_RISK'])

    # NTAI31 — contributions des composantes pondérées (leur somme REDONNE le
    # score ci-dessus, avant bonus de fidélité et bornage).
    facteurs = facteurs_ponderes(composantes, weight_total, limite=None)

    # Bonus de fidélité : un contrat explicitement actif RÉDUIT le risque.
    if contract_active is True and (lapse_days is None or lapse_days <= 0):
        relief = params['CONTRACT_ACTIVE_RELIEF']
        score -= relief
        factors['active_relief'] = -round(relief, 4)
        facteurs.append(_facteur_fidelite(relief))

    score = _clamp01(score)

    return ChurnRiskResult(
        score=round(score, 4),
        band=band_for_score(score, params),
        used_fallback=False,
        factors=factors,
        facteurs=top_facteurs(facteurs),
    )


def _facteur_fidelite(relief):
    """Le bonus de fidélité, exprimé comme un facteur NÉGATIF (il rassure)."""
    from .score_factors import facteur
    return facteur(
        'active_relief', 'Contrat de maintenance actif (fidélité)', -relief)
