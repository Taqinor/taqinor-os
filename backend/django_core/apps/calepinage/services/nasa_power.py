"""ACAL746 (D-ACAL-81) — NASA POWER, SECONDE source météo, en COMPARAISON seulement.

Le fondateur a répondu le 23/11/2026 : « Yes, use it ». Sa règle générale du même
jour : UN SEUL chiffre par valeur. PVGIS reste donc la source de toute production ;
NASA POWER ne produit qu'une irradiation horizontale affichée À CÔTÉ de celle de
PVGIS, jamais un second chiffre de production (PVsyst compare de même deux bases
météo d'un lieu : https://www.pvsyst.com/help/meteo-database/compare-meteo-data/index.html).

Service : l'API horaire « point » de NASA POWER
(https://power.larc.nasa.gov/docs/services/api/temporal/hourly/), appelée SANS clé
ni compte. Paramètres lus sur une réponse réelle du 23/11/2026 (bloc ``parameters``
de la réponse, API v2.10.5) : ``ALLSKY_SFC_SW_DWN`` (global horizontal),
``ALLSKY_SFC_SW_DNI`` (direct normal), ``ALLSKY_SFC_SW_DIFF`` (diffus), en Wh/m² par
heure, ``T2M`` (°C), ``WS10M`` (m/s) ; ``time-standard=UTC`` ; le code de
remplissage est celui que la réponse publie dans ``header.fill_value``.

Discipline, comme ``pvgis_serie.ClientPvgis`` : transport INJECTABLE (aucun appel
réseau en test), délai COURT, cache borné réemployé (``pvgis_serie._Cache``). Une
valeur manquante refuse la série en NOMMANT l'heure ; une panne réseau refuse avec
son motif — jamais une série partielle. La comparaison, elle, ne lève jamais : un
service muet donne un bloc avec son motif, et la simulation continue.

Aucune donnée de client ne part : seule une coordonnée ARRONDIE au centième de degré
(≈ 1 km — la grille de NASA POWER est d'environ un demi-degré) est envoyée.
"""
from __future__ import annotations

import datetime
import json
import logging
import urllib.error
import urllib.parse

from .pvgis_serie import _CACHE_PARTAGE, _maintenant_iso, _transport_urllib, cle_de_cache
from .valeurs import nombre

logger = logging.getLogger(__name__)

__all__ = ['ClientNasaPower', 'NasaPowerIndisponible', 'PARAMETRES', 'RACINE_API']

#: L'API horaire « point » de NASA POWER.
RACINE_API = 'https://power.larc.nasa.gov/api/temporal/hourly/point'

#: Délai COURT : une comparaison ne retient jamais une simulation.
TIMEOUT_S = 10

#: Décimales gardées sur la coordonnée envoyée (au centième ≈ 1 km).
DECIMALES_COORDONNEE = 2

#: ``{paramètre NASA POWER: colonne de la série}`` — l'ordre de la requête.
PARAMETRES = {
    'ALLSKY_SFC_SW_DWN': 'ghi_w_m2',
    'ALLSKY_SFC_SW_DNI': 'dni_w_m2',
    'ALLSKY_SFC_SW_DIFF': 'dhi_w_m2',
    'T2M': 't2m_c',
    'WS10M': 'ws10m',
}

#: ACAL2043 — délai TOTAL d'une comparaison (une demande par année) : au-delà, la comparaison
#: est omise avec son motif, jamais la simulation retenue.
DELAI_TOTAL_S = 30

#: Heures d'une année complète (non bissextile, bissextile).
HEURES_PAR_AN = (8760, 8784)


class NasaPowerIndisponible(RuntimeError):
    """NASA POWER injoignable, en refus ou incomplet — AUCUNE série publiée."""

    def __init__(self, message, *, champ='meteo.nasa_power'):
        super().__init__(message)
        self.champ = champ
        self.motif = message


