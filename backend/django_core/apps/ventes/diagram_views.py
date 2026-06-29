"""FG252 — endpoints du brouillon de schéma unifilaire (SVG).

Deux entrées, toutes deux en LECTURE (aucun changement de statut de devis,
couche additive séparée du PDF premium et de `/proposal`, RULE #4) :

  POST /ventes/schema-unifilaire/                → SVG depuis des paramètres
       (panneaux/strings/onduleur/comptage/ONEE) fournis dans le corps.
  GET  /ventes/devis/<id>/schema-unifilaire/     → SVG déduit du devis (lignes
       + etude_params), scopé société.

Sortie : ``Content-Type: image/svg+xml`` (ou JSON via ?format=json renvoyant
les paramètres normalisés + le SVG), jamais de prix / prix d'achat / marge.
"""
from django.http import HttpResponse, Http404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from .models import Devis
from .single_line_diagram import (
    build_single_line_svg,
    normalize_diagram_params,
    diagram_params_from_devis,
)


def _svg_response(svg):
    return HttpResponse(svg, content_type="image/svg+xml; charset=utf-8")


@api_view(['POST'])
@permission_classes([IsAnyRole])
def schema_unifilaire(request):
    """POST /ventes/schema-unifilaire/

    Génère un schéma unifilaire SVG à partir de paramètres bruts. Ne touche
    aucune donnée : pur rendu. ?format=json → ``{params, svg}``.
    """
    params = normalize_diagram_params(request.data or {})
    svg = build_single_line_svg(params)
    if request.query_params.get('format') == 'json':
        return Response({"params": params, "svg": svg})
    return _svg_response(svg)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def schema_unifilaire_devis(request, pk):
    """GET /ventes/devis/<id>/schema-unifilaire/

    Déduit les paramètres depuis le devis (lignes + etude_params) puis rend le
    SVG. Scopé société : un devis d'une autre société renvoie 404.
    ?format=json → ``{params, svg}``.
    """
    user = request.user
    qs = Devis.objects.all()
    if getattr(user, 'company_id', None):
        qs = qs.filter(company=user.company)
    elif not user.is_superuser:
        qs = qs.none()
    try:
        devis = qs.prefetch_related('lignes').get(pk=pk)
    except Devis.DoesNotExist:
        raise Http404("Devis introuvable.")

    params = diagram_params_from_devis(devis)
    svg = build_single_line_svg(params)
    if request.query_params.get('format') == 'json':
        return Response({"params": params, "svg": svg})
    return _svg_response(svg)
