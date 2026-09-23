"""Les DOCUMENTS du lot 6 (« Livrables & rapports ») servis en HTTP.

POURQUOI UN FICHIER NEUF (D-CALX 13)
------------------------------------
``views/sorties.py`` est déjà partagé par les sorties historiques (planche,
note, DXF, tableur, dossier technique) : chaque pièce du lot 6 y aurait
rouvert le même fichier. Les actions du lot vivent donc ICI, surface
APPEND-ONLY (une section par tâche, ajoutée EN FIN), et chacune se rattache au
``CalepinageViewSet`` par AFFECTATION D'ATTRIBUT écrite — le nom d'attribut
est EXACTEMENT ``fonction.__name__`` (DRF mappe par ``__name__``, piège de
classe #105). L'import qui exécute ce module vit en fin de
``views/rattachements.py``, donc AVANT ``router.register``.

CE QUI EST GARANTI, ET PAR QUI
------------------------------
* **Société** — ``self.get_object()`` passe par le ``get_queryset`` du viewset
  pivot : un calepinage d'une autre société est INTROUVABLE (404) ;
* **Permission** — chaque action déclare ``PeutVoirCalepinage`` ;
* **Aucun statut ne bouge** (règle #4) et aucune pièce n'est un devis client :
  ``/proposal`` reste le seul PDF de devis ; aucune pièce ne porte de montant
  (D5).
"""
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from .calepinages import CalepinageViewSet


# ── CALX297 — le rapport d'étude (PDF) ──────────────────────────────────────
@extend_schema(
    responses={200: OpenApiTypes.BINARY},
    parameters=[OpenApiParameter(
        name='langue', type=OpenApiTypes.STR, required=False,
        description="Langue de sortie demandée (fr, en ; ar retombe sur le "
                    "français en le disant au pied du document).")],
)
@action(detail=True, methods=['get'], url_path='rapport-etude.pdf',
        url_name='rapport-etude-pdf', permission_classes=[PeutVoirCalepinage])