class ClientNasaPower:
    """Le client NASA POWER — réseau injectable, sans clé, sans compte."""

    def __init__(self, transport=None, *, racine=RACINE_API, timeout_s=TIMEOUT_S, cache=None):
        self.transport = transport or _transport_urllib
        self.racine = racine
        self.timeout_s = timeout_s
        self.cache = cache if cache is not None else _CACHE_PARTAGE
        self.urls_appelees = []

    def serie_horizontale(self, lat, lon, annee_debut, annee_fin, *, obtenue_le=None):
        """La série HORIZONTALE horaire (UTC) des années demandées.

        Returns:
            dict — ``points[{annee, mois, jour, heure, ghi_w_m2, dni_w_m2, dhi_w_m2,
            t2m_c, ws10m}]``, ``plan_des_donnees: 'horizontal'`` et ``meteo``
            ``{service, obtenue_le, point, url, sources, version_api}``.

        Raises:
            NasaPowerIndisponible: panne réseau, refus HTTP, réponse illisible ou
                valeur manquante (l'heure est nommée).
        """
        params = {
            'parameters': ','.join(PARAMETRES), 'community': 'RE',
            'longitude': round(float(lon), DECIMALES_COORDONNEE),
            'latitude': round(float(lat), DECIMALES_COORDONNEE),
            'start': f'{int(annee_debut)}0101', 'end': f'{int(annee_fin)}1231',
            'format': 'JSON', 'time-standard': 'UTC',
        }
        url = f'{self.racine}?{urllib.parse.urlencode(params, safe=",")}'
        charge = self._charge(url, params)
        valeurs = ((charge.get('properties') or {}).get('parameter') or {})
        manquant = nombre((charge.get('header') or {}).get('fill_value'))
        horodatages = sorted(valeurs.get('ALLSKY_SFC_SW_DWN') or {})
        if not horodatages or any(nom not in valeurs for nom in PARAMETRES):
            raise NasaPowerIndisponible(
                'La réponse de NASA POWER ne porte pas les cinq paramètres demandés '
                f'({", ".join(PARAMETRES)}) : aucune série n\'est publiée.')
        points = [self._point(horodatage, valeurs, manquant) for horodatage in horodatages]
        geometrie = (charge.get('geometry') or {}).get('coordinates') or []
        entete = charge.get('header') or {}
        return {
            'points': points,
            'plan_des_donnees': 'horizontal',
            'meteo': {
                'service': 'nasa_power',
                'obtenue_le': obtenue_le or _maintenant_iso(),
                'point': {'lat': params['latitude'], 'lon': params['longitude'],
                          'altitude_m': nombre(geometrie[2]) if len(geometrie) > 2 else None},
                'url': url,
                'sources': list(entete.get('sources') or []),
                'version_api': ((entete.get('api') or {}).get('version')),
            },
        }

    def comparaison_horizontale(self, *, lat, lon, annee_debut, annee_fin, ghi_pvgis_kwh_m2):
        """L'irradiation horizontale annuelle de NASA POWER À CÔTÉ de celle de PVGIS.

        PVGIS reste la source du chiffre (``source_du_chiffre``). Ne lève JAMAIS :
        un service muet, une année incomplète ou un chiffre PVGIS absent donnent un
        bloc dont ``motif`` dit pourquoi, valeurs à ``None``.
        """
        bloc = {'source_du_chiffre': 'pvgis', 'source_comparee': 'nasa_power',
                'irradiation_horizontale_kwh_m2': {'pvgis': nombre(ghi_pvgis_kwh_m2), 'nasa_power': None},
                'ecart_pct': None, 'annees': [], 'meteo': None, 'motif': ''}
        try:
            serie = self._series_annuelles(lat, lon, int(annee_debut), int(annee_fin))
        except (NasaPowerIndisponible, TypeError, ValueError) as refus:
            logger.info('NASA POWER : comparaison omise (%s)', refus)
            bloc['motif'] = getattr(refus, 'motif', None) or f'Entrée illisible : {refus}'
            return bloc
        bloc['meteo'] = serie['meteo']
        par_annee = {}
        for point in serie['points']:
            heures, somme = par_annee.get(point['annee'], (0, 0.0))
            par_annee[point['annee']] = (heures + 1, somme + point['ghi_w_m2'] / 1000.0)
        incompletes = sorted(annee for annee, (heures, _s) in par_annee.items() if heures not in HEURES_PAR_AN)
        if incompletes:
            bloc['motif'] = ('NASA POWER ne couvre pas entièrement les années '
                             f'{", ".join(map(str, incompletes))} : aucune moyenne annuelle n\'est comparée.')
            return bloc
        nasa = round(sum(s for _h, s in par_annee.values()) / len(par_annee), 1)
        bloc['annees'] = sorted(par_annee)
        bloc['irradiation_horizontale_kwh_m2']['nasa_power'] = nasa
        pvgis = bloc['irradiation_horizontale_kwh_m2']['pvgis']
        if pvgis is None or pvgis <= 0:
            bloc['motif'] = "L'irradiation horizontale de PVGIS n'est pas connue : l'écart n'est pas calculé."
            return bloc
        bloc['ecart_pct'] = round((nasa - pvgis) / pvgis * 100.0, 2)
        return bloc

    def _series_annuelles(self, lat, lon, annee_debut, annee_fin):
        """ACAL2043 — la série des années demandées, UNE demande par année (chacune en cache) :
        le service refuse en HTTP 422 une demande horaire JSON de plus d'un an (mesuré le
        25/11/2026 : 2022 seule ⇒ 200, 2014-2023 ⇒ 422). Délai total borné (:data:`DELAI_TOTAL_S`)."""
        import time

        depart, points, meteo = time.monotonic(), [], None
        for annee in range(annee_debut, annee_fin + 1):
            if time.monotonic() - depart > DELAI_TOTAL_S:
                raise NasaPowerIndisponible(
                    f'NASA POWER n’a pas répondu à temps (plus de {DELAI_TOTAL_S} s pour '
                    f'{annee_fin - annee_debut + 1} années) : la comparaison météo est omise.')
            serie = self.serie_horizontale(lat, lon, annee, annee)
            points.extend(serie['points'])
            meteo = meteo or serie['meteo']
        return {'points': points, 'meteo': meteo}

    # ── l'appel ─────────────────────────────────────────────────────────
    def _charge(self, url, params):
        cle = cle_de_cache('nasa_power', params)
        en_cache = self.cache.lire(cle)
        if en_cache is not None:
            return en_cache
        self.urls_appelees.append(url)
        try:
            statut, corps = self.transport(url, self.timeout_s)
        except (urllib.error.URLError, TimeoutError, OSError) as erreur:
            raise NasaPowerIndisponible(
                f'NASA POWER est injoignable ({type(erreur).__name__}) : la comparaison '
                'météo est omise, PVGIS reste la source.')
        if statut != 200:
            raise NasaPowerIndisponible(
                f'NASA POWER a refusé la demande (HTTP {statut}) : la comparaison météo est omise.')
        try:
            charge = json.loads(corps)
        except ValueError:
            raise NasaPowerIndisponible(
                'La réponse de NASA POWER est illisible (JSON invalide) : la comparaison météo est omise.')
        if not isinstance(charge, dict):
            raise NasaPowerIndisponible('La réponse de NASA POWER n\'est pas un objet JSON.')
        self.cache.poser(cle, charge)
        return charge

    @staticmethod
    def _point(horodatage, valeurs, manquant):
        """Un point de la série ; une valeur manquante refuse en NOMMANT l'heure."""
        try:
            instant = datetime.datetime.strptime(horodatage, '%Y%m%d%H')
        except ValueError:
            raise NasaPowerIndisponible(
                f'Horodatage NASA POWER illisible (« {horodatage} ») : aucune série n\'est publiée.')
        point = {'annee': instant.year, 'mois': instant.month, 'jour': instant.day, 'heure': instant.hour}
        for parametre, colonne in PARAMETRES.items():
            valeur = nombre((valeurs.get(parametre) or {}).get(horodatage))
            if valeur is None or (manquant is not None and valeur == manquant):
                raise NasaPowerIndisponible(
                    f'NASA POWER n\'a pas de valeur « {parametre} » le '
                    f'{instant:%Y-%m-%d} à {instant.hour} h UTC : la série est refusée, '
                    'jamais complétée.', champ=f'meteo.nasa_power.{parametre}')
            point[colonne] = valeur
        return point
