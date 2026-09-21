"""OSM building-footprint roof-outline auto-detection.

Approach (free, no API key):
  Given a GPS point, query the public Overpass API
  (https://overpass-api.de) for the nearest building way within 25 m.
  Parse the way's geometry into an ordered list of {lat, lng} vertices
  and return it so the client/seller can skip tracing the roof outline manually.

Limitation — obstacle detection:
  Automatic obstacle detection (chimneys, HVAC units, skylights…) requires
  high-resolution aerial imagery (Nearmap, EagleView, Google Solar API).
  Google Solar API has NO coverage in Morocco. Nearmap/EagleView are paid
  services not approved for this project.
  => Obstacle detection is explicitly OUT OF SCOPE for this feature.
     The returned polygon is the building footprint only; the user must
     mark obstacles manually in the roof-layout tool.

Network policy:
  All calls are best-effort with a short timeout (~8 s).
  Any failure (network error, Overpass down, rate-limited, no building at
  the given point) returns None (or an empty polygon) so the caller falls
  back gracefully to manual drawing. No exception ever reaches the HTTP layer.

CALX106 — what the OSM way SAYS about the building:
  The Overpass query already asks for `out geom`, so every answer carries the
  way's `tags` alongside its nodes; until CALX106 those tags were thrown away.
  `_parse_geometry` now keeps the THREE useful ones and publishes each with
  its provenance (`osm:<tag>`) and the way id:

    building:levels -> levels        roof:levels -> roof_levels
    height          -> height_m

  Three rules, non-negotiable (D-CALX 7 « zéro chiffre inventé »):
    * NOTHING is converted. A number of storeys stays a number of storeys, a
      height stays a height — no « 3 m per floor » is ever assumed, in either
      direction.
    * A tag that is absent (or that OSM writes in a form we cannot read, e.g.
      feet, a range, a list) publishes `null` AND names, in French, why —
      `non_renseignes[<clé>]`. Never a default, never a zero.
    * Every published value carries `source: "openstreetmap"` and a
      `provenance[<clé>] = "osm:<tag>"`. No value published => `source: null`.
"""

import logging
import re

logger = logging.getLogger(__name__)

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_TIMEOUT_S = 8
_RADIUS_M = 25  # search radius in metres around the pin

#: CALX106 — the provenance published next to every value read from OSM.
SOURCE_OSM = "openstreetmap"

#: CALX106 — « 7.5 », « 7,5 », « 12 m », « 12m ». Anything else (feet `25'`,
#: a range `10-12`, a list `3;4`, a word) is NOT readable and says so.
_METRES = re.compile(r"^(\d+(?:[.,]\d+)?)\s*m?$", re.IGNORECASE)
_ENTIER = re.compile(r"^(\d+)$")


def _lire_metres(brut):
    """('valeur en mètres', None) or (None, 'motif français')."""
    texte = str(brut).strip()
    trouve = _METRES.match(texte)
    if not trouve:
        return None, ("cette écriture n'est pas une hauteur en mètres "
                      "lisible (pieds, intervalle, liste ou texte libre).")
    valeur = float(trouve.group(1).replace(",", "."))
    if valeur <= 0:
        return None, "une hauteur nulle ou négative n'est pas une hauteur."
    return valeur, None


def _lire_entier(brut):
    """('nombre de niveaux', None) or (None, 'motif français')."""
    texte = str(brut).strip()
    trouve = _ENTIER.match(texte)
    if not trouve:
        return None, ("cette écriture n'est pas un nombre entier de niveaux "
                      "(valeur décimale, intervalle, liste ou texte libre).")
    return int(trouve.group(1)), None


#: CALX106 — (clé publiée, tag OSM, lecteur). A tag that is NOT in this table
#: does not exist for us: we never guess from a neighbouring tag.
_TAGS_RETENUS = (
    ("levels", "building:levels", _lire_entier),
    ("roof_levels", "roof:levels", _lire_entier),
    ("height_m", "height", _lire_metres),
)

#: Motifs served when there is simply nothing to read.
MOTIF_AUCUN_BATIMENT = (
    "aucun bâtiment OpenStreetMap n'a été trouvé à cet emplacement."
)
MOTIF_OSM_INJOIGNABLE = (
    "OpenStreetMap n'a pas répondu : rien n'a pu être lu."
)


def batiment_non_renseigne(motif: str) -> dict:
    """The building block when NOTHING could be read — every key `null`.

    `motif` (French) says why, key by key. Published as-is by the view so the
    shape served never changes between « found », « not found » and
    « Overpass unreachable ».
    """
    batiment = {"osm_way_id": None}
    for cle, _tag, _lecteur in _TAGS_RETENUS:
        batiment[cle] = None
    batiment["source"] = None
    batiment["provenance"] = {}
    batiment["non_renseignes"] = {cle: motif
                                  for cle, _tag, _lecteur in _TAGS_RETENUS}
    return batiment


