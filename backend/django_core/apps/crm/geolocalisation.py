"""GPS7 — GPS d'un lead depuis un lien Maps, des coordonnées ou l'adresse.

Résolveurs PURS (aucune écriture — l'écran remplit ``gps_lat``/``gps_lng`` et
l'enregistrement normal du lead persiste et journalise) :

* ``resoudre_lien_maps`` — tout ce qu'un client peut envoyer : lien Google
  (long, court, de consentement), coordonnées nues (décimales ou entières),
  degrés-minutes-secondes, plus code (complet, ou court avec sa localité),
  nom de lieu ou adresse. Les coordonnées EXTRAITES viennent TOUJOURS du texte
  (règle « zéro chiffre inventé ») ; sans coordonnée, le nom du lieu est
  géocodé et la précision rendue le dit (``adresse``/``lieu-dit``/``ville``).
* ``coords_depuis_lien_maps`` — la seule extraction exacte (sans géocodage).
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
from fractions import Fraction
from urllib.parse import unquote, urlsplit

import logging

logger = logging.getLogger(__name__)

#: Domaines de liens COURTS Google Maps — les seuls pour lesquels une
#: résolution HTTP est tentée (jamais une URL arbitraire).
_DOMAINES_COURTS = (
    'maps.app.goo.gl', 'goo.gl', 'g.co', 'maps.google.com/maps/api')

# --- Coordonnées décimales -------------------------------------------------
# lat sur 2 chiffres, lng sur 3, entiers ou décimaux, signe ``+``/``-``
# facultatif (Google écrit « 33.38,+-7.54 »). Deux formes : séparées par ``,``
# ou ``;`` (entiers permis) ou par des blancs (décimaux exigés, pour ne pas
# lire « 12 34 rue X » comme un point).
_LAT = r'([+-]?\d{1,2}(?:\.\d+)?)'
_LNG = r'(-?\d{1,3}(?:\.\d+)?)(?![\d.])'
_LAT_D = r'([+-]?\d{1,2}\.\d+)'
_LNG_D = r'(-?\d{1,3}\.\d+)(?![\d.])'
_SEP_C = r'\s*[,;]\s*\+?\s*'
_SEP_B = r'\s+\+?\s*'


def _formes(prefixe, suffixe=''):
    """Les deux motifs (virgule / blancs) d'un point précédé de ``prefixe``."""
    return (re.compile(prefixe + r'(?<![\d.])' + _LAT + _SEP_C + _LNG + suffixe),
            re.compile(prefixe + r'(?<![\d.])' + _LAT_D + _SEP_B + _LNG_D
                       + suffixe))


_RE_3D4D = re.compile(
    r'!3d([+-]?\d{1,2}(?:\.\d+)?)!4d([+-]?\d{1,3}(?:\.\d+)?)(?![\d.])')
_FORMES_REQUETE = _formes(
    r'[?&](?:q|query|ll|destination|center|daddr|sll)=\s*(?:loc:)?\s*')
_FORMES_CHEMIN = _formes(r'/maps/(?:search|place|dir)/(?:/)?')
_FORMES_AROBASE = _formes(r'@')[:1]
_FORMES_NU = _formes(r'^\s*', r'\s*$')

# --- Degrés / minutes / secondes ------------------------------------------
_COMPOSANTE = (
    r'(\d{1,3}(?:\.\d+)?)\s*(?:[°º˚]\s*(?:(\d{1,2}(?:\.\d+)?)\s*'
    r"(?:['′’]|&#39;)\s*(?:(\d{1,2}(?:\.\d+)?)\s*"
    r'(?:"|″|”|\'\'|′′|’’)?)?)?)?'
    r'\s*([NSEWO])(?![A-Za-z])')
_RE_DMS = re.compile(
    _COMPOSANTE + r'[\s,;+]*' + _COMPOSANTE, re.IGNORECASE)

