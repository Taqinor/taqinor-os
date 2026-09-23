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

from ..permissions import PeutGererCalepinage, PeutVoirCalepinage
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
    # CALX307 (clôture M4) — la sélection de sections de la SOCIÉTÉ
    # s'applique au rendu : ``None`` = toutes les sections, le rapport
    # d'aujourd'hui octet pour octet ; un réglage invalide est REFUSÉ en
    # nommant ``sections`` (RapportRefuse, attrapé ci-dessous).
    from ..selectors import parametres_de_societe
    from ..services.rapport.sections_societe import sections_retenues
    try:
        octets = rendre_rapport(
            calepinage, company=calepinage.company, langue=langue,
            sections=sections_retenues(
                parametres_de_societe(calepinage.company)))
    except RapportRefuse as refus:
        return Response({refus.champ or 'resultat': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    # CALX322 — chaque téléchargement RÉUSSI devient une version retrouvable
    # (``services/documents/versions_document.py``) ; BEST-EFFORT, comme le
    # journal (``services/journal.py``) : un incident de versionnement ne
    # doit jamais faire échouer la remise du document lui-même.
    from ..services.documents.versions_document import (
        enregistrer_version_document,
    )
    try:
        enregistrer_version_document(
            calepinage, code='rapport_etude', octets=octets, langue=langue,
            user=getattr(request, 'user', None))
    except Exception:  # noqa: BLE001 — un versionnement perdu ne casse rien
        import logging

        logging.getLogger(__name__).exception(
            'CALX322 : version de rapport_etude perdue (calepinage %s)',
            calepinage.pk)
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


# ── CALX321 — l'inventaire des documents du lot 6, DONNÉE PAR DONNÉE ───────
@extend_schema(responses={200: OpenApiTypes.OBJECT})
@action(detail=True, methods=['get'], url_path='documents',
        url_name='documents', permission_classes=[PeutVoirCalepinage])
def documents(self, request, pk=None):
    """CALX321 — l'inventaire des NEUF documents du lot 6 (contrat
    ``calepinage_documents.json``), DISTINCT de l'inventaire des sorties
    techniques (``sorties/``, CAL175). Une pièce indisponible reste LISTÉE,
    avec ``manque[]`` qui NOMME le ou les champs à saisir."""
    from ..services.documents import inventaire_des_documents

    calepinage = self.get_object()  # borné société par get_queryset
    return Response(inventaire_des_documents(calepinage))


CalepinageViewSet.documents = documents


# ── CALX323 — l'aperçu HTML d'un document, AVANT le PDF ─────────────────────
@extend_schema(
    responses={200: OpenApiTypes.STR},
    parameters=[
        OpenApiParameter(
            name='code', type=OpenApiTypes.STR, required=True,
            description='Code du document (inventaire GET documents/).'),
        OpenApiParameter(
            name='langue', type=OpenApiTypes.STR, required=False,
            description='Langue de sortie demandée (fr, en).'),
    ],
)
@action(detail=True, methods=['get'], url_path='apercu-document',
        url_name='apercu-document', permission_classes=[PeutVoirCalepinage])
def apercu_document(self, request, pk=None):
    """CALX323 — le HTML EXACT que consomme le rendu PDF de ``?code=``.

    UNE seule fonction de mise en page par document (``services/documents``
    ``::MISES_EN_PAGE``) : cette action et le rendu PDF (``rapport-etude
    .pdf/``…) appellent la MÊME — aucune rastérisation, aucun second
    gabarit qui pourrait diverger.

    * **200** — le document en ``text/html``, sans PDF ;
    * **400** — ``code`` absent/inconnu (le code NOMMÉ), ou le document
      refuse (motif et champ NOMMÉS, identiques au rendu PDF).
    """
    from django.http import HttpResponse

    from ..services.documents import mise_en_page
    from ..services.rapport import RapportRefuse

    #: Les refus RÉELLEMENT levés par les mises en page aujourd'hui
    #: enregistrées (``MISES_EN_PAGE``) — un document neuf AJOUTE sa
    #: propre exception ici quand il rejoint le registre, exactement comme
    #: ``sorties.py::_tableur`` capture ``(ExportRefuse, PlancheRefusee)``.
    REFUS_CONNUS = (RapportRefuse,)

    calepinage = self.get_object()  # borné société par get_queryset
    code = (request.query_params.get('code') or '').strip()
    if not code:
        return Response({'code': "Paramètre « code » requis (voir GET "
                                 "documents/)."},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        fonction = mise_en_page(code)
    except KeyError as refus:
        # ``KeyError.__str__`` ré-encapsule son message entre guillemets —
        # ``args[0]`` reste le texte FRANÇAIS propre, tel qu'écrit.
        message = refus.args[0] if refus.args else str(refus)
        return Response({'code': message}, status=status.HTTP_400_BAD_REQUEST)

    langue = request.query_params.get('langue')
    try:
        html = fonction(calepinage, langue=langue)
    except REFUS_CONNUS as refus:
        return Response({refus.champ or 'resultat': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return HttpResponse(html, content_type='text/html; charset=utf-8')


CalepinageViewSet.apercu_document = apercu_document


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

#: La forme du contrat ``export_projet.json`` (douze clés) — jamais un
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
    # CALX314 — la provenance partagée avec le XLSX et le DXF.
    'provenance': drf_serializers.ListField(
        child=drf_serializers.DictField()),
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


# ── CALX302 — le dépôt d'une image PRODUITE PAR LE NAVIGATEUR ──────────────
@extend_schema(request=OpenApiTypes.OBJECT,
               responses={201: OpenApiTypes.OBJECT})
@action(detail=True, methods=['post'], url_path='image-document',
        url_name='image-document', permission_classes=[PeutVoirCalepinage])
def image_document(self, request, pk=None):
    """CALX302 — dépose une image PRODUITE PAR LE NAVIGATEUR (carte de
    chaleur d'ombrage, diagramme de pertes, rendu 3D) — genre parmi une
    énumération FERMÉE (``ombrage``, ``sankey``, ``plan3d``), stockée en
    ``records.Attachment`` (MinIO, jamais un binaire au dépôt). Corps
    ``{genre, fichier}`` — ``fichier`` accepte un fichier multipart OU une
    data-URL base64 produite par le navigateur.

    * **201** — ``{ok, genre, attachment, depose_le}`` ;
    * **400** — genre inconnu, fichier absent/illisible, format ou
      dimensions refusés : le motif français et le CHAMP NOMMÉ (jamais une
      confiance au ``Content-Type`` déclaré par le navigateur).
    """
    from ..services.images_document import (
        ImageDocumentRefuse, deposer_image_document,
    )

    calepinage = self.get_object()  # borné société par get_queryset
    fichier = request.FILES.get('fichier')
    if fichier is None:
        fichier = request.data.get('fichier')
    genre = request.data.get('genre')
    try:
        depot = deposer_image_document(
            calepinage, genre=genre, fichier=fichier,
            user=getattr(request, 'user', None))
    except ImageDocumentRefuse as refus:
        return Response({refus.champ or 'fichier': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response({
        'ok': True,
        'genre': depot['genre'],
        'attachment': depot['attachment'].pk,
        'depose_le': depot['attachment'].created_at,
    }, status=status.HTTP_201_CREATED)


CalepinageViewSet.image_document = image_document


# ── CALX317 — le rapport d'ombrage AUTONOME (matrice, horizon, carte) ──────
@extend_schema(
    responses={200: OpenApiTypes.BINARY},
    parameters=[OpenApiParameter(
        name='langue', type=OpenApiTypes.STR, required=False,
        description="Langue de sortie demandée (fr, en ; ar retombe sur le "
                    "français en le disant au pied du document).")],
)
@action(detail=True, methods=['get'], url_path='rapport-ombrage.pdf',
        url_name='rapport-ombrage-pdf',
        permission_classes=[PeutVoirCalepinage])
def rapport_ombrage_pdf(self, request, pk=None):
    """CALX317 — le rapport d'ombrage autonome : par pan (kWc, modules,
    azimut, inclinaison, accès solaire moyen/minimum, TOF/TSRF, chaîne la
    plus faible), la matrice 12×24, ses moyennes mensuelles, le profil
    d'horizon enregistré et la carte de chaleur déposée (CALX302).

    * **200** — le PDF, nommé d'après le calepinage ;
    * **400** — aucune matrice d'ombrage (``shading12x24`` NOMMÉ), aucune
      conception/résultat, ou des blocs dont l'accès solaire vient de
      méthodes qui ne se comparent pas : le motif français et le champ
      NOMMÉ.
    """
    from ..services.planche import nom_de_fichier
    from ..services.rapport_ombrage import (
        RapportOmbrageRefuse, rendre_rapport_ombrage,
    )
    from .sorties import MIME_PDF, reponse_de_fichier

    calepinage = self.get_object()  # borné société par get_queryset
    langue = request.query_params.get('langue')
    try:
        octets = rendre_rapport_ombrage(calepinage, company=calepinage.company,
                                        langue=langue)
    except RapportOmbrageRefuse as refus:
        return Response({refus.champ or 'roof_layout': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return reponse_de_fichier(
        octets, mime=MIME_PDF,
        nom_fichier=nom_de_fichier(calepinage, 'rapport-ombrage.pdf'))


CalepinageViewSet.rapport_ombrage_pdf = rapport_ombrage_pdf
# ── CALX316 — le manuel du propriétaire, depuis le gabarit société ─────────


@extend_schema(responses={200: OpenApiTypes.BINARY})
@action(detail=True, methods=['get'], url_path='manuel-proprietaire.pdf',
        url_name='manuel-proprietaire-pdf',
        permission_classes=[PeutVoirCalepinage])
def manuel_proprietaire_pdf(self, request, pk=None):
    """CALX316 — le manuel du propriétaire : gabarit société (genre
    « manuel »), aucun texte de consigne rédigé par le module.

    * **200** — le PDF, nommé d'après le calepinage ;
    * **400** — aucun gabarit de genre « manuel » déposé, aucun résultat de
      moteur, une variable inconnue dans le gabarit, ou une donnée refusée
      (clé de coût) : le motif français et le champ NOMMÉ.
    """
    from ..services.documents.manuel_proprietaire import rendre_manuel
    from ..services.planche import nom_de_fichier
    from ..services.rapport import RapportRefuse
    from .sorties import MIME_PDF, reponse_de_fichier

    calepinage = self.get_object()  # borné société par get_queryset
    try:
        octets = rendre_manuel(calepinage, company=calepinage.company)
    except RapportRefuse as refus:  # ManuelRefuse en est une sous-classe
        return Response({refus.champ or 'gabarit': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return reponse_de_fichier(
        octets, mime=MIME_PDF,
        nom_fichier=nom_de_fichier(calepinage, 'manuel-proprietaire.pdf'))


CalepinageViewSet.manuel_proprietaire_pdf = manuel_proprietaire_pdf


# ── CALX318 — le document as-built (prévu, posé, écarts, photos) ───────────
@extend_schema(responses={200: OpenApiTypes.BINARY})
@action(detail=True, methods=['get'], url_path='document-asbuilt.pdf',
        url_name='document-asbuilt-pdf',
        permission_classes=[PeutVoirCalepinage])
def document_asbuilt_pdf(self, request, pk=None):
    """CALX318 — le document as-built : prévu, posé, écarts, photos de site.

    * **200** — le PDF, nommé d'après le calepinage.

    Ce document ne refuse jamais : un pan sans relevé imprime sa mention
    (``asbuilt.MENTION_SANS_SAISIE``), une conception absente laisse la
    planche « en regard » vide, et l'absence de photo est DITE — jamais un
    document manquant pour autant.
    """
    from ..services.documents.document_asbuilt import rendre_document_asbuilt
    from ..services.planche import nom_de_fichier
    from .sorties import MIME_PDF, reponse_de_fichier

    calepinage = self.get_object()  # borné société par get_queryset
    octets = rendre_document_asbuilt(calepinage, company=calepinage.company)
    return reponse_de_fichier(
        octets, mime=MIME_PDF,
        nom_fichier=nom_de_fichier(calepinage, 'document-asbuilt.pdf'))


CalepinageViewSet.document_asbuilt_pdf = document_asbuilt_pdf


# ── CALX315 — la présentation compacte interne, deux pages, sans montant ───
@extend_schema(responses={200: OpenApiTypes.BINARY})
@action(detail=True, methods=['get'], url_path='presentation-compacte.pdf',
        url_name='presentation-compacte-pdf',
        permission_classes=[PeutVoirCalepinage])
def presentation_compacte_pdf(self, request, pk=None):
    """CALX315 — la présentation compacte : deux pages, INTERNE, sans aucun
    montant — ne vaut jamais offre de prix (règle #4, ``/proposal`` seul
    chemin de devis client).

    * **200** — le PDF (2 pages), nommé d'après le calepinage ;
    * **400** — une donnée refusée (clé de coût) : le motif français et le
      champ NOMMÉ. Un calepinage non simulé ne refuse PAS : la page 2 nomme
      ce qui manque.
    """
    from ..services.documents.presentation_compacte import (
        rendre_presentation_compacte,
    )
    from ..services.planche import nom_de_fichier
    from ..services.rapport import RapportRefuse
    from .sorties import MIME_PDF, reponse_de_fichier

    calepinage = self.get_object()  # borné société par get_queryset
    try:
        octets = rendre_presentation_compacte(calepinage,
                                              company=calepinage.company)
    except RapportRefuse as refus:
        return Response({refus.champ or 'resultat': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return reponse_de_fichier(
        octets, mime=MIME_PDF,
        nom_fichier=nom_de_fichier(calepinage, 'presentation-compacte.pdf'))


CalepinageViewSet.presentation_compacte_pdf = presentation_compacte_pdf


# ── CALX319 — le dossier de fin de chantier ─────────────────────────────────
@extend_schema(responses={201: OpenApiTypes.OBJECT})
@action(detail=True, methods=['post'], url_path='dossier-fin-chantier',
        url_name='dossier-fin-chantier',
        permission_classes=[PeutGererCalepinage])
def dossier_fin_chantier(self, request, pk=None):
    """CALX319 — produit le dossier de fin de chantier et le RANGE en GED.

    Plan de pose, document as-built, plan de câblage, nomenclature, manuel
    du propriétaire — LA MÊME mécanique que ``pack-technique`` (CAL181,
    ``views/sorties.py``). La recette IEC 62446-1 et les garanties restent
    PRODUITES PAR LE CHANTIER : ``signalements`` le NOMME toujours, ce
    dossier ne les fabrique jamais.

    En ÉCRITURE (POST) et gardée par ``calepinage_gerer``, comme
    ``pack-technique`` : l'appel CRÉE des documents GED.

    * **201** — le document, ses pièces (code, libellé, pages) et
      ``signalements`` ;
    * **400** — aucune pièce à fusionner, ou aucune société : le motif
      français et la pièce NOMMÉE.
    """
    from ..services.pack_technique import (
        PackRefuse, construire_dossier_fin_chantier,
    )

    calepinage = self.get_object()  # borné société par get_queryset
    try:
        resultat = construire_dossier_fin_chantier(
            calepinage, company=calepinage.company, created_by=request.user)
    except PackRefuse as refus:
        return Response({refus.piece or 'pieces': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    document = resultat['document']
    return Response({
        'document': getattr(document, 'pk', None),
        'nom': getattr(document, 'nom', ''),
        'pieces': [{'code': code, 'libelle': libelle, 'pages': pages}
                   for code, libelle, pages in resultat['pieces']],
        'pages_attendues': resultat['pages_attendues'],
        # Les pièces ABSENTES sont dites, jamais tues — de même la recette
        # et les garanties, produites par le chantier (MENTION_RECETTE_
        # GARANTIES, toujours présente ici).
        'signalements': resultat['signalements'],
    }, status=status.HTTP_201_CREATED)


CalepinageViewSet.dossier_fin_chantier = dossier_fin_chantier