def _batiment_depuis_tags(tags: dict, osm_way_id) -> dict:
    """Read the retained tags of ONE OSM way — never derive, never default."""
    batiment = {"osm_way_id": osm_way_id}
    provenance = {}
    non_renseignes = {}
    for cle, tag, lecteur in _TAGS_RETENUS:
        brut = (tags or {}).get(tag)
        if brut is None or str(brut).strip() == "":
            batiment[cle] = None
            non_renseignes[cle] = (
                f"le bâtiment OpenStreetMap ne porte pas le tag « {tag} »."
            )
            continue
        valeur, motif = lecteur(brut)
        if valeur is None:
            batiment[cle] = None
            non_renseignes[cle] = (
                f"le tag OpenStreetMap « {tag} » vaut « {brut} » : {motif}"
            )
            continue
        batiment[cle] = valeur
        provenance[cle] = f"osm:{tag}"
    batiment["source"] = SOURCE_OSM if provenance else None
    batiment["provenance"] = provenance
    batiment["non_renseignes"] = non_renseignes
    return batiment


def _build_query(lat: float, lng: float) -> str:
    """Return an Overpass QL query that fetches the nearest building polygon."""
    # `way(around:R,LAT,LNG)["building"]` finds all building ways in radius R.
    # `(._;>;)` recurses to fetch the nodes that form the way.
    # `out geom` returns coordinates inline so we don't need a second request.
    return (
        f"[out:json][timeout:{_TIMEOUT_S}];"
        f'way(around:{_RADIUS_M},{lat},{lng})["building"];'
        f"(._;>;);out geom;"
    )


def _parse_geometry(data: dict) -> dict:
    """Extract the footprint AND what the OSM way says about the building.

    Returns (CALX106) ``{"polygon": [...], "batiment": {...}}`` for the first
    usable building way found:

      * ``polygon`` — ordered ``{"lat": float, "lng": float}`` vertices (at
        least 3), or ``[]`` when nothing usable is in the response;
      * ``batiment`` — ``osm_way_id``, ``levels``, ``roof_levels``,
        ``height_m``, ``source``, ``provenance``, ``non_renseignes``. Each
        published value comes from ONE tag, named in ``provenance``; anything
        absent or unreadable is ``null`` and named in ``non_renseignes``.
    """
    elements = data.get("elements", []) if isinstance(data, dict) else []
    # Find the first element that is a way with inline geometry.
    for el in elements:
        if el.get("type") == "way" and el.get("geometry"):
            vertices = []
            for node in el["geometry"]:
                try:
                    vertices.append({"lat": float(node["lat"]), "lng": float(node["lon"])})
                except (KeyError, TypeError, ValueError):
                    continue
            if len(vertices) >= 3:
                return {
                    "polygon": vertices,
                    "batiment": _batiment_depuis_tags(el.get("tags"),
                                                      el.get("id")),
                }
    return {"polygon": [],
            "batiment": batiment_non_renseigne(MOTIF_AUCUN_BATIMENT)}


def fetch_building_footprint(lat: float, lng: float) -> dict | None:
    """Query Overpass for the building footprint at (lat, lng).

    Returns:
        ``{"polygon": [...], "batiment": {...}}`` — the polygon holds at least
        3 vertices when a building is found and is ``[]`` when no building
        exists at that location (CALX106 : the ``batiment`` block is served in
        BOTH cases, all keys ``null`` and named when there is nothing to read)
        — or ``None`` on any network/parse failure.

    This function NEVER raises — all failures produce None.
    """
    try:
        import requests as _requests
    except ImportError:
        import urllib.request as _urllib_request
        import urllib.parse as _urllib_parse
        import json as _json

        query = _build_query(lat, lng)
        encoded = _urllib_parse.urlencode({"data": query}).encode()
        req = _urllib_request.Request(
            _OVERPASS_URL,
            data=encoded,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with _urllib_request.urlopen(req, timeout=_TIMEOUT_S) as resp:
                data = _json.loads(resp.read().decode())
            return _parse_geometry(data)
        except Exception as exc:
            logger.info("OSM footprint lookup failed (urllib): %s", exc)
            return None

    query = _build_query(lat, lng)
    try:
        resp = _requests.post(
            _OVERPASS_URL,
            data={"data": query},
            timeout=_TIMEOUT_S,
        )
        resp.raise_for_status()
        return _parse_geometry(resp.json())
    except Exception as exc:
        logger.info("OSM footprint lookup failed (requests): %s", exc)
        return None
