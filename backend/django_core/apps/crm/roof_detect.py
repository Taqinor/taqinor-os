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
  the given point) returns None/[] so the caller falls back gracefully to
  manual drawing. No exception is ever propagated to the HTTP layer.
"""

import logging

logger = logging.getLogger(__name__)

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_TIMEOUT_S = 8
_RADIUS_M = 25  # search radius in metres around the pin


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


def _parse_geometry(data: dict) -> list:
    """Extract ordered vertices from an Overpass JSON response.

    Returns a list of {"lat": float, "lng": float} dicts for the first
    building way found, or [] if nothing usable is in the response.
    """
    elements = data.get("elements", [])
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
                return vertices
    return []


def fetch_building_footprint(lat: float, lng: float) -> list | None:
    """Query Overpass for the building footprint at (lat, lng).

    Returns:
        A list of {"lat": float, "lng": float} vertices (at least 3) when a
        building is found, [] when no building exists at that location, or
        None on any network/parse failure.

    This function NEVER raises — all failures produce None/[].
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
