"""N65 — Client PVGIS (irradiation/productible au point GPS exact).

Interroge PVGIS (Photovoltaic Geographical Information System de la Commission
européenne) au point GPS EXACT du site pour estimer le productible annuel
(kWh/kWc/an) et la production mensuelle.

CONTRAINTES founder :
* STDLIB UNIQUEMENT (``urllib``) — aucune dépendance pip nouvelle.
* Timeout COURT — on ne bloque jamais un chiffrage sur le réseau.
* REPLI GRACIEUX hors-ligne : si PVGIS est injoignable (réseau bloqué, timeout,
  erreur), on retombe sur une hypothèse manuelle CONSERVATRICE éditable
  (``productible_manuel_kwh_kwc``). Le repli DOIT fonctionner hors-ligne — les
  tests ne dépendent JAMAIS du réseau.

Convention d'azimut founder : Sud 0 / Est −90 / Ouest +90 / Nord +180.
PVGIS attend ``aspect`` en degrés depuis le SUD, positif vers l'OUEST — c'est
EXACTEMENT la même convention, on passe donc l'azimut tel quel.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

# Endpoint JSON du calcul PV de PVGIS (v5.2, base de données par défaut).
PVGIS_BASE = 'https://re.jrc.ec.europa.eu/api/v5_2/PVcalc'

# Timeout réseau COURT (s) : on préfère le repli au blocage.
PVGIS_TIMEOUT_S = 6


def _manual_result(settings, reason):
    """Résultat de repli (hors-ligne) basé sur le réglage manuel conservateur.

    Renvoie un dict avec ``source='manual'`` ; jamais d'exception : un chiffrage
    ne doit jamais échouer faute de réseau.
    """
    try:
        manuel = float(settings.productible_manuel_kwh_kwc)
    except (TypeError, ValueError):
        manuel = 1500.0
    return {
        'source': 'manual',
        'productible_kwh_kwc': round(manuel, 1),
        'production_mensuelle_kwh_kwc': None,
        'reason': reason,
    }


def fetch_productible(settings, lat, lon, peakpower_kwc=1.0,
                      tilt=None, azimuth=None, loss=14):
    """Productible au point (lat, lon) via PVGIS, repli manuel si indisponible.

    Paramètres
    ----------
    settings : ``TariffSettings`` (pour le repli + les défauts inclinaison/azimut).
    lat, lon : coordonnées GPS EXACTES du site (degrés décimaux).
    peakpower_kwc : puissance crête pour la requête (1 kWc → kWh/kWc/an direct).
    tilt : inclinaison des modules (°) ; défaut = réglage société.
    azimuth : azimut (convention Sud 0 / Est −90 / Ouest +90 / Nord +180) ;
        défaut = réglage société. Passé tel quel à PVGIS (même convention).
    loss : pertes système PVGIS (%) — défaut 14 (valeur PVGIS usuelle).

    Retourne TOUJOURS un dict ; ``source`` ∈ {'pvgis', 'manual'}. Jamais
    d'exception réseau remontée à l'appelant.
    """
    # Coordonnées invalides → repli direct (pas d'appel réseau inutile).
    try:
        latf = float(lat)
        lonf = float(lon)
    except (TypeError, ValueError):
        return _manual_result(settings, 'coordonnées GPS manquantes ou invalides')

    # PVGIS désactivé par réglage → repli manuel (assumé, pas une erreur).
    if not getattr(settings, 'pvgis_actif', True):
        return _manual_result(settings, 'PVGIS désactivé dans les paramètres')

    if tilt is None:
        tilt = settings.inclinaison_defaut_deg
    if azimuth is None:
        azimuth = settings.azimut_defaut_deg

    params = {
        'lat': latf,
        'lon': lonf,
        'peakpower': float(peakpower_kwc or 1.0),
        'loss': loss,
        'angle': tilt,
        'aspect': azimuth,   # convention identique (Sud 0, Ouest +)
        'outputformat': 'json',
        'pvtechchoice': 'crystSi',
        'mountingplace': 'building',
    }
    url = PVGIS_BASE + '?' + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'taqinor-os'})
        with urllib.request.urlopen(req, timeout=PVGIS_TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        return _parse_pvgis(payload, float(peakpower_kwc or 1.0))
    except (urllib.error.URLError, urllib.error.HTTPError,
            TimeoutError, ValueError, KeyError, OSError) as exc:
        # Réseau bloqué / timeout / réponse inattendue → repli hors-ligne.
        return _manual_result(settings, f'PVGIS indisponible ({type(exc).__name__})')


def _parse_pvgis(payload, peakpower_kwc):
    """Extrait le productible (kWh/kWc/an) + mensuel d'une réponse PVGIS.

    Lève ``ValueError`` si la structure est inattendue → l'appelant retombe sur
    le repli manuel.
    """
    outputs = payload.get('outputputs') or payload.get('outputs') or {}
    totals = outputs.get('totals', {}).get('fixed', {})
    e_y = totals.get('E_y')  # production annuelle (kWh) pour peakpower demandé
    if e_y is None:
        raise ValueError('réponse PVGIS sans E_y')
    pk = peakpower_kwc if peakpower_kwc else 1.0
    productible = float(e_y) / pk

    monthly = None
    months = outputs.get('monthly', {}).get('fixed')
    if isinstance(months, list) and months:
        try:
            monthly = [round(float(m.get('E_m', 0)) / pk, 1) for m in months]
        except (TypeError, ValueError):
            monthly = None

    return {
        'source': 'pvgis',
        'productible_kwh_kwc': round(productible, 1),
        'production_mensuelle_kwh_kwc': monthly,
        'reason': None,
    }