# --- Plus codes (Open Location Code) --------------------------------------
_OLC_ALPHABET = '23456789CFGHJMPQRVWX'
_OLC_CAR = '[23456789CFGHJMPQRVWX]'
_RE_PLUS = re.compile(
    r'(?<![A-Za-z0-9])(' + _OLC_CAR + r'{8}|' + _OLC_CAR + r'{6}|' + _OLC_CAR
    + r'{4})\+(' + _OLC_CAR + r'{2,7})(?![A-Za-z0-9])', re.IGNORECASE)
_RESOLUTIONS_PAIRES = (Fraction(20), Fraction(1), Fraction(1, 20),
                       Fraction(1, 400), Fraction(1, 8000))

_TIMEOUT_S = 6
_NOM_MAX = 200
_SEPT = Decimal('0.0000001')
_SIX = Decimal('0.000001')


def _valides(lat, lng):
    try:
        lat, lng = Decimal(str(lat).lstrip('+')), Decimal(str(lng).lstrip('+'))
    except ArithmeticError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    if lat.as_tuple().exponent < -6:  # colonnes gps_lat/gps_lng : 6 décimales
        lat = lat.quantize(_SIX)
    if lng.as_tuple().exponent < -6:
        lng = lng.quantize(_SIX)
    return (lat, lng)


def _variantes(texte):
    """Le texte brut puis ses décodages successifs (``%2C`` en ``,``,
    ``%25C2%25B0`` en ``%C2%B0`` puis ``°``), 3 passes au plus."""
    sortie = [texte or '']
    for _ in range(3):
        suivant = unquote(sortie[-1])
        if suivant == sortie[-1]:
            break
        sortie.append(suivant)
    return sortie