def rapport_etude_pdf(self, request, pk=None):
    """CALX297 — le rapport d'étude : site, système, pertes, production…

    * **200** — le PDF, nommé d'après le calepinage ;
    * **400** — aucun résultat de moteur, ou une donnée refusée (clé de coût,
      températures illisibles) : le motif français et le champ NOMMÉ.
    """
    from ..services.planche import nom_de_fichier
    from ..services.rapport import RapportRefuse, rendre_rapport
    from .sorties import MIME_PDF, reponse_de_fichier

    calepinage = self.get_object()  # borné société par get_queryset
    langue = request.query_params.get('langue')
    try:
        octets = rendre_rapport(calepinage, company=calepinage.company,
                                langue=langue)
    except RapportRefuse as refus:
        return Response({refus.champ or 'resultat': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return reponse_de_fichier(
        octets, mime=MIME_PDF,
        nom_fichier=nom_de_fichier(calepinage, 'rapport-etude.pdf'))


CalepinageViewSet.rapport_etude_pdf = rapport_etude_pdf


# ── CALX308 — le diagramme de pertes (SVG dessiné par le serveur) ──────────
@extend_schema(
    responses={200: OpenApiTypes.BINARY},
    parameters=[OpenApiParameter(
        name='langue', type=OpenApiTypes.STR, required=False,
        description='Langue des libellés (fr, en ; ar retombe sur fr).')],
)
@action(detail=True, methods=['get'], url_path='diagramme-pertes.svg',
        url_name='diagramme-pertes-svg',
        permission_classes=[PeutVoirCalepinage])
def diagramme_pertes_svg(self, request, pk=None):
    """CALX308 — la cascade de pertes en SVG autonome (aucun accès réseau).

    * **200** — le SVG, nommé d'après le calepinage ;
    * **400** — aucun résultat, aucune cascade produite, ou une donnée
      refusée : le motif français et le champ NOMMÉ.
    """
    from ..services.diagramme_pertes import DiagrammeRefuse, svg_du_calepinage
    from ..services.planche import nom_de_fichier
    from ..services.rapport import RapportRefuse
    from .sorties import MIME_SVG, reponse_de_fichier

    calepinage = self.get_object()  # borné société par get_queryset
    try:
        svg = svg_du_calepinage(calepinage,
                                langue=request.query_params.get('langue'))
    except (DiagrammeRefuse, RapportRefuse) as refus:
        return Response({refus.champ or 'cascade': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return reponse_de_fichier(
        svg.encode('utf-8'), mime=MIME_SVG,
        nom_fichier=nom_de_fichier(calepinage, 'diagramme-pertes.svg'))


CalepinageViewSet.diagramme_pertes_svg = diagramme_pertes_svg


# ── CALX310 — le plan de câblage des chaînes (PDF et DXF) ──────────────────
def _refus_plan_cablage(refus):
    """400 + la donnée NOMMÉE (géométrie, chaînage, pare-feu de montants)."""
    return Response({getattr(refus, 'champ', '') or 'electrique.chainage':
                     str(refus)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(responses={200: OpenApiTypes.BINARY})
@action(detail=True, methods=['get'], url_path='plan-cablage.pdf',
        url_name='plan-cablage-pdf', permission_classes=[PeutVoirCalepinage])
def plan_cablage_pdf(self, request, pk=None):
    """CALX310 — le plan de câblage : modules teintés par chaîne, légende.

    * **200** — le PDF A3, nommé d'après le calepinage ;
    * **400** — aucune conception, aucune chaîne publiée, ou une donnée
      refusée : le motif français et le champ NOMMÉ.
    """
    from ..services.documents.plan_cablage import rendre_plan_cablage_pdf
    from ..services.planche import PlancheRefusee, nom_de_fichier
    from ..services.rapport import RapportRefuse
    from .sorties import MIME_PDF, reponse_de_fichier

    calepinage = self.get_object()  # borné société par get_queryset
    try:
        octets = rendre_plan_cablage_pdf(calepinage,
                                         company=calepinage.company)
    except (PlancheRefusee, RapportRefuse) as refus:
        return _refus_plan_cablage(refus)
    return reponse_de_fichier(
        octets, mime=MIME_PDF,
        nom_fichier=nom_de_fichier(calepinage, 'plan-cablage.pdf'))


CalepinageViewSet.plan_cablage_pdf = plan_cablage_pdf


@extend_schema(responses={200: OpenApiTypes.BINARY})
@action(detail=True, methods=['get'], url_path='plan-cablage.dxf',
        url_name='plan-cablage-dxf', permission_classes=[PeutVoirCalepinage])
def plan_cablage_dxf(self, request, pk=None):
    """CALX310 — le DXF de pose AVEC le calque ``CHAINES``.

    * **200** — le DXF (mètres), nommé d'après le calepinage ;
    * **400** — mêmes refus que le PDF, champ NOMMÉ.
    """
    from ..services.documents.plan_cablage import exporter_plan_cablage_dxf
    from ..services.planche import PlancheRefusee, nom_de_fichier
    from ..services.rapport import RapportRefuse
    from .sorties import MIME_DXF, reponse_de_fichier

    calepinage = self.get_object()  # borné société par get_queryset
    try:
        octets = exporter_plan_cablage_dxf(calepinage)
    except (PlancheRefusee, RapportRefuse) as refus:
        return _refus_plan_cablage(refus)
    return reponse_de_fichier(
        octets, mime=MIME_DXF,
        nom_fichier=nom_de_fichier(calepinage, 'plan-cablage.dxf'))


CalepinageViewSet.plan_cablage_dxf = plan_cablage_dxf


# ── CALX312 — l'export JSON versionné du projet et de ses résultats ────────
# Imports de SECTION (fichier append-only : l'en-tête ne se rouvre pas).
from drf_spectacular.utils import inline_serializer  # noqa: E402
from rest_framework import serializers as drf_serializers  # noqa: E402
from rest_framework.renderers import JSONRenderer  # noqa: E402

#: La forme du contrat ``export_projet.json`` (onze clés) — jamais un
#: « type: object » vide, qui validerait tout (check_openapi_shapes, R1).
EXPORT_PROJET_SCHEMA = inline_serializer('CalepinageExportProjet', {
    'format_version': drf_serializers.IntegerField(),
    'produit_le': drf_serializers.CharField(),
    'calepinage': drf_serializers.DictField(),
    'site': drf_serializers.DictField(),
    'equipements': drf_serializers.DictField(),
    'roof_layout': drf_serializers.JSONField(allow_null=True),
    'layout_hash': drf_serializers.CharField(allow_null=True),
    'version_moteur': drf_serializers.CharField(allow_null=True),
    'resultat': drf_serializers.JSONField(allow_null=True),
    'pertes': drf_serializers.ListField(child=drf_serializers.DictField()),
    'avertissements': drf_serializers.ListField(
        child=drf_serializers.CharField()),
})


@extend_schema(responses={200: EXPORT_PROJET_SCHEMA})
@action(detail=True, methods=['get'], url_path='export-projet.json',
        url_name='export-projet-json', permission_classes=[PeutVoirCalepinage],
        renderer_classes=[JSONRenderer])
def export_projet_json(self, request, pk=None):
    """CALX312 — projet + résultats en JSON, forme ``export_projet.json``.

    * **200** — le document, en TÉLÉCHARGEMENT nommé d'après le calepinage
      (``Content-Disposition: attachment``, même nom assaini que
      ``reponse_de_fichier``). Servi par une ``Response`` DRF au rendu JSON
      SEUL (jamais l'API navigable) plutôt que par un ``HttpResponse`` nu :
      la garde de surface CAL122 (``tests/test_aucun_prix_achat.py``) balaie
      le ``.data`` de chaque GET — un corps brut lui échapperait ;
    * **400** — une clé de montant, une valeur non finie ou des températures
      illisibles : le motif français et le champ NOMMÉ.
    """
    from ..services.export_projet import ExportProjetRefuse, document_de_projet
    from ..services.planche import nom_de_fichier

    calepinage = self.get_object()  # borné société par get_queryset
    try:
        document = document_de_projet(calepinage)
    except ExportProjetRefuse as refus:
        return Response({refus.champ or 'resultat': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    reponse = Response(document)
    reponse['Content-Disposition'] = 'attachment; filename="%s"' % (
        nom_de_fichier(calepinage, 'export-projet.json'))
    return reponse


CalepinageViewSet.export_projet_json = export_projet_json
