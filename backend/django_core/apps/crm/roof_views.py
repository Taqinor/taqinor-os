"""Roof-footprint view — returns the OSM building polygon for a pinned lead.

Endpoint: GET /api/django/crm/leads/<id>/roof-footprint/

Access: company-scoped (resolves lead by company; 404 for another company's lead).
Auth: standard IsAuthenticated (inherits from the rest of the CRM views).
Response:
  200 {"polygon": [{lat, lng}, ...], "source": "osm", "batiment": {...}}
  200 {"polygon": [], "source": "osm", "batiment": {...},
       "message": "Aucun bâtiment trouvé — tracez le contour manuellement."}
  404 lead not found or wrong company
  400 le lead n'a pas de point GPS enregistré

CALX106 — `batiment` is ALWAYS served, with the same keys in all three cases
(building found, no building, Overpass unreachable) : `osm_way_id`, `levels`,
`roof_levels`, `height_m`, `source`, `provenance`, `non_renseignes`. Nothing
is derived: a value OSM does not carry is `null` and `non_renseignes` says, in
French, why. Frozen by
`apps/calepinage/contract_samples/calepinage_empreinte_osm.json`.
"""

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from .roof_detect import (
    MOTIF_OSM_INJOIGNABLE, batiment_non_renseigne, fetch_building_footprint,
)

_MSG_NO_BUILDING = (
    "Aucun bâtiment trouvé à cet emplacement — "
    "tracez le contour manuellement."
)
_MSG_NO_PIN = (
    "Ce lead n'a pas de point GPS enregistré. "
    "Épinglez d'abord la localisation sur la carte."
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def lead_roof_footprint(request, lead_id):
    """Return the OSM building-footprint polygon for a pinned lead.

    Company-scoped: only leads owned by request.user.company are accessible.
    Best-effort: if Overpass is unreachable the polygon is empty and the client
    falls back to manual drawing.
    """
    # Function-local import to keep cross-app boundary clean.
    from .models import Lead  # noqa: PLC0415

    try:
        lead = Lead.objects.get(pk=lead_id, company=request.user.company)
    except Lead.DoesNotExist:
        return JsonResponse(
            {"detail": "Lead introuvable."},
            status=404,
        )

    # Resolve the pinned GPS point.  Prefer roof_point (the explicit pin set
    # via the toiture tool) and fall back to gps_lat/gps_lng if available.
    lat = lng = None

    if lead.roof_point and isinstance(lead.roof_point, dict):
        try:
            lat = float(lead.roof_point["lat"])
            lng = float(lead.roof_point["lng"])
        except (KeyError, TypeError, ValueError):
            lat = lng = None

    if lat is None and lead.gps_lat is not None and lead.gps_lng is not None:
        try:
            lat = float(lead.gps_lat)
            lng = float(lead.gps_lng)
        except (TypeError, ValueError):
            lat = lng = None

    if lat is None:
        return JsonResponse(
            {"detail": _MSG_NO_PIN},
            status=400,
        )

    empreinte = fetch_building_footprint(lat, lng)

    # fetch_building_footprint returns None on network errors, and an empty
    # polygon on "no building". Both cases degrade gracefully — the client
    # draws manually — and both still carry the `batiment` block (CALX106),
    # whose keys are then all null with the reason named.
    if empreinte is None:
        empreinte = {
            "polygon": [],
            "batiment": batiment_non_renseigne(MOTIF_OSM_INJOIGNABLE),
        }

    polygon = empreinte.get("polygon") or []
    batiment = empreinte.get("batiment") \
        or batiment_non_renseigne(MOTIF_OSM_INJOIGNABLE)

    if not polygon:
        return JsonResponse({
            "polygon": [],
            "source": "osm",
            "batiment": batiment,
            "message": _MSG_NO_BUILDING,
        })

    return JsonResponse({
        "polygon": polygon,
        "source": "osm",
        "batiment": batiment,
    })
