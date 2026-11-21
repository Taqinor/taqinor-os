"""Roof-footprint view — returns the OSM building polygon for a pinned lead.

Endpoint: GET /api/django/crm/leads/<id>/roof-footprint/
ACAL421 (décision fondateur du 21/11/2026 : tâche de fond) — the SAME lookup
in the background, Overpass being given 60 s instead of 5 s :
  POST /api/django/crm/leads/<id>/roof-footprint/recherche/  → 202 (job)
  GET  /api/django/crm/leads/roof-footprint/recherche/<job_id>/ → statut
       `en_cours` | `pret` (polygon) | `refus` (motif `osm_injoignable` ou
       `aucun_batiment`, never conflated). Contract :
       `apps/crm/contract_samples/lead_emprise_recherche.json`.

Access: the LeadViewSet scope (company + team/subtree + entity); a lead out
of scope gets the same 404 as a missing id.
Auth (ALEA38): internal account (IsAnyRole — portal → 403) carrying
`crm_voir` (HasPermissionOrLegacy — Commercial terrain → 403).
Response:
  200 {"polygon": [{lat, lng}, ...], "source": "osm", "batiment": {...}}
  200 {"polygon": [], "source": "osm", "batiment": {...},
       "message": "Aucun bâtiment trouvé — tracez le contour manuellement."}
  200 same keys when Overpass is unreachable (HTTP error/timeout), with the
       distinct message « OpenStreetMap n'a pas répondu … » (ACAL421)
  404 lead not found or wrong company
  409 le lead n'a pas de point GPS enregistré (état de la fiche, ERR-ENF11-FUZZ-CRM)

CALX106 — `batiment` is ALWAYS served, with the same keys in all three cases
(building found, no building, Overpass unreachable) : `osm_way_id`, `levels`,
`roof_levels`, `height_m`, `source`, `provenance`, `non_renseignes`. Nothing
is derived: a value OSM does not carry is `null` and `non_renseignes` says, in
French, why. Frozen by
`apps/calepinage/contract_samples/calepinage_empreinte_osm.json`.
"""

from django.http import JsonResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser

from authentication.permissions import HasPermissionOrLegacy, IsAnyRole

from .roof_detect import (
    MOTIF_OSM_INJOIGNABLE, batiment_non_renseigne, fetch_building_footprint,
)

_MSG_NO_BUILDING = (
    "Aucun bâtiment trouvé à cet emplacement — "
    "tracez le contour manuellement."
)
#: ACAL421 — Overpass unreachable (HTTP error, timeout) is NAMED, never
#: presented as « no building » : same response keys, distinct message.
_MSG_OSM_INJOIGNABLE = (
    "OpenStreetMap n'a pas répondu : le contour n'a pas pu être cherché — "
    "réessayez plus tard ou tracez le contour manuellement."
)
_MSG_NO_PIN = (
    "Ce lead n'a pas de point GPS enregistré. "
    "Épinglez d'abord la localisation sur la carte."
)


def _leads_visibles(request):
    """ALEA38 — LA portée du ``LeadViewSet`` (société + équipe/sous-arbre +
    entité), relue sur le viewset lui-même : une seule source de vérité,
    jamais une copie du filtre qui dériverait."""
    from .views import LeadViewSet  # noqa: PLC0415 — évite un cycle d'import (D-ENF22)

    vue = LeadViewSet()
    vue.request = request
    vue.action = 'retrieve'
    vue.format_kwarg = None
    vue.args = ()
    vue.kwargs = {}
    return vue.get_queryset()