# --- Open Location Code ----------------------------------------------------
def olc_encoder(lat, lng, longueur=10):
    """Plus code COMPLET (``longueur`` chiffres, paires seulement : 2 à 10)."""
    lat = min(max(Fraction(str(lat)) + 90, Fraction(0)),
              Fraction(180) - Fraction(1, 10 ** 9))
    lng = (Fraction(str(lng)) + 180) % 360
    code = ''
    for i in range(longueur // 2):
        res = _RESOLUTIONS_PAIRES[i]
        d_lat, d_lng = int(lat // res), int(lng // res)
        lat -= d_lat * res
        lng -= d_lng * res
        code += _OLC_ALPHABET[d_lat] + _OLC_ALPHABET[d_lng]
        if i == 3:
            code += '+'
    return code


def olc_decoder(code):
    """Centre ``(lat, lng)`` (``Fraction``) d'un plus code COMPLET, ou ``None``."""
    chiffres = code.replace('+', '').upper()
    if len(chiffres) < 8 or any(c not in _OLC_ALPHABET for c in chiffres):
        return None
    lat = lng = Fraction(0)
    for i, c in enumerate(chiffres[:10]):
        res = _RESOLUTIONS_PAIRES[i // 2]
        if i % 2 == 0:
            lat += _OLC_ALPHABET.index(c) * res
        else:
            lng += _OLC_ALPHABET.index(c) * res
    h_lat = h_lng = _RESOLUTIONS_PAIRES[(min(len(chiffres), 10) // 2) - 1]
    for c in chiffres[10:15]:
        idx = _OLC_ALPHABET.index(c)
        h_lat /= 5
        h_lng /= 4
        lat += (idx // 4) * h_lat
        lng += (idx % 4) * h_lng
    lat_c, lng_c = lat - 90 + h_lat / 2, lng - 180 + h_lng / 2
    if not (-90 <= lat_c <= 90 and -180 <= lng_c <= 180):
        return None
    return (lat_c, lng_c)


def olc_retrouver(code_court, ref_lat, ref_lng):
    """``recoverNearest`` : le plus code complet le plus proche de la
    référence, centre ``(lat, lng)`` en ``Fraction``, ou ``None``."""
    avant = code_court.split('+')[0]
    remplissage = 8 - len(avant)
    resolution = Fraction(20) ** (2 - remplissage // 2)
    demi = resolution / 2
    prefixe = olc_encoder(ref_lat, ref_lng, 10).replace('+', '')[:remplissage]
    centre = olc_decoder(prefixe + code_court.upper())
    if centre is None:
        return None
    lat, lng = centre
    ref_lat, ref_lng = Fraction(str(ref_lat)), Fraction(str(ref_lng))
    if ref_lat + demi < lat and lat - resolution >= -90:
        lat -= resolution
    elif ref_lat - demi > lat and lat + resolution <= 90:
        lat += resolution
    if ref_lng + demi < lng:
        lng -= resolution
    elif ref_lng - demi > lng:
        lng += resolution
    return (lat, lng)


def _coords_olc(centre):
    lat, lng = (Decimal(f.numerator) / Decimal(f.denominator) for f in centre)
    return _valides(lat.quantize(_SEPT), lng.quantize(_SEPT))


# --- Extraction ------------------------------------------------------------
def _extraire_dms(texte):
    for m in _RE_DMS.finditer(texte):
        g = m.groups()
        valeurs = []
        for deg, mn, sec, hem in (g[0:4], g[4:8]):
            if (mn is not None and Decimal(mn) >= 60) or (
                    sec is not None and Decimal(sec) >= 60):
                break
            v = Decimal(deg) + (Decimal(mn) / 60 if mn else 0) + (
                Decimal(sec) / 3600 if sec else 0)
            valeurs.append((v.quantize(_SEPT), hem.upper()))
        if len(valeurs) != 2:
            continue
        (a, ha), (b, hb) = valeurs
        if ha in 'NS' and hb in 'EWO':
            lat, lng, h_lat, h_lng = a, b, ha, hb
        elif ha in 'EWO' and hb in 'NS':
            lat, lng, h_lat, h_lng = b, a, hb, ha
        else:
            continue
        coords = _valides(-lat if h_lat == 'S' else lat,
                          -lng if h_lng in 'WO' else lng)
        if coords:
            return coords
    return None


def _extraire_olc_complet(texte):
    for m in _RE_PLUS.finditer(texte):
        if len(m.group(1)) == 8:
            centre = olc_decoder(m.group(1) + '+' + m.group(2))
            if centre:
                return _coords_olc(centre)
    return None


def _chercher(formes, texte):
    for motif in formes:
        m = motif.search(texte)
        if m:
            coords = _valides(m.group(1), m.group(2))
            if coords:
                return coords
    return None


def _extraire_variante(texte, html=False):
    m = _RE_3D4D.search(texte)
    if m:
        coords = _valides(m.group(1), m.group(2))
        if coords:
            return coords
    coords = (_chercher(_FORMES_REQUETE, texte)
              or _chercher(_FORMES_CHEMIN, texte))
    if coords:
        return coords
    if not html:
        coords = _extraire_dms(texte)
        if coords:
            return coords
    coords = _chercher(_FORMES_AROBASE, texte)
    if coords or html:
        return coords
    return _extraire_olc_complet(texte)


def _extraire(texte, html=False):
    """(lat, lng) trouvées dans ``texte`` (URL, texte collé ou HTML), ou
    ``None``. Précision décroissante : coordonnées nues, repère ``!3d!4d``,
    recherche explicite (``q=``, ``/search/``, ``/place/``), DMS, centre de la
    carte (``@``), plus code complet. ``html`` : page d'un lien court, où seules
    les formes d'URL sont lues (jamais un « lat, lng » au milieu du texte)."""
    for variante in _variantes(texte):
        if not html:
            coords = _chercher(_FORMES_NU, variante)
            if coords:
                return coords
        coords = _extraire_variante(variante, html)
        if coords:
            return coords
    return None


def est_lien_court(lien):
    """Vrai si ``lien`` est un lien court Google (résolu par requête HTTP)."""
    lien = (lien or '').strip()
    # Le champ accepte désormais du texte libre : on lit l'HÔTE réel, jamais
    # une sous-chaîne (« http://10.0.0.1/?goo.gl » ne fait aucune requête).
    try:
        url = urlsplit(lien)
    except ValueError:
        return False
    if url.scheme.lower() not in ('http', 'https') or not url.hostname:
        return False
    cible = url.hostname.lower() + url.path
    return any(cible == d or cible.startswith(d + '/')
               for d in _DOMAINES_COURTS)


def _suivre_lien_court(lien):
    """(url finale, texte de la page) du lien court, ou ``None`` (best-effort)."""
    try:
        import requests
        reponse = requests.get(
            lien, timeout=_TIMEOUT_S, allow_redirects=True,
            headers={'User-Agent': 'solar-erp-geocoder/1.0 (resolution GPS lead)'})
        return (reponse.url, reponse.text[:200000])
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
        logger.warning("coords depuis lien maps : échec ignoré, comportement dégradé", exc_info=True)
        return None


def _exactes(texte):
    """((lat, lng) ou ``None``, cible) : extraction exacte, lien court suivi ;
    ``cible`` est le texte (ou l'URL finale) sur lequel replier, ``None`` si le
    lien court n'a pas pu être ouvert."""
    coords = _extraire(texte)
    if coords or not est_lien_court(texte):
        return coords, texte
    page = _suivre_lien_court(texte)
    if page is None:
        return None, None
    url, html = page
    return _extraire(url) or _extraire(html, html=True), url


def coords_depuis_lien_maps(lien):
    """(lat, lng) EXACTS du lien / texte, ou ``None`` si rien d'extractible."""
    lien = (lien or '').strip()
    if not lien:
        return None
    return _exactes(lien)[0]


# --- Repli : plus code court, nom de lieu ----------------------------------
_RE_NOM_CHEMIN = re.compile(r'/maps/(?:place|search)/([^/?#@]+)')
_RE_NOM_REQUETE = re.compile(r'[?&](?:q|query|destination|daddr)=([^&#]+)')


def _plus_code_court(texte):
    """(code court, localité qui le suit) du premier plus code COURT, ou ``None``."""
    for variante in _variantes(texte):
        for m in _RE_PLUS.finditer(variante):
            if len(m.group(1)) < 8:
                reste = re.split(r'[?&#/]', variante[m.end():], maxsplit=1)[0]
                reste = re.sub(r'^[\s,;-]+', '', reste.replace('+', ' ')).strip()
                return m.group(1) + '+' + m.group(2), reste
    return None


def _nom_lieu(texte):
    """Texte à géocoder : le nom d'un lien Google (``/place/<Nom>``,
    ``?q=<texte>``), ou le texte collé lui-même s'il n'est pas une URL."""
    texte = texte.strip()
    if re.match(r'(?i)https?://', texte):
        if not any(h in texte.lower() for h in ('google.', 'goo.gl', 'g.co')):
            return None
        for variante in reversed(_variantes(texte)):
            for motif in (_RE_NOM_CHEMIN, _RE_NOM_REQUETE):
                m = motif.search(variante)
                if m:
                    nom = m.group(1).replace('+', ' ').strip()
                    if any(c.isalpha() for c in nom):
                        return nom[:_NOM_MAX]
        return None
    if '\n' in texte or len(texte) > _NOM_MAX or not any(
            c.isalpha() for c in texte):
        return None
    return texte


def resoudre_lien_maps(texte, ville=''):
    """(lat, lng, precision) depuis ce que le client a envoyé, ou ``None``.

    ``'lien'`` : point lu dans le texte (ou plus code retrouvé près de sa
    localité) ; sinon le NOM du lieu est géocodé et la précision de
    ``coords_depuis_adresse`` est rendue telle quelle. Un plus code court sans
    localité ni ville connue ⇒ ``None`` (jamais une position inventée)."""
    texte = (texte or '').strip()
    if not texte:
        return None
    coords, cible = _exactes(texte)
    if coords:
        return (*coords, 'lien')
    if cible is None:
        return None
    court = _plus_code_court(cible)
    if court:
        code, localite = court
        reference = coords_depuis_adresse(localite, ville) if (
            localite or ville) else None
        if reference is None:
            return None
        retrouve = olc_retrouver(code, reference[0], reference[1])
        coords = _coords_olc(retrouve) if retrouve else None
        return (*coords, 'lien') if coords else None
    nom = _nom_lieu(cible)
    if nom:
        return coords_depuis_adresse(nom, ville)
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
        except Exception:  # noqa: BLE001 — best-effort, repli ville (D-ENF22-BLE001)
            logger.warning("coords depuis adresse : échec ignoré, comportement dégradé", exc_info=True)
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
