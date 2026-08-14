"""FG252 — endpoints du brouillon de schéma unifilaire (SVG).

Deux entrées, toutes deux en LECTURE (aucun changement de statut de devis,
couche additive séparée du PDF premium et de `/proposal`, RULE #4) :

  POST /ventes/schema-unifilaire/                → SVG depuis des paramètres
       (panneaux/strings/onduleur/comptage/ONEE) fournis dans le corps.
  GET  /ventes/devis/<id>/schema-unifilaire/     → SVG déduit du devis (lignes
       + etude_params), scopé société.

Sortie : ``Content-Type: image/svg+xml`` (ou JSON via ?format=json renvoyant
les paramètres normalisés + le SVG, ou PDF via ?format=pdf), jamais de prix /
prix d'achat / marge.

PV40 — ``?format=pdf`` rend la MÊME planche en PDF, via le service de rendu
PARTAGÉ ``core.pdf.render_pdf`` (ARC11 : aucun appel direct à WeasyPrint dans
une app, le garde-fou ``scripts/check_platform.py`` l'arme). Ce n'est pas un
document client : c'est la pièce « schéma unifilaire » du dossier technique,
donc elle ne passe évidemment PAS par le moteur de devis premium ni par
``/proposal`` (règle #4) et ne touche aucun statut.
"""
import re

from django.http import HttpResponse, Http404
from rest_framework.decorators import (
    api_view, permission_classes, renderer_classes)
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from rest_framework.settings import api_settings

from authentication.permissions import IsAnyRole
from core.electrique.schema import FORMAT_A4_PAYSAGE
from .models import Devis
from .single_line_diagram import (
    build_single_line_svg,
    normalize_diagram_params,
    diagram_params_from_devis,
)


class PdfRenderer(BaseRenderer):
    """PV40 — rend ``?format=pdf`` NÉGOCIABLE côté DRF.

    Sans ce renderer, la négociation de contenu de DRF refuse un ``format``
    inconnu par un 404 AVANT même d'atteindre la vue : déclarer le format est
    donc la condition pour que ``?format=pdf`` existe. Les vues retournent une
    ``HttpResponse`` déjà construite, ce renderer n'est jamais appelé pour
    sérialiser — il ne fait que rendre le format déclarable.
    """

    media_type = 'application/pdf'
    format = 'pdf'
    charset = None
    render_style = 'binary'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


#: Les renderers PAR DÉFAUT du projet + le PDF — la négociation existante
#: (``?format=json``, Accept navigateur) reste identique.
_RENDERERS = list(api_settings.DEFAULT_RENDERER_CLASSES) + [PdfRenderer]

#: Marge de planche (mm) — le SVG occupe toute la surface utile restante.
_MARGE_MM = 8

_VIEWBOX_RE = re.compile(
    r'viewBox\s*=\s*"\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)\s*"')
_WIDTH_RE = re.compile(r'\bwidth\s*=\s*"([\d.]+)"')


def _largeur_svg(svg):
    """Largeur déclarée par le schéma LUI-MÊME (viewBox, sinon ``width``)."""
    trouve = _VIEWBOX_RE.search(svg or "")
    if trouve:
        return float(trouve.group(1))
    trouve = _WIDTH_RE.search(svg or "")
    return float(trouve.group(1)) if trouve else 0.0


def _format_planche(svg):
    """Format ``@page`` déduit de la taille du schéma — A4 sinon A3, paysage.

    Le noyau (PV39) publie ses planches en pixels CSS à 96 ppp : une planche
    plus large que l'A4 paysage EST une planche A3. Le brouillon v1
    (980 px de large) tient donc en A4 paysage, et un schéma v2 basculé en A3
    par le noyau sort en A3 sans que cette vue ait à le savoir.
    """
    return ("A3 landscape"
            if _largeur_svg(svg) > FORMAT_A4_PAYSAGE[0] else "A4 landscape")


def _pdf_html(svg):
    """Enveloppe HTML minimale : une planche, un schéma, rien d'autre."""
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<title>Schéma unifilaire</title><style>'
        '@page { size: %s; margin: %dmm; }'
        'html, body { margin: 0; padding: 0; }'
        'svg { display: block; width: 100%%; height: auto; }'
        '</style></head><body>%s</body></html>'
        % (_format_planche(svg), _MARGE_MM, svg))


def _svg_response(svg):
    return HttpResponse(svg, content_type="image/svg+xml; charset=utf-8")


def _pdf_response(svg, nom_fichier):
    """PDF de la planche via le service PARTAGÉ ``core.pdf`` (ARC11).

    Import FONCTION-LOCAL : WeasyPrint est une lib lourde, et c'est aussi le
    point d'ancrage que les tests remplacent (``mock.patch('core.pdf.render_pdf')``).
    """
    from core.pdf import render_pdf
    pdf = render_pdf(html=_pdf_html(svg))
    reponse = HttpResponse(pdf, content_type="application/pdf")
    reponse["Content-Disposition"] = (
        'inline; filename="%s"' % nom_fichier)
    return reponse


@api_view(['POST'])
@permission_classes([IsAnyRole])
@renderer_classes(_RENDERERS)
def schema_unifilaire(request):
    """POST /ventes/schema-unifilaire/

    Génère un schéma unifilaire SVG à partir de paramètres bruts. Ne touche
    aucune donnée : pur rendu. ?format=json → ``{params, svg}`` ;
    ?format=pdf → la même planche en PDF (PV40).
    """
    params = normalize_diagram_params(request.data or {})
    svg = build_single_line_svg(params)
    format_demande = request.query_params.get('format')
    if format_demande == 'json':
        return Response({"params": params, "svg": svg})
    if format_demande == 'pdf':
        return _pdf_response(svg, "schema-unifilaire.pdf")
    return _svg_response(svg)


@api_view(['GET'])
@permission_classes([IsAnyRole])
@renderer_classes(_RENDERERS)
def schema_unifilaire_devis(request, pk):
    """GET /ventes/devis/<id>/schema-unifilaire/

    Déduit les paramètres depuis le devis (lignes + etude_params) puis rend le
    SVG. Scopé société : un devis d'une autre société renvoie 404.
    ?format=json → ``{params, svg}`` ; ?format=pdf → la planche en PDF (PV40),
    nommée d'après la référence du devis.
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
    format_demande = request.query_params.get('format')
    if format_demande == 'json':
        return Response({"params": params, "svg": svg})
    if format_demande == 'pdf':
        reference = re.sub(r'[^A-Za-z0-9_.-]+', '-',
                           str(devis.reference or devis.pk))
        return _pdf_response(svg, "schema-unifilaire-%s.pdf" % reference)
    return _svg_response(svg)
