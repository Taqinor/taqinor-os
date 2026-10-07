"""Roof-footprint view — returns the OSM building polygon for a pinned lead.

Endpoint: GET /api/django/crm/leads/<id>/roof-footprint/

Access: the LeadViewSet scope (company + team/subtree + entity); a lead out
of scope gets the same 404 as a missing id.
Auth (ALEA38): internal account (IsAnyRole — portal → 403) carrying
`crm_voir` (HasPermissionOrLegacy — Commercial terrain → 403).
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

from authentication.permissions import HasPermissionOrLegacy, IsAnyRole

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


def _leads_visibles(request):
    """ALEA38 — LA portée du ``LeadViewSet`` (société + équipe/sous-arbre +
    entité), relue sur le viewset lui-même : une seule source de vérité,
    jamais une copie du filtre qui dériverait."""
    from .views import LeadViewSet  # noqa: PLC0415 — évite un cycle d'import

    vue = LeadViewSet()
    vue.request = request
    vue.action = 'retrieve'
    vue.format_kwarg = None
    vue.args = ()
    vue.kwargs = {}
    return vue.get_queryset()


@api_view(["GET"])
@permission_classes([IsAnyRole, HasPermissionOrLegacy('crm_voir')])
def lead_roof_footprint(request, lead_id):
    """Return the OSM building-footprint polygon for a pinned lead.

    ALEA38 — gardée comme la fiche lead : compte INTERNE (``IsAnyRole`` — un
    compte portail reçoit 403) portant ``crm_voir`` (un Commercial terrain,
    sans ce droit, reçoit 403), et lead dans la PORTÉE du ``LeadViewSet``
    (hors portée → 404, identique à un id absent). Aucun rôle portant
    ``calepinage_*`` n'est privé de ``crm_voir`` dans le registre canonique :
    l'atelier calepinage garde l'accès. Aucun appel Overpass n'est tenté
    avant que ces gardes passent.
    Best-effort: if Overpass is unreachable the polygon is empty and the client
    falls back to manual drawing.
    """
    lead = _leads_visibles(request).filter(pk=lead_id).first()
    if lead is None:
        return JsonResponse(
            {"detail": "Lead introuvable."},
            status=404,
        )

    # QJR598 — LE repère toit du lead (le GPS corrigé prime sur l'épingle).
    from .selectors import repere_toit  # noqa: PLC0415

    pin, _source, _contour_utilisable = repere_toit(lead)
    if pin is None:
        return JsonResponse(
            {"detail": _MSG_NO_PIN},
            status=400,
        )

    empreinte = fetch_building_footprint(pin["lat"], pin["lng"])

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
