"""PV69/70/72/73 — étude bancable v1 : `Devis.etude_params['simulation']`.

Orchestrateur PUR (aucune écriture DB, aucun changement de statut — règle #4)
qui agrège, par zone (pan de toiture), le productible PVGIS et une année météo
type (TMY) déjà offline-safe (``apps.parametres.pvgis.fetch_productible`` /
``apps.ventes.weather_feed.fetch_irradiance_tmy``) puis applique l'arbre de
pertes (`apps.ventes.solar_design.simulate_bankable_yield`) pour produire un
ratio de performance (PR) et les scénarios P50/P90/P75.

PV70 ajoute le pont vers la matrice d'ombrage 12×24 de shadingUi.ts
(``factors[mois][heure] ∈ [0,1]``, 1 = plein soleil — convention WJ19/WJ21) :
quand une zone en porte une (fournie directement ou lue dans
``Devis.roof_layout``), la perte annuelle d'ombrage est une moyenne PONDÉRÉE
PRODUCTION (jamais une moyenne plate) — chaque cellule mois×heure pèse selon
la part mensuelle réelle (TMY) × la forme horaire ciel clair
(:func:`~apps.ventes.solar_design.clearsky_hourly_irradiance`). Sans matrice,
repli sur :func:`~apps.ventes.solar_design.shading_analysis` (horizon/obstacles
qualitatifs) puis, à défaut, aucun ombrage.

PV72 ferme la chaîne complète : autoconsommation horaire
(``hourly_self_consumption`` sur les courbes charge/production 288 points —
charge fournie ou synthétisée depuis la conso du lead, production issue de
:func:`production_horaire_zone`), net-metering du surplus
(``net_metering_savings``, tarifs par tranche toujours ceux DÉFAUT « à
confirmer » de ``solar_design`` — jamais durcis ici), puissance souscrite
recommandée (``optimize_subscribed_power``, UNIQUEMENT en industriel/
commercial — bloc minimal honnête ailleurs), dégradation garantie
(``module_degradation_curve``) et projection 25 ans VAN/TRI
(``tariff_escalation_projection``, coût initial = ``Devis.total_ht``).

PV73 met les deux fetchers PVGIS derrière un cache SYSTÈME (``core/cache``,
``company=None`` — la physique d'un point GPS ne dépend pas du tenant qui
consulte) : productible 6 h, TMY 7 jours. ``force_refresh`` court-circuite la
LECTURE mais réécrit toujours l'entrée.

ADDITIF STRICT (PV69/règle #2) : ce module ne touche JAMAIS les clés
historiques d'``etude_params`` (``production_annuelle``, ``economies_annuelles``,
``payback``…) — la table 5 villes QX38 reste la source CANONIQUE pour
l'écran/le PDF. ``run_bankable_study`` se contente de RENVOYER un dict prêt à
être posé, par l'appelant, dans ``etude_params['simulation']`` (PV74, hors de
ce fichier) — jamais un ``devis.save()`` ici.

Le dict renvoyé suit EXACTEMENT le contrat
``apps/ventes/contract_samples/simulation.json`` (PACT10) : chaque sous-bloc
n'expose QUE les clés du contrat, jamais les clés internes des fonctions
``solar_design`` (ex. ``applied_losses``, ``z_p90`` de
:func:`~apps.ventes.solar_design.simulate_bankable_yield` sont absorbées ici,
pas recopiées).

Hors de ``quote_engine`` (règle #4) : ce module ne rend AUCUN PDF, ne change
AUCUN statut de devis, n'expose AUCUN prix d'achat/marge.
"""
from __future__ import annotations

import datetime as _dt

from apps.ventes.solar_design import (
    DEFAULT_LOSS_FACTORS,
    TYPICAL_LOAD_PROFILE_COMMERCIAL,
    TYPICAL_LOAD_PROFILE_RESIDENTIAL,
    hourly_self_consumption,
    module_degradation_curve,
    net_metering_savings,
    optimize_subscribed_power,
    simulate_bankable_yield,
    tariff_escalation_projection,
)

# Version du schéma `etude_params['simulation']` — incrémentée à tout
# changement de forme (jamais de mutation silencieuse d'un schéma déjà posé).
SIMULATION_VERSION = 1