@extend_schema(responses={200: inline_serializer("LeadEmpreinteToit", {
    # polygone OSM [[lat, lng], …] (vide : dessin manuel) + bloc bâtiment CALX106.
    "polygon": serializers.ListField(child=serializers.JSONField()),
    "source": serializers.CharField(),
    "batiment": serializers.DictField(),
    "message": serializers.CharField(required=False),
}), 409: OpenApiResponse(description="Le lead n'a pas de point GPS enregistré.")})
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
    from .selectors import repere_toit  # noqa: PLC0415 — import différé (cycle/coût de démarrage) (D-ENF22)

    pin, _source, _contour_utilisable = repere_toit(lead)
    if pin is None:
        # ERR-ENF11-FUZZ-CRM — requête conforme, c'est la FICHE qui n'a pas
        # de repère : 409 (l'atelier n'appelle qu'avec une épingle).
        return JsonResponse(
            {"detail": _MSG_NO_PIN},
            status=409,
        )

    empreinte = fetch_building_footprint(pin["lat"], pin["lng"])

    # fetch_building_footprint returns None on network errors, and an empty
    # polygon on "no building". Both cases degrade gracefully — the client
    # draws manually — and both still carry the `batiment` block (CALX106),
    # whose keys are then all null with the reason named.
    if empreinte is None:
        return JsonResponse({
            "polygon": [],
            "source": "osm",
            "batiment": batiment_non_renseigne(MOTIF_OSM_INJOIGNABLE),
            "message": _MSG_OSM_INJOIGNABLE,
        })

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


# ── ACAL421 — la même recherche en tâche de fond (décision fondateur 21/11) ──

#: Type logique du ``BackgroundJob`` (``core.jobs.submit``, NTPLT29).
KIND_EMPRISE_TOIT = "crm_emprise_toit"

_MSG_EN_COURS = "Recherche du bâtiment en cours…"
_MSG_ECHEC_TACHE = (
    "La recherche du bâtiment n'a pas abouti — réessayez ou tracez le contour "
    "manuellement."
)
_MSG_FILE_INJOIGNABLE = (
    "La recherche du bâtiment n'a pas pu être lancée (file de tâches "
    "injoignable) — réessayez plus tard ou tracez le contour manuellement."
)


def cle_recherche_emprise(job_id):
    """La clé de cache (par société, ``core.cache``) d'une recherche finie."""
    return f"crm:emprise_toit:{job_id}"


def corps_recherche(empreinte):
    """L'issue d'une recherche : ``pret`` (polygone) ou ``refus`` NOMMÉ.

    ``None`` (Overpass injoignable) et ``polygon: []`` (aucun bâtiment) sont
    deux refus DISTINCTS — motif et message propres, jamais confondus.
    """
    if empreinte is None:
        return {"statut": "refus", "motif": "osm_injoignable", "polygon": [],
                "batiment": batiment_non_renseigne(MOTIF_OSM_INJOIGNABLE),
                "message": _MSG_OSM_INJOIGNABLE}
    polygon = empreinte.get("polygon") or []
    batiment = empreinte.get("batiment") \
        or batiment_non_renseigne(MOTIF_OSM_INJOIGNABLE)
    if not polygon:
        return {"statut": "refus", "motif": "aucun_batiment", "polygon": [],
                "batiment": batiment, "message": _MSG_NO_BUILDING}
    return {"statut": "pret", "motif": "", "polygon": polygon,
            "batiment": batiment, "message": ""}


_FORME_RECHERCHE = inline_serializer("LeadEmpriseRecherche", {
    "job_id": serializers.IntegerField(),
    "statut": serializers.CharField(help_text="en_cours | pret | refus"),
    "motif": serializers.CharField(),
    "polygon": serializers.ListField(child=serializers.JSONField()),
    "source": serializers.CharField(),
    "batiment": serializers.DictField(allow_null=True),
    "message": serializers.CharField(),
})


