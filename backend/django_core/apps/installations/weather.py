"""XFSM21 — Météo sur le planning (travaux toiture).

Intègre Open-Meteo (https://open-meteo.com/ — gratuit, SANS clé, sans compte)
pour récupérer la prévision J+3 aux coordonnées GPS des interventions de type
POSE planifiées, et positionner un drapeau `meteo_risque` selon des seuils
paramétrables (pluie / vent). Panne API → no-op SILENCIEUX (aucune exception ne
remonte, `meteo_risque` reste inchangé) : c'est un confort opérationnel, jamais
un blocage.

Seuils par défaut (paramétrables via les constantes ci-dessous) :
  * pluie ≥ 5 mm cumulés sur le jour cible ;
  * vent ≥ 40 km/h en rafale sur le jour cible.
Un dépassement de L'UN des deux seuils suffit à signaler le risque.
"""
import logging

logger = logging.getLogger(__name__)

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT_S = 8

# Seuils par défaut — pluie cumulée (mm) et rafale de vent (km/h) sur le jour.
SEUIL_PLUIE_MM = 5
SEUIL_VENT_KMH = 40


def _fetch_json(url, params):
    """GET JSON best-effort (requests si dispo, sinon urllib). Renvoie None
    sur tout échec réseau/parsing — ne lève JAMAIS."""
    try:
        import requests as _requests
    except ImportError:
        import json as _json
        import urllib.parse as _urllib_parse
        import urllib.request as _urllib_request
        full_url = f"{url}?{_urllib_parse.urlencode(params)}"
        try:
            with _urllib_request.urlopen(full_url, timeout=_TIMEOUT_S) as resp:
                return _json.loads(resp.read().decode())
        except Exception as exc:
            logger.info("Open-Meteo lookup failed (urllib): %s", exc)
            return None

    try:
        resp = _requests.get(url, params=params, timeout=_TIMEOUT_S)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.info("Open-Meteo lookup failed (requests): %s", exc)
        return None


def fetch_forecast(lat, lng, target_date):
    """Prévision quotidienne (pluie cumulée mm, rafale de vent max km/h) pour
    ``target_date`` (date) au point (lat, lng). Renvoie
    {"precipitation_mm": float, "windgusts_kmh": float} ou None si le point
    GPS manque, la date est hors couverture, ou l'API échoue."""
    if lat is None or lng is None or target_date is None:
        return None
    data = _fetch_json(_OPEN_METEO_URL, {
        'latitude': float(lat), 'longitude': float(lng),
        'daily': 'precipitation_sum,windgusts_10m_max',
        'timezone': 'Africa/Casablanca',
        'start_date': target_date.isoformat(),
        'end_date': target_date.isoformat(),
    })
    if not data:
        return None
    daily = data.get('daily') or {}
    try:
        precip = daily.get('precipitation_sum', [None])[0]
        vent = daily.get('windgusts_10m_max', [None])[0]
    except (IndexError, TypeError):
        return None
    if precip is None and vent is None:
        return None
    return {
        'precipitation_mm': precip,
        'windgusts_kmh': vent,
    }


def evaluate_risk(
        forecast, seuil_pluie_mm=SEUIL_PLUIE_MM, seuil_vent_kmh=SEUIL_VENT_KMH):
    """True si la prévision dépasse un des deux seuils, False sinon, None si
    la prévision est absente/inexploitable."""
    if not forecast:
        return None
    precip = forecast.get('precipitation_mm')
    vent = forecast.get('windgusts_kmh')
    if precip is None and vent is None:
        return None
    risque = False
    if precip is not None and precip >= seuil_pluie_mm:
        risque = True
    if vent is not None and vent >= seuil_vent_kmh:
        risque = True
    return risque
