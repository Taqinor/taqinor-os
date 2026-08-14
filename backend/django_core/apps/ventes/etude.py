"""PV69 — étude bancable v1 : `Devis.etude_params['simulation']`.

Orchestrateur PUR (aucune écriture DB, aucun changement de statut — règle #4)
qui agrège, par zone (pan de toiture), le productible PVGIS et une année météo
type (TMY) déjà offline-safe (``apps.parametres.pvgis.fetch_productible`` /
``apps.ventes.weather_feed.fetch_irradiance_tmy``) puis applique l'arbre de
pertes (`apps.ventes.solar_design.simulate_bankable_yield`) pour produire un
ratio de performance (PR) et les scénarios P50/P90/P75.

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


def _zone_base_production(settings, zone, *, force_refresh=False):
    """Contexte productible d'une zone (pan) : PVGIS + TMY, jamais d'exception.

    Renvoie ``{base_production_kwh, source, monthly_share, warnings}``.
    ``source`` vaut ``'manual'`` dès qu'AU MOINS un des deux fetchers est
    retombé en repli hors-ligne (reporting conservateur : ``'pvgis'`` garantit
    que TOUT le calcul de la zone est ancré sur des données réseau réelles).
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

    return {
        'base_production_kwh': base_kwh,
        'source': source,
        'monthly_share': _zone_monthly_share(tmy_res),
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
    """PV69 — étude bancable v1 : productible PVGIS par zone → PR → P50/P90/P75.

    Paramètres
    ----------
    devis : ``Devis`` — sert UNIQUEMENT à résoudre la société (réglages PVGIS
        + tarifs) ; jamais lu/écrit autrement (aucun ``devis.save()`` ici).
    zones : liste de ``{label, lat, lon, tilt, azimuth, kwc}`` — un pan de
        toiture par élément. Une zone illisible (kWc/coords manquants) ne fait
        jamais échouer l'étude : elle contribue 0 kWh, jamais d'exception.
    load_curve : réservé à PV72 (autoconsommation) — ignoré en v1.
    force_refresh : réservé à PV73 (cache PVGIS système) — sans effet tant que
        le cache n'est pas branché (comportement v1 inchangé).
    computed_at : ``datetime`` figé pour un rendu déterministe (tests) ;
        défaut = maintenant (``django.utils.timezone.now``, appelé ici pour
        rester du code applicatif, pas le module PUR ``solar_design``).

    Retourne un dict JSON-sérialisable ``{version, computed_at, source, zones,
    pr, warnings}`` conforme au sous-ensemble ``PV69`` du contrat PACT10 (les
    blocs ``self_consumption``/``net_metering``/``subscribed_power``/
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

    for zone in (zones or []):
        zone = zone or {}
        ctx = _zone_base_production(settings, zone, force_refresh=force_refresh)
        kwc = _num(zone.get('kwc'))
        zones_out.append({
            'label': zone.get('label') or '',
            'lat': _maybe_num(zone.get('lat')),
            'lon': _maybe_num(zone.get('lon')),
            'tilt': _maybe_num(zone.get('tilt')),
            'azimuth': _maybe_num(zone.get('azimuth')),
            'kwc': kwc,
            'base_production_kwh': ctx['base_production_kwh'],
            'shading_annual_loss_pct': 0.0,
        })
        base_total += ctx['base_production_kwh']
        kwc_total += kwc
        sources.add(ctx['source'])
        warnings.extend(ctx['warnings'])

    if not zones_out:
        warnings.append("aucune zone fournie — étude vide")

    source = 'manual' if ('manual' in sources or not sources) else 'pvgis'

    loss_factors = {**DEFAULT_LOSS_FACTORS, 'shading': 0.0}
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
