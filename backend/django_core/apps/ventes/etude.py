"""PV69/70 — étude bancable v1 : `Devis.etude_params['simulation']`.

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

from apps.ventes.solar_design import DEFAULT_LOSS_FACTORS, simulate_bankable_yield

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


def _fetch_productible(settings, lat, lon, *, peakpower_kwc=1.0,
                       tilt=None, azimuth=None, force_refresh=False):
    """Point de bascule UNIQUE vers PVGIS productible (PV73 y branchera le cache).

    ``force_refresh`` est accepté dès PV69 pour stabiliser la signature de
    :func:`run_bankable_study` — sans effet tant que PV73 n'a pas posé le
    cache (aucun cache = toujours un fetch réel, comportement inchangé).
    """
    from apps.parametres.pvgis import fetch_productible
    return fetch_productible(settings, lat, lon, peakpower_kwc=peakpower_kwc,
                             tilt=tilt, azimuth=azimuth)


def _fetch_tmy(lat, lon, *, force_refresh=False):
    """Point de bascule UNIQUE vers PVGIS TMY (PV73 y branchera le cache)."""
    from apps.ventes.weather_feed import fetch_irradiance_tmy
    return fetch_irradiance_tmy(lat, lon)


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


def run_bankable_study(devis, *, zones, load_curve=None, force_refresh=False,
                       computed_at=None):
    """PV69/70 — productible PVGIS multi-zones → ombrage pondéré → PR → P50/P90/P75.

    Paramètres
    ----------
    devis : ``Devis`` — résout la société (réglages PVGIS + tarifs) ET sert de
        source pour la matrice d'ombrage 12×24 (``devis.roof_layout``, PV70,
        repli tolérant si absente) ; jamais lu/écrit autrement (aucun
        ``devis.save()`` ici).
    zones : liste de ``{label, lat, lon, tilt, azimuth, kwc, shading12x24?,
        horizon_profile?, obstacles?}`` — un pan de toiture par élément. Une
        zone illisible (kWc/coords manquants) ne fait jamais échouer l'étude :
        elle contribue 0 kWh, jamais d'exception.
    load_curve : réservé à PV72 (autoconsommation) — ignoré en v1/v2.
    force_refresh : réservé à PV73 (cache PVGIS système) — sans effet tant que
        le cache n'est pas branché (comportement inchangé).
    computed_at : ``datetime`` figé pour un rendu déterministe (tests) ;
        défaut = maintenant (``django.utils.timezone.now``, appelé ici pour
        rester du code applicatif, pas le module PUR ``solar_design``).

    Retourne un dict JSON-sérialisable ``{version, computed_at, source, zones,
    pr, warnings}`` conforme au sous-ensemble ``PV69/70`` du contrat PACT10
    (les blocs ``self_consumption``/``net_metering``/``subscribed_power``/
    ``degradation``/``projection_25y`` arrivent en PV72). Ne lève JAMAIS.
    """
    if computed_at is None:
        from django.utils import timezone
        computed_at = timezone.now()

    warnings = []
    settings = _company_settings(devis)

    zones_out = []
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

    return {
        'version': SIMULATION_VERSION,
        'computed_at': _iso_z(computed_at),
        'source': source,
        'zones': zones_out,
        'pr': pr,
        'warnings': warnings,
    }