@extend_schema(request=None, responses={
    202: _FORME_RECHERCHE,
    403: OpenApiResponse(description="Compte portail ou sans crm_voir."),
    404: OpenApiResponse(description="Lead introuvable ou hors portée."),
    409: OpenApiResponse(description="Le lead n'a pas de point GPS enregistré."),
    503: OpenApiResponse(description="File de tâches injoignable."),
})
@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([IsAnyRole, HasPermissionOrLegacy('crm_voir')])
def lead_roof_footprint_recherche(request, lead_id):
    """Lance la recherche de l'emprise en tâche de fond (202 + ``job_id``).

    Mêmes gardes que ``lead_roof_footprint`` (portée du ``LeadViewSet``,
    ``crm_voir``) ; société et utilisateur FORCÉS côté serveur par
    ``core.jobs.submit`` — aucun champ du corps n'est lu.
    """
    lead = _leads_visibles(request).filter(pk=lead_id).first()
    if lead is None:
        return JsonResponse({"detail": "Lead introuvable."}, status=404)

    from .selectors import repere_toit  # noqa: PLC0415 — import différé (cycle/coût de démarrage) (D-ENF22)

    pin, _source, _contour_utilisable = repere_toit(lead)
    if pin is None:
        return JsonResponse({"detail": _MSG_NO_PIN}, status=409)

    from core.jobs import submit  # noqa: PLC0415 — import différé (D-ENF22)

    from .tasks import chercher_emprise_toit_task  # noqa: PLC0415 — import différé (D-ENF22)

    try:
        job = submit(KIND_EMPRISE_TOIT, chercher_emprise_toit_task,
                     company=request.user.company, user=request.user,
                     lat=float(pin["lat"]), lng=float(pin["lng"]))
    except Exception:  # noqa: BLE001 — broker injoignable : nommé, jamais un 500 (D-ENF22-BLE001)
        return JsonResponse({"detail": _MSG_FILE_INJOIGNABLE}, status=503)
    return JsonResponse({
        "job_id": job.pk,
        "statut": "en_cours",
        "motif": "",
        "polygon": [],
        "source": "osm",
        "batiment": None,
        "message": _MSG_EN_COURS,
    }, status=202)


@extend_schema(responses={
    200: _FORME_RECHERCHE,
    403: OpenApiResponse(description="Compte portail ou sans crm_voir."),
    404: OpenApiResponse(description="Recherche introuvable (autre société "
                                     "ou autre utilisateur)."),
})
@api_view(["GET"])
@permission_classes([IsAnyRole, HasPermissionOrLegacy('crm_voir')])
def roof_footprint_recherche_statut(request, job_id):
    """L'état d'une recherche lancée par CET utilisateur : ``en_cours``,
    ``pret`` (contour) ou ``refus`` (motif nommé). Le job d'un autre
    (utilisateur ou société) est introuvable (404), jamais « interdit »."""
    from core import cache as cache_tenant  # noqa: PLC0415 — import différé (D-ENF22)
    from core.models import BackgroundJob  # noqa: PLC0415 — import différé (D-ENF22)

    job = BackgroundJob.objects.filter(
        pk=job_id, company=request.user.company, user=request.user,
        kind=KIND_EMPRISE_TOIT).first()
    if job is None:
        return JsonResponse({"detail": "Recherche introuvable."}, status=404)

    charge = None
    if job.statut == BackgroundJob.STATUT_DONE and job.result_file_key:
        charge = cache_tenant.get(job.company_id, job.result_file_key)
    if job.statut in (BackgroundJob.STATUT_QUEUED, BackgroundJob.STATUT_RUNNING):
        charge = {"statut": "en_cours", "motif": "", "polygon": [],
                  "batiment": None, "message": _MSG_EN_COURS}
    elif charge is None:
        charge = {"statut": "refus", "motif": "echec_tache", "polygon": [],
                  "batiment": None, "message": _MSG_ECHEC_TACHE}
    return JsonResponse({
        "job_id": job.pk,
        "statut": charge["statut"],
        "motif": charge["motif"],
        "polygon": charge["polygon"],
        "source": "osm",
        "batiment": charge["batiment"],
        "message": charge["message"],
    })