def _num(value, default=0.0):
    """Float tolérant : illisible/``None`` → ``default`` (jamais d'exception)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _maybe_num(value):
    """Float tolérant qui préserve ``None`` (jamais un 0.0 fabriqué)."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_z(value):
    """Horodatage ISO-8601 UTC suffixé ``Z`` (forme du contrat PACT10)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=_dt.timezone.utc)
    return value.astimezone(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _company_settings(devis):
    """Réglages Tarification & ROI (PVGIS + tarifs) de la société du devis.

    Import paresseux (``parametres`` est une app fondation exemptée de la
    frontière cross-app — CLAUDE.md) : on reste aligné sur le style du reste
    de ``apps/ventes`` (imports d'``apps.parametres`` faits au point d'usage).
    """
    from apps.parametres.models_tariff import TariffSettings
    return TariffSettings.get(company=getattr(devis, 'company', None))


def _resolved_tilt_azimuth(settings, tilt, azimuth):
    """Résout tilt/azimut EFFECTIFS (défauts société appliqués si absents).

    Nécessaire pour une clé de cache SYSTÈME correcte (PV73) : deux sociétés
    aux défauts différents qui appellent toutes deux avec ``tilt=None`` ne
    doivent JAMAIS collisionner sur la même entrée — on résout donc la valeur
    RÉELLEMENT utilisée avant de bâtir la clé, exactement comme le ferait
    ``apps.parametres.pvgis.fetch_productible`` en interne.
    """
    t = tilt if tilt is not None else getattr(settings, 'inclinaison_defaut_deg', 30)
    a = azimuth if azimuth is not None else getattr(settings, 'azimut_defaut_deg', 0)
    try:
        t = float(t)
    except (TypeError, ValueError):
        t = 30.0
    try:
        a = float(a)
    except (TypeError, ValueError):
        a = 0.0
    return t, a


def _productible_cache_key(lat, lon, tilt, azimuth):
    """Clé de cache système PV73 — arrondie pour regrouper les points voisins."""
    return f'pvgis:prod:{lat:.3f}:{lon:.3f}:{tilt:.0f}:{azimuth:.0f}'


def _tmy_cache_key(lat, lon):
    """Clé de cache système PV73 (TMY, pas de tilt/azimut — climat du point)."""
    return f'pvgis:tmy:{lat:.3f}:{lon:.3f}'


# PV73 — TTL du cache PVGIS SYSTÈME (core/cache, company=None — partagé entre
# TOUTES les sociétés : la physique du point GPS ne dépend pas du tenant).
# Productible : 6 h (assez court pour absorber une correction PVGIS amont,
# assez long pour épargner un aller-retour réseau par relance d'étude).
_PVGIS_PROD_CACHE_TTL_S = 6 * 60 * 60
# TMY (climatologie) : 7 jours — un profil météo type ne change pas d'un jour
# à l'autre, contrairement au productible ponctuel.
_PVGIS_TMY_CACHE_TTL_S = 7 * 24 * 60 * 60


def _fetch_productible(settings, lat, lon, *, peakpower_kwc=1.0,
                       tilt=None, azimuth=None, force_refresh=False):
    """Point de bascule UNIQUE vers PVGIS productible — cache SYSTÈME (PV73).

    ``force_refresh=True`` court-circuite la LECTURE du cache (on force un
    fetch réel) mais réécrit tout de même l'entrée ensuite (le prochain appel
    normal profite du résultat frais). Coordonnées illisibles → aucun cache
    (le fetcher lui-même retombe sur son repli manuel, jamais d'exception ici).
    """
    from apps.parametres.pvgis import fetch_productible
    from core import cache as tenant_cache

    try:
        latf = float(lat)
        lonf = float(lon)
    except (TypeError, ValueError):
        return fetch_productible(settings, lat, lon, peakpower_kwc=peakpower_kwc,
                                 tilt=tilt, azimuth=azimuth)

    tilt_r, az_r = _resolved_tilt_azimuth(settings, tilt, azimuth)
    key = _productible_cache_key(latf, lonf, tilt_r, az_r)

    if not force_refresh:
        cached = tenant_cache.get(None, key)
        if cached is not None:
            return cached

    result = fetch_productible(settings, lat, lon, peakpower_kwc=peakpower_kwc,
                               tilt=tilt, azimuth=azimuth)
    tenant_cache.set(None, key, result, _PVGIS_PROD_CACHE_TTL_S)
    return result


def _fetch_tmy(lat, lon, *, force_refresh=False):
    """Point de bascule UNIQUE vers PVGIS TMY — cache SYSTÈME (PV73).

    Même politique que :func:`_fetch_productible` (``force_refresh`` bypass la
    lecture, réécrit toujours) avec une clé plus courte (pas de tilt/azimut —
    la TMY est une propriété du point GPS, pas de l'orientation des modules).
    """
    from apps.ventes.weather_feed import fetch_irradiance_tmy
    from core import cache as tenant_cache

    try:
        latf = float(lat)
        lonf = float(lon)
    except (TypeError, ValueError):
        return fetch_irradiance_tmy(lat, lon)

    key = _tmy_cache_key(latf, lonf)

    if not force_refresh:
        cached = tenant_cache.get(None, key)
        if cached is not None:
            return cached

    result = fetch_irradiance_tmy(lat, lon)
    tenant_cache.set(None, key, result, _PVGIS_TMY_CACHE_TTL_S)
    return result


def _zone_monthly_share(tmy_result):
    """Part mensuelle de l'irradiation (12 valeurs, somme = 1) depuis un TMY.

    Repli parts égales (1/12 chacune) si le profil est absent/illisible — le
    TMY est déjà offline-safe (repli climatique), ce champ n'est donc JAMAIS
    vide, seulement moins précis hors-ligne.
    """
    monthly = (tmy_result or {}).get('irradiance_mensuelle_kwh_m2')
    if not monthly or len(monthly) != 12:
        return [1.0 / 12.0] * 12
    total = sum(max(0.0, _num(v)) for v in monthly)
    if total <= 0:
        return [1.0 / 12.0] * 12
    return [max(0.0, _num(v)) / total for v in monthly]


def _valid_matrix(value):
    """Valide une matrice 12×24 (listes de listes) — sinon ``None`` (tolérant).

    Lecture TOLÉRANTE par construction : la matrice PV71 (sérialisation côté
    web) n'existe pas encore sur tous les devis, et une forme mal formée ne
    doit jamais faire échouer l'étude, seulement retomber sur le repli
    ``shading_analysis``/aucun ombrage.
    """
    if not isinstance(value, list) or len(value) != 12:
        return None
    for row in value:
        if not isinstance(row, list) or len(row) != 24:
            return None
    return value


def _zone_shading_matrix(devis, zone, index):
    """Résout la matrice 12×24 d'une zone : zone fournie → `Devis.roof_layout`
    (par zone, appariée sur ``label`` puis sur l'index) → repli global du
    layout → ``None`` (pas de matrice).

    Clé tolérante : accepte ``shading12x24`` au niveau zone ET au niveau
    global du layout (PV71 choisit encore où la matrice voyage côté web).
    """
    matrix = _valid_matrix((zone or {}).get('shading12x24'))
    if matrix is not None:
        return matrix

    layout = getattr(devis, 'roof_layout', None) or {}
    if not isinstance(layout, dict):
        return None

    layout_zones = layout.get('zones')
    if isinstance(layout_zones, list):
        label = (zone or {}).get('label')
        if label:
            for lz in layout_zones:
                if isinstance(lz, dict) and lz.get('label') == label:
                    matrix = _valid_matrix(lz.get('shading12x24'))
                    if matrix is not None:
                        return matrix
        if 0 <= index < len(layout_zones) and isinstance(layout_zones[index], dict):
            matrix = _valid_matrix(layout_zones[index].get('shading12x24'))
            if matrix is not None:
                return matrix

    return _valid_matrix(layout.get('shading12x24'))


def _hour_weight_shape():
    """Poids horaire (24 valeurs, somme = 1) — forme ciel clair centrée midi.

    Réutilise :func:`~apps.ventes.solar_design.clearsky_hourly_irradiance`
    (jamais une nouvelle forme inventée) : une heure de production réelle pèse
    plus qu'une heure d'aube/crépuscule dans la moyenne pondérée de pertes.
    """
    from apps.ventes.solar_design import clearsky_hourly_irradiance
    shape = clearsky_hourly_irradiance(1.0)
    total = sum(shape) or 1.0
    return [v / total for v in shape]


def _zone_production_weights(monthly_share):
    """Matrice de poids 12×24 (somme = 1) : part mensuelle réelle (TMY) × forme
    horaire ciel clair — jamais une moyenne plate mois par mois NI heure par
    heure."""
    hour_shape = _hour_weight_shape()
    return [[m_share * h for h in hour_shape] for m_share in monthly_share]


def _weighted_shading_loss_pct(matrix, weights):
    """Perte d'ombrage annuelle (%) pondérée PRODUCTION depuis une matrice 12×24.

    ``matrix[m][h]`` ∈ [0, 1] = facteur de production retenu à cette cellule
    (1 = plein soleil, 0 = totalement masqué — convention shadingUi.ts). Chaque
    cellule pèse selon ``weights`` (part mensuelle réelle × forme horaire ciel
    clair) : une heure creuse masquée compte donc peu dans la moyenne — JAMAIS
    une moyenne plate sur les 288 cellules. Valeurs illisibles/hors [0,1] sont
    bornées, jamais rejetées.
    """
    total_w = 0.0
    total_loss_w = 0.0
    for m in range(min(12, len(matrix or []))):
        row = matrix[m] or []
        wrow = weights[m] if m < len(weights) else [0.0] * 24
        for h in range(min(24, len(row))):
            factor = min(1.0, max(0.0, _num(row[h], 1.0)))
            loss = 1.0 - factor
            w = wrow[h] if h < len(wrow) else 0.0
            total_loss_w += loss * w
            total_w += w
    if total_w <= 0:
        return 0.0
    return round(total_loss_w / total_w * 100.0, 2)


def _zone_shading(devis, zone, index, monthly_share):
    """Perte d'ombrage annuelle (%) d'une zone + matrice résolue (ou ``None``).

    Ordre : matrice 12×24 réelle (moyenne pondérée production) → repli
    ``shading_analysis`` (horizon/obstacles qualitatifs, zone['horizon_profile']
    / zone['obstacles']) → aucun ombrage (0 %) si rien n'est fourni. La matrice
    PVGIS-horizon (« printhorizon ») est EXPLICITEMENT hors v1 (forme non
    vérifiée par le founder) — jamais appelée ici.
    """
    matrix = _zone_shading_matrix(devis, zone, index)
    if matrix is not None:
        weights = _zone_production_weights(monthly_share)
        return _weighted_shading_loss_pct(matrix, weights), matrix

    horizon = (zone or {}).get('horizon_profile')
    obstacles = (zone or {}).get('obstacles')
    if horizon or obstacles:
        from apps.ventes.solar_design import shading_analysis
        result = shading_analysis(horizon, obstacles)
        return _num(result.get('annual_loss_pct')), None

    return 0.0, None


def production_horaire_zone(zone, matrix=None):
    """PV70 — courbe de production horaire d'une zone (12 mois × 24 h = 288 pts).

    Tuile un jour-type mensuel (forme ciel clair,
    :func:`~apps.ventes.solar_design.clearsky_hourly_irradiance`) sur les 12
    mois — répartition mensuelle ÉGALE (1/12 du total annuel), faute d'un
    profil mensuel par zone accessible à cet appel isolé — puis dérate chaque
    cellule par ``matrix`` (12×24, facteurs [0,1], convention shadingUi.ts)
    quand fournie. ``zone`` est le dict ENRICHI (issu de ``run_bankable_study``,
    porte ``base_production_kwh``) — sert de courbe de production à
    :func:`~apps.ventes.solar_design.hourly_self_consumption` (PV72).

    ``base_production_kwh`` absent/≤ 0 → 288 zéros (jamais d'exception).
    """
    base = _num((zone or {}).get('base_production_kwh'), 0.0)
    if base <= 0:
        return [0.0] * 288
    monthly_kwh = base / 12.0
    hour_shape = _hour_weight_shape()
    curve = []
    for m in range(12):
        row = matrix[m] if matrix and m < len(matrix) else None
        for h in range(24):
            factor = 1.0
            if row and h < len(row):
                factor = min(1.0, max(0.0, _num(row[h], 1.0)))
            curve.append(round(monthly_kwh * hour_shape[h] * factor, 5))
    return curve


def _zone_base_production(settings, zone, *, devis=None, index=0,
                          force_refresh=False):
    """Contexte productible d'une zone (pan) : PVGIS + TMY, jamais d'exception.

    Renvoie ``{base_production_kwh, source, monthly_share,
    shading_annual_loss_pct, shading_matrix, warnings}``. ``source`` vaut
    ``'manual'`` dès qu'AU MOINS un des deux fetchers est retombé en repli
    hors-ligne (reporting conservateur : ``'pvgis'`` garantit que TOUT le
    calcul de la zone est ancré sur des données réseau réelles).
    """
    zone = zone or {}
    lat = zone.get('lat')
    lon = zone.get('lon')
    kwc = _num(zone.get('kwc'))
    tilt = zone.get('tilt')
    azimuth = zone.get('azimuth')
    label = zone.get('label') or '?'

    prod_res = _fetch_productible(
        settings, lat, lon, peakpower_kwc=1.0, tilt=tilt, azimuth=azimuth,
        force_refresh=force_refresh) or {}
    tmy_res = _fetch_tmy(lat, lon, force_refresh=force_refresh) or {}

    productible = _num(prod_res.get('productible_kwh_kwc'))
    base_kwh = round(productible * kwc, 1)

    warnings = []
    if prod_res.get('source') != 'pvgis' or tmy_res.get('source') != 'pvgis':
        source = 'manual'
        reason = prod_res.get('reason') or tmy_res.get('reason')
        if reason:
            warnings.append(f"zone {label} : source dégradée ({reason})")
    else:
        source = 'pvgis'

    monthly_share = _zone_monthly_share(tmy_res)
    shading_pct, shading_matrix = _zone_shading(devis, zone, index, monthly_share)

    return {
        'base_production_kwh': base_kwh,
        'source': source,
        'monthly_share': monthly_share,
        'shading_annual_loss_pct': shading_pct,
        'shading_matrix': shading_matrix,
        'warnings': warnings,
    }


def _pr_block(base_production_kwh, kwc_total, loss_factors):
    """Bloc ``pr`` du contrat (clés EXACTES) depuis ``simulate_bankable_yield``.

    Absorbe les clés internes de ``simulate_bankable_yield`` (``applied_losses``,
    ``z_p90``, ``z_p75``, ``base_production_kwh``, ``warnings``) qui n'ont pas
    de place dans le contrat — seules ``warnings`` remonte, fondue dans les
    avertissements globaux de l'étude par l'appelant.
    """
    sim = simulate_bankable_yield(
        base_production_kwh, loss_factors=loss_factors, kwc=kwc_total)
    loss_breakdown_pct = {
        poste: detail['pct'] for poste, detail in sim['loss_breakdown'].items()
    }
    pr = {
        'performance_ratio': sim['performance_ratio'],
        'total_loss_pct': sim['total_loss_pct'],
        'loss_breakdown': loss_breakdown_pct,
        'p50_kwh': sim['p50_kwh'],
        'p90_kwh': sim['p90_kwh'],
        'p75_kwh': sim['p75_kwh'],
        'annual_variability': sim['annual_variability'],
        'specific_yield_kwh_kwc': sim['specific_yield_kwh_kwc'],
    }
    return pr, sim['warnings']


def _load_profile_key(devis):
    """Profil de charge type à utiliser : commercial (C&I) ou résidentiel."""
    mode = getattr(devis, 'mode_installation', None)
    return 'commercial' if mode in ('industriel', 'commercial') else 'residential'


def _daily_load_kwh_from_devis(devis):
    """Charge journalière (kWh/j) dérivée de la conso mensuelle du lead.

    Source UNIQUE : ``Lead.conso_mensuelle_kwh`` (kWh/mois → kWh/j, ×12÷365).
    Absent (pas de lead, ou lead sans conso saisie) → 0.0 : le bloc
    ``self_consumption`` reste structurellement complet (jamais d'exception)
    mais honnêtement à 0 plutôt qu'un chiffre inventé depuis un montant MAD
    (aucune inversion fiable du barème ONEE progressif/sélectif sans le
    modèle tarifaire complet — mieux vaut 0 documenté qu'un prix moyen faux).
    """
    lead = getattr(devis, 'lead', None)
    conso = getattr(lead, 'conso_mensuelle_kwh', None) if lead is not None else None
    if conso is None:
        return 0.0
    return _num(conso) * 12.0 / 365.0


def _tiled_load_curve(daily_load_kwh, profile_key):
    """Courbe de charge 288 points (12 mois × jour-type 24 h, même résolution
    que :func:`production_horaire_zone`) depuis une charge journalière.

    Réutilise les MÊMES profils publics que l'auto-synthèse propre à
    ``hourly_self_consumption`` (``TYPICAL_LOAD_PROFILE_RESIDENTIAL`` /
    ``_COMMERCIAL``) — pas une forme inventée — mais les tuile sur 12 mois
    (répartition mensuelle égale, faute de courbe de charge mensuelle réelle)
    pour matcher la résolution de la courbe de production agrégée, plutôt que
    le jour-type unique (24 pts) que produirait l'auto-synthèse interne, ce
    qui tronquerait la production réelle à un seul jour.
    """
    annual = _num(daily_load_kwh, 0.0) * 365.0
    if annual <= 0:
        return [0.0] * 288
    profile = TYPICAL_LOAD_PROFILE_COMMERCIAL if profile_key == 'commercial' \
        else TYPICAL_LOAD_PROFILE_RESIDENTIAL
    total_shape = sum(profile) or 1.0
    monthly = annual / 12.0
    curve = []
    for _ in range(12):
        curve.extend(round(monthly * (p / total_shape), 5) for p in profile)
    return curve


def _hourly_flows(load_curve, production_curve):
    """Aligne charge/production heure par heure → surplus injecté / import réseau.

    Même règle que ``hourly_self_consumption`` (autoconsommé[h] =
    min(charge[h], production[h])), mais renvoie les SÉRIES complètes :
    ``net_metering_savings`` et ``optimize_subscribed_power`` raisonnent heure
    par heure, pas seulement en agrégat annuel.
    """
    load = [max(0.0, _num(v)) for v in (load_curve or [])]
    prod = [max(0.0, _num(v)) for v in (production_curve or [])]
    n = min(len(load), len(prod))
    surplus = []
    imported = []
    for i in range(n):
        sc = load[i] if load[i] < prod[i] else prod[i]
        surplus.append(prod[i] - sc)
        imported.append(load[i] - sc)
    return load[:n], prod[:n], surplus, imported


def _subscribed_power_block(devis, load_curve, production_curve):
    """Bloc ``subscribed_power`` du contrat — UNIQUEMENT calculé en industriel/
    commercial (règle métier : la notion de puissance souscrite optimisée ne
    s'applique pas au résidentiel/agricole). La clé du contrat est TOUJOURS
    émise (conformité au jeu de clés) ; hors C&I, un bloc minimal honnête
    (valeurs ``None``) plutôt qu'un chiffre hors-sujet.
    """
    mode = getattr(devis, 'mode_installation', None)
    if mode not in ('industriel', 'commercial'):
        return (
            {
                'peak_reduction_pct': None,
                'recommended_subscribed': None,
                'annual_saving': None,
            },
            [],
        )

    current_subscribed_kva = None
    etude = getattr(devis, 'etude_params', None) or {}
    for key in ('puissance_souscrite_kva', 'puissance_souscrite', 'subscribed_kva'):
        if etude.get(key) is not None:
            current_subscribed_kva = etude.get(key)
            break

    result = optimize_subscribed_power(
        load_curve=load_curve, production_curve=production_curve,
        current_subscribed_kva=current_subscribed_kva)
    block = {
        'peak_reduction_pct': result['peak_reduction_pct'],
        'recommended_subscribed': result['recommended_subscribed'],
        'annual_saving': result['annual_saving'],
    }
    return block, result['warnings']


def _annual_savings_year1(settings, self_consumed_kwh, classe):
    """Économie annuelle year-1 de l'énergie AUTOCONSOMMÉE, ancrée sur le prix
    marginal réellement payé (``apps.parametres.tariff.effective_kwh_price`` —
    même logique que ``tariff_service.compute_roi``), jamais un tarif moyen
    inventé. Le surplus compensé est valorisé À PART par
    ``net_metering_savings`` (additionné par l'appelant) : les deux montants
    ne se recouvrent jamais (énergie autoconsommée vs énergie injectée).
    """
    if self_consumed_kwh <= 0:
        return 0.0
    from apps.parametres import tariff as tariff_service
    conso_mensuelle_repr = self_consumed_kwh / 12.0
    prix = tariff_service.effective_kwh_price(settings, conso_mensuelle_repr, classe)
    return float(prix) * self_consumed_kwh


def run_bankable_study(devis, *, zones, load_curve=None, force_refresh=False,
                       computed_at=None):
    """PV69/70/72 — chaîne complète : productible → ombrage → PR → autoconso →
    net-metering → puissance souscrite → dégradation → projection 25 ans.

    Paramètres
    ----------
    devis : ``Devis`` — résout la société (réglages PVGIS + tarifs), la
        matrice d'ombrage 12×24 (``devis.roof_layout``, PV70, repli tolérant),
        la conso du lead (``devis.lead.conso_mensuelle_kwh``, PV72, repli 0) et
        le coût initial (``devis.total_ht``, PV72) ; jamais écrit (aucun
        ``devis.save()`` ici).
    zones : liste de ``{label, lat, lon, tilt, azimuth, kwc, shading12x24?,
        horizon_profile?, obstacles?}`` — un pan de toiture par élément. Une
        zone illisible (kWc/coords manquants) ne fait jamais échouer l'étude :
        elle contribue 0 kWh, jamais d'exception.
    load_curve : courbe de charge horaire explicite (n'importe quelle
        longueur) ; absente → synthétisée depuis la conso du lead, tuilée sur
        288 points (12 mois × jour-type) pour matcher la courbe de production
        agrégée (voir :func:`_tiled_load_curve`).
    force_refresh : réservé à PV73 (cache PVGIS système) — sans effet tant que
        le cache n'est pas branché (comportement inchangé).
    computed_at : ``datetime`` figé pour un rendu déterministe (tests) ;
        défaut = maintenant (``django.utils.timezone.now``, appelé ici pour
        rester du code applicatif, pas le module PUR ``solar_design``).

    Retourne un dict JSON-sérialisable conforme au contrat PACT10 COMPLET :
    ``{version, computed_at, source, zones, pr, self_consumption,
    net_metering, subscribed_power, degradation, projection_25y, warnings}``.
    Ne lève JAMAIS.
    """
    if computed_at is None:
        from django.utils import timezone
        computed_at = timezone.now()

    warnings = []
    settings = _company_settings(devis)

    zones_out = []
    zone_curves = []
    base_total = 0.0
    kwc_total = 0.0
    sources = set()

    for index, zone in enumerate(zones or []):
        zone = zone or {}
        ctx = _zone_base_production(
            settings, zone, devis=devis, index=index, force_refresh=force_refresh)
        kwc = _num(zone.get('kwc'))
        zones_out.append({
            'label': zone.get('label') or '',
            'lat': _maybe_num(zone.get('lat')),
            'lon': _maybe_num(zone.get('lon')),
            'tilt': _maybe_num(zone.get('tilt')),
            'azimuth': _maybe_num(zone.get('azimuth')),
            'kwc': kwc,
            'base_production_kwh': ctx['base_production_kwh'],
            'shading_annual_loss_pct': ctx['shading_annual_loss_pct'],
        })
        # PV72 — courbe de production horaire de la zone (dérate matrice déjà
        # résolue par _zone_base_production), agrégée plus bas.
        zone_curves.append(
            production_horaire_zone(zones_out[-1], ctx['shading_matrix']))
        base_total += ctx['base_production_kwh']
        kwc_total += kwc
        sources.add(ctx['source'])
        warnings.extend(ctx['warnings'])

    if not zones_out:
        warnings.append("aucune zone fournie — étude vide")

    source = 'manual' if ('manual' in sources or not sources) else 'pvgis'

    # PV70 — le poste 'shading' agrégé est une moyenne PONDÉRÉE PRODUCTION des
    # pertes d'ombrage par zone (Σ zone.base_production_kwh × zone.perte),
    # jamais une moyenne plate entre zones : un pan minoritaire très ombragé ne
    # doit pas peser autant qu'un grand pan bien exposé.
    shading_fraction = 0.0
    if base_total > 0:
        shading_fraction = sum(
            (z['base_production_kwh'] / base_total)
            * (z['shading_annual_loss_pct'] / 100.0)
            for z in zones_out)

    loss_factors = {**DEFAULT_LOSS_FACTORS, 'shading': shading_fraction}
    pr, sim_warnings = _pr_block(base_total, kwc_total, loss_factors)
    warnings.extend(sim_warnings)

    # PV72 — production agrégée horaire (Σ des courbes de zone, 288 pts).
    production_curve = (
        [sum(vals) for vals in zip(*zone_curves)] if zone_curves else [])

    # PV72 — charge horaire : explicite si fournie, sinon synthétisée depuis
    # la conso du lead (même résolution 288 pts que la production, voir
    # _tiled_load_curve — jamais l'auto-synthèse 24 pts interne à
    # hourly_self_consumption, qui tronquerait la production réelle).
    if load_curve:
        load_curve_resolved = list(load_curve)
    else:
        daily_load = _daily_load_kwh_from_devis(devis)
        if daily_load <= 0:
            warnings.append(
                "consommation du lead non renseignée — autoconsommation non "
                "estimable (0 par construction, jamais un chiffre inventé)")
        load_curve_resolved = _tiled_load_curve(
            daily_load, _load_profile_key(devis))

    sc_result = hourly_self_consumption(
        load_curve=load_curve_resolved, production_curve=production_curve)
    self_consumption = {
        'hours': sc_result['hours'],
        'self_consumption_rate': sc_result['self_consumption_rate'],
        'coverage_rate': sc_result['coverage_rate'],
        'self_consumed_kwh': sc_result['self_consumed_kwh'],
        'surplus_kwh': sc_result['surplus_kwh'],
        'grid_import_kwh': sc_result['grid_import_kwh'],
    }
    warnings.extend(sc_result['warnings'])

    _, _, surplus_curve, import_curve = _hourly_flows(
        load_curve_resolved, production_curve)

    mode = getattr(devis, 'mode_installation', None)
    classe = 'agricole' if mode == 'agricole' else 'residentiel'

    # PV72 — les tarifs par tranche restent les DÉFAUTS « à confirmer » de
    # solar_design (jamais durcis ici) ; seul le toggle réel de compensation
    # société est branché (13-09 : OFF par défaut au Maroc).
    nm_result = net_metering_savings(
        injected_curve=surplus_curve, import_curve=import_curve,
        days_per_year=1,
        surplus_injecte_compense=bool(settings.surplus_injecte_compense))
    net_metering = {
        'annual_savings_mad': nm_result['annual_savings_mad'],
        'annual_compensated_kwh': nm_result['annual_compensated_kwh'],
        'annual_spill_value_mad': nm_result['annual_spill_value_mad'],
    }
    warnings.extend(nm_result['warnings'])

    subscribed_power, sp_warnings = _subscribed_power_block(
        devis, load_curve_resolved, production_curve)
    warnings.extend(sp_warnings)

    deg_result = module_degradation_curve(
        production_year1=base_total if base_total > 0 else None)
    degradation = {
        'factor_year1': deg_result['summary']['factor_year1'],
        'factor_last_year': deg_result['summary']['factor_last_year'],
        'any_warranty_breach': deg_result['summary']['any_warranty_breach'],
    }
    warnings.extend(deg_result['warnings'])

    annual_savings_year1 = (
        _annual_savings_year1(settings, self_consumption['self_consumed_kwh'], classe)
        + net_metering['annual_savings_mad'])
    upfront_cost = _num(getattr(devis, 'total_ht', None), 0.0)
    proj_result = tariff_escalation_projection(
        annual_savings_year1=annual_savings_year1, upfront_cost=upfront_cost)
    projection_25y = {
        'npv': proj_result['summary']['npv'],
        'irr': proj_result['summary']['irr'],
        'payback_year': proj_result['summary']['payback_year'],
        'discounted_payback_year': proj_result['summary']['discounted_payback_year'],
    }
    warnings.extend(proj_result['warnings'])

    return {
        'version': SIMULATION_VERSION,
        'computed_at': _iso_z(computed_at),
        'source': source,
        'zones': zones_out,
        'pr': pr,
        'self_consumption': self_consumption,
        'net_metering': net_metering,
        'subscribed_power': subscribed_power,
        'degradation': degradation,
        'projection_25y': projection_25y,
        'warnings': warnings,
    }
