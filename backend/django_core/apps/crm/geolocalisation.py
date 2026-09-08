"""GPS7 (fondateur 07/09/2026) — GPS d'un lead depuis un lien Maps ou l'adresse.

Deux résolveurs, PURS (aucune écriture — l'écran remplit ``gps_lat``/
``gps_lng`` et l'enregistrement normal du lead persiste et journalise) :

* ``coords_depuis_lien_maps`` — un lien Google Maps collé par le client :
  coordonnées EXTRAITES du lien (``!3d…!4d…`` du repère, ``?q=lat,lng``,
  ``@lat,lng``, ou « lat, lng » nu). Un lien COURT (maps.app.goo.gl…) est
  résolu par une requête HTTP qui suit les redirections (best-effort, 6 s),
  puis parsé pareil — les coordonnées viennent TOUJOURS de Google, jamais
  d'une estimation (règle « zéro chiffre inventé »).

* ``coords_depuis_adresse`` — géocodage Nominatim (OpenStreetMap, gratuit,
  ``countrycodes=ma``) de l'adresse ; puis (VREF-LIEUX, 08/09/2026) le
  LIEU-DIT GeoNames nommé dans l'adresse ou la ville (douar, quartier —
  ``apps/parametres/lieux_maroc.py``, correspondance sans équivoque
  seulement) ; en repli, l'ancre GeoNames de la VILLE du gazetier (précision
  « ville », annoncée telle quelle, jamais maquillée en adresse exacte).

Précisions rendues : ``'lien'`` (exact, choisi par le client), ``'adresse'``
(géocodeur), ``'lieu-dit'`` (centre d'un douar/quartier), ``'ville'``
(centre-ville approximatif). Échec ⇒ ``None`` — l'appelant n'écrit rien.
"""
from __future__ import annotations

import re
from decimal import Decimal

#: Domaines de liens COURTS Google Maps — les seuls pour lesquels une
#: résolution HTTP est tentée (jamais une URL arbitraire).
_DOMAINES_COURTS = (
    'maps.app.goo.gl', 'goo.gl', 'g.co', 'maps.google.com/maps/api')

#: Motifs d'extraction, du plus PRÉCIS au moins précis : le repère du lieu
#: (!3d/!4d), puis la recherche explicite (?q=lat,lng), puis le centre de la
#: carte (@lat,lng).
_RE_3D4D = re.compile(r'!3d(-?\d{1,2}\.\d+)!4d(-?\d{1,3}\.\d+)')
_RE_Q = re.compile(
    r'[?&](?:q|query|ll|destination|center)='
    r'(-?\d{1,2}\.\d+)(?:%2C|,)\s*(-?\d{1,3}\.\d+)')
_RE_AT = re.compile(r'@(-?\d{1,2}\.\d+),(-?\d{1,3}\.\d+)')
_RE_NU = re.compile(r'^\s*(-?\d{1,2}\.\d+)\s*[,;]\s*(-?\d{1,3}\.\d+)\s*$')

_TIMEOUT_S = 6


def _valides(lat, lng):
    try:
        lat, lng = Decimal(lat), Decimal(lng)
    except ArithmeticError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return (lat, lng)


def _extraire(texte):
    """(lat, lng) trouvées dans ``texte`` (URL ou HTML), ou ``None``."""
    for motif in (_RE_NU, _RE_3D4D, _RE_Q, _RE_AT):
        m = motif.search(texte or '')
        if m:
            coords = _valides(m.group(1), m.group(2))
            if coords:
                return coords
    return None


def coords_depuis_lien_maps(lien):
    """(lat, lng) du lien Google Maps, ou ``None`` si rien d'extractible."""
    lien = (lien or '').strip()
    if not lien:
        return None
    coords = _extraire(lien)
    if coords:
        return coords
    if not any(domaine in lien for domaine in _DOMAINES_COURTS):
        return None
    # Lien court : suivre les redirections puis parser l'URL FINALE (et, à
    # défaut, le HTML — Google y répète les coordonnées du repère).
    try:
        import requests
        reponse = requests.get(
            lien, timeout=_TIMEOUT_S, allow_redirects=True,
            headers={'User-Agent': 'solar-erp-geocoder/1.0 (resolution GPS lead)'})
        coords = _extraire(reponse.url)
        if coords:
            return coords
        return _extraire(reponse.text[:200000])
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return None


def coords_depuis_adresse(adresse, ville=''):
    """(lat, lng, precision) depuis l'adresse postale, ou ``None``.

    Nominatim d'abord (précision ``'adresse'``) ; puis le lieu-dit GeoNames
    (précision ``'lieu-dit'``) ; en repli l'ancre GeoNames de la ville du
    gazetier (précision ``'ville'`` — un centre-ville approximatif ANNONCÉ
    comme tel, jamais présenté comme le toit du client).
    """
    adresse = (adresse or '').strip()
    ville = (ville or '').strip()
    if adresse:
        try:
            import requests
            q = ', '.join(p for p in (adresse, ville, 'Maroc') if p)
            reponse = requests.get(
                'https://nominatim.openstreetmap.org/search',
                params={'format': 'json', 'q': q, 'limit': 1,
                        'countrycodes': 'ma'},
                timeout=_TIMEOUT_S,
                headers={'User-Agent': 'solar-erp-geocoder/1.0 (geocodage lead)'})
            resultats = reponse.json() if reponse.ok else []
            if resultats:
                coords = _valides(resultats[0].get('lat'),
                                  resultats[0].get('lon'))
                if coords:
                    return (*coords, 'adresse')
        except Exception:  # noqa: BLE001 — best-effort, repli ville
            pass
    # VREF-LIEUX (08/09/2026, cas « Sidi Hashass ») — lieu-dit GeoNames
    # (douar, quartier, hameau) : l'ADRESSE d'abord, corroborée par la ville
    # tapée, puis le champ ville lui-même. Correspondance sans équivoque
    # seulement (homonymes éloignés → None) ; précision « lieu-dit » annoncée.
    from apps.parametres.lieux_maroc import position_lieu_dit
    for texte, contexte in ((adresse, ville), (ville, '')):
        if not texte:
            continue
        lieu = position_lieu_dit(texte, contexte_ville=contexte)
        if lieu:
            return (Decimal(str(lieu[0])), Decimal(str(lieu[1])), 'lieu-dit')
    from apps.parametres.villes_maroc import coordonnees_ville
    for texte in (ville, adresse):
        if not texte:
            continue
        coords = coordonnees_ville(texte)
        if coords:
            lat, lng = coords
            return (Decimal(str(lat)), Decimal(str(lng)), 'ville')
    return None
