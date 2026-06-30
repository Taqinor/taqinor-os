"""FG265 — Flux d'irradiance/météo (TMY) pour caler simulations & O&M.

Récupère, au point GPS EXACT d'un site, un flux d'irradiance « année
météorologique type » (TMY — Typical Meteorological Year) afin de CALER les
simulations de production (P50/P90, autoconsommation horaire…) et de fournir un
profil mensuel de référence pour le suivi O&M (production attendue vs réelle).

Source : PVGIS (Commission européenne), endpoint TMY — c'est la MÊME source
réseau, GRATUITE et STDLIB-only, déjà retenue par le projet pour le productible
(``apps.parametres.pvgis``). AUCUNE dépendance pip nouvelle, AUCUNE clé d'API.

CONTRAINTES (alignées sur le client PVGIS existant) :
* STDLIB UNIQUEMENT (``urllib``) — pas de nouvelle dépendance.
* Timeout COURT — on ne bloque jamais une simulation sur le réseau.
* REPLI GRACIEUX hors-ligne : si PVGIS est injoignable, on retombe sur un
  profil mensuel CLIMATIQUE par défaut (Maroc) borné au productible manuel
  conservateur. Le repli FONCTIONNE hors-ligne — les tests ne dépendent JAMAIS
  du réseau.
* Module additif, séparé du PDF premium / ``/proposal`` ; ne change AUCUN statut
  de devis (RULE #4) et n'expose JAMAIS de prix.

NOTE (gating) : le flux « TEMPS RÉEL » (irradiance live minute par minute pour
le pilotage O&M instantané) nécessite un fournisseur météo PAYANT avec clé
d'API dédiée — NON inclus ici, à provisionner par le founder. Le présent module
couvre le flux TMY (calage des simulations et référence O&M), gratuit.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

# Endpoint JSON TMY de PVGIS (v5.2). Renvoie une année météo type horaire au
# point GPS demandé (irradiance globale plan horizontal G(h), température, etc.).
PVGIS_TMY_BASE = 'https://re.jrc.ec.europa.eu/api/v5_2/tmy'

# Timeout réseau COURT (s) : on préfère le repli au blocage d'une simulation.
PVGIS_TMY_TIMEOUT_S = 6

# Profil mensuel CLIMATIQUE de repli — part relative de l'irradiation annuelle
# par mois pour un climat marocain « moyen » (12 fractions sommant à ~1.0).
# Utilisé hors-ligne pour ventiler le productible manuel en profil mensuel.
_DEFAULT_MONTHLY_SHARE = [
    0.058, 0.066, 0.085, 0.092, 0.103, 0.106,
    0.110, 0.104, 0.090, 0.078, 0.059, 0.049,
]


def _manual_monthly_irradiance(annual_kwh_m2):
    """Ventile une irradiation annuelle (kWh/m²) en 12 valeurs mensuelles.

    Utilise le profil climatique marocain par défaut. Renvoie une liste de 12
    floats arrondis ; jamais d'exception.
    """
    try:
        annual = float(annual_kwh_m2)
    except (TypeError, ValueError):
        annual = 1900.0
    if annual <= 0:
        annual = 1900.0
    return [round(annual * share, 1) for share in _DEFAULT_MONTHLY_SHARE]


def _manual_result(annual_kwh_m2, reason):
    """Flux de repli (hors-ligne) basé sur un profil climatique par défaut.

    Renvoie TOUJOURS un dict avec ``source='manual'`` ; jamais d'exception : une
    simulation ne doit jamais échouer faute de réseau.
    """
    monthly = _manual_monthly_irradiance(annual_kwh_m2)
    return {
        'source': 'manual',
        'irradiance_annuelle_kwh_m2': round(sum(monthly), 1),
        'irradiance_mensuelle_kwh_m2': monthly,
        'temperature_moyenne_c': None,
        'reason': reason,
    }


def fetch_irradiance_tmy(lat, lon, *, annual_fallback_kwh_m2=1900.0,
                         timeout_s=PVGIS_TMY_TIMEOUT_S):
    """Flux d'irradiance TMY au point (lat, lon), repli climatique si indispo.

    Paramètres
    ----------
    lat, lon : coordonnées GPS EXACTES du site (degrés décimaux).
    annual_fallback_kwh_m2 : irradiation annuelle conservatrice à ventiler en
        repli (hors-ligne). Défaut 1900 kWh/m² (Maroc « moyen »).
    timeout_s : timeout réseau (s). Court par défaut.

    Retourne TOUJOURS un dict ; ``source`` ∈ {'pvgis', 'manual'} :
        ``irradiance_annuelle_kwh_m2`` (float),
        ``irradiance_mensuelle_kwh_m2`` (12 floats, plan horizontal),
        ``temperature_moyenne_c`` (float | None),
        ``reason`` (str | None).
    Jamais d'exception réseau remontée à l'appelant ; jamais aucun prix.
    """
    try:
        latf = float(lat)
        lonf = float(lon)
    except (TypeError, ValueError):
        return _manual_result(annual_fallback_kwh_m2,
                              'coordonnées GPS manquantes ou invalides')

    params = {
        'lat': latf,
        'lon': lonf,
        'outputformat': 'json',
    }
    url = PVGIS_TMY_BASE + '?' + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'taqinor-os'})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        return parse_tmy(payload)
    except (urllib.error.URLError, urllib.error.HTTPError,
            TimeoutError, ValueError, KeyError, OSError) as exc:
        return _manual_result(
            annual_fallback_kwh_m2,
            f'PVGIS TMY indisponible ({type(exc).__name__})')


def parse_tmy(payload):
    """Agrège une réponse PVGIS-TMY horaire en profil mensuel d'irradiance.

    La réponse TMY contient une liste horaire (8760 points) sous
    ``outputs.tmy_hourly`` avec, par heure, l'irradiance globale plan horizontal
    ``G(h)`` (W/m²) et la température ``T2m`` (°C) ; le champ ``time(UTC)`` porte
    le mois sur les positions 4-5 d'un horodatage ``YYYYMMDD:HHMM``.

    Lève ``ValueError`` si la structure est inattendue → l'appelant retombe sur
    le repli climatique. Sépare l'I/O réseau du parsing (testable hors-ligne).
    """
    outputs = payload.get('outputs') or {}
    hourly = outputs.get('tmy_hourly')
    if not isinstance(hourly, list) or not hourly:
        raise ValueError('réponse PVGIS-TMY sans tmy_hourly')

    # Wh/m² cumulés par mois (1..12) ; G(h) en W/m² ⇒ 1 h = G Wh/m².
    monthly_wh = [0.0] * 12
    temp_sum = 0.0
    temp_count = 0
    for point in hourly:
        stamp = str(point.get('time(UTC)', ''))
        # Format attendu 'YYYYMMDD:HHMM' → mois aux positions 4-5.
        if len(stamp) < 6:
            continue
        try:
            month = int(stamp[4:6])
        except ValueError:
            continue
        if not 1 <= month <= 12:
            continue
        try:
            ghi = float(point.get('G(h)', 0) or 0)
        except (TypeError, ValueError):
            ghi = 0.0
        monthly_wh[month - 1] += ghi
        t2m = point.get('T2m')
        if t2m is not None:
            try:
                temp_sum += float(t2m)
                temp_count += 1
            except (TypeError, ValueError):
                pass

    # Wh/m² → kWh/m².
    monthly_kwh = [round(wh / 1000.0, 1) for wh in monthly_wh]
    annual_kwh = round(sum(monthly_kwh), 1)
    if annual_kwh <= 0:
        raise ValueError('irradiance TMY agrégée nulle')

    temp_moy = round(temp_sum / temp_count, 1) if temp_count else None
    return {
        'source': 'pvgis',
        'irradiance_annuelle_kwh_m2': annual_kwh,
        'irradiance_mensuelle_kwh_m2': monthly_kwh,
        'temperature_moyenne_c': temp_moy,
        'reason': None,
    }
