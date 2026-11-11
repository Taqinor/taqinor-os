"""Endpoints PDF clients ADDITIFS, rendus dans le langage visuel premium :

- ``lettre_relance_premium`` — lettre de relance premium pour une facture en
  retard, niveau 1/2/3 (?niveau=1|2|3) à ton croissant.
- ``fiche_remise_premium`` — fiche de remise / garantie après-vente (une page)
  pour un chantier.

Toujours scopés à la société de l'utilisateur (un id d'une autre société
renvoie 404). Aucun de ces documents n'expose de prix d'achat / marge. La
génération réutilise les helpers visuels du moteur premium (jamais modifié)
via ``apps.ventes.quote_engine.extra_docs``.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from . import openapi_shapes as SH
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from .gardes_lecture import LectureFactures

from .models import Facture
import logging

logger = logging.getLogger(__name__)


def _scope(qs, user):
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()


@extend_schema(
    parameters=[OpenApiParameter('niveau', OpenApiTypes.INT, required=False,
                                 enum=[1, 2, 3])],
    responses={(200, 'application/pdf'): OpenApiTypes.BINARY,
               409: SH.DetailResponse, 500: SH.DetailResponse})
@api_view(['GET'])
@permission_classes([LectureFactures])  # AARG66
def lettre_relance_premium(request, facture_id):
    """Lettre de relance premium pour une facture en retard.

    ?niveau=1 (courtois) / 2 (ferme) / 3 (mise en demeure). Défaut : 1.
    """
    # AFAC54 (C-AFAC-048) — même portée que `FactureViewSet` (créée par soi
    # / l'équipe) : une facture invisible répond 404, indistinct d'un id
    # inexistant.
    from authentication.scoping import scope_queryset
    facture = scope_queryset(_scope(
        Facture.objects.select_related('client'), request.user),
        request.user, ['created_by']).filter(pk=facture_id).first()
    if facture is None:
        return Response({'detail': 'Facture introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    # ENF11 — un ``niveau`` non entier répond 400 (il retombait sur 1).
    try:
        niveau = int(request.query_params.get('niveau', 1))
    except (TypeError, ValueError):
        niveau = None
    if niveau not in (1, 2, 3):
        return Response({'detail': 'Niveau de relance invalide (1, 2 ou 3).'},
                        status=status.HTTP_400_BAD_REQUEST)
    # AMOT60 (C-AMOT-036) / AMOT112 — porte partagée `facture_relancable` (comme
    # `lettre_relance_pdf`) : brouillon, payée, annulée ou sans somme EXIGIBLE → 409.
    from .recouvrement import facture_relancable
    if not facture_relancable(facture)[0]:
        return Response({'detail': 'Aucune somme exigible sur cette facture.'},
                        status=status.HTTP_409_CONFLICT)
    from .quote_engine.extra_docs import render_lettre_relance_pdf
    try:
        pdf_bytes = render_lettre_relance_pdf(facture, niveau)
    except Exception as exc:
        logger.warning("extra_docs_views.lettre_relance_premium : erreur ignorée (mode dégradé)", exc_info=True)
        return Response({'detail': f'PDF indisponible : {exc}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = (
        f'inline; filename="Relance_{facture.reference}_N{niveau}.pdf"')
    return resp


@extend_schema(responses={(200, 'application/pdf'): OpenApiTypes.BINARY,
                          409: SH.DetailResponse, 500: SH.DetailResponse})
@api_view(['GET'])
@permission_classes([IsAnyRole])
def fiche_remise_premium(request, chantier_id):
    """Fiche de remise / garantie après-vente (une page) pour un chantier."""
    # ADRG8 (D-APFS-4) — lecture du module chantiers ou octroi ``ventes_voir``,
    # puis la portée de la fiche chantier (``_scope_chantier``).
    from authentication.permissions import peut_lire_module
    if not (peut_lire_module(request.user, 'installations')
            or request.user.has_erp_permission('ventes_voir')):
        return Response({'detail': 'Accès réservé aux rôles du module.'},
                        status=status.HTTP_403_FORBIDDEN)
    # Lecture seule du chantier d'une autre app, via son sélecteur (jamais modifié).
    from apps.installations.selectors import installation_qs_for_remise
    from apps.documents.views import _scope_chantier
    qs = _scope(installation_qs_for_remise(), request.user)
    chantier = _scope_chantier(qs, request.user).filter(pk=chantier_id).first()
    if chantier is None:
        return Response({'detail': 'Chantier introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    # ACSV99 — même garde d'état que les documents de chantier (ADOC72) :
    # annulé ou pas encore installé ⇒ 409 nommé.
    from apps.documents.views import _refus_etat
    refus = _refus_etat(chantier)
    if refus is not None:
        return refus
    from .quote_engine.extra_docs import render_fiche_remise_pdf
    try:
        pdf_bytes = render_fiche_remise_pdf(chantier)
    except Exception as exc:
        logger.warning("extra_docs_views.fiche_remise_premium : erreur ignorée (mode dégradé)", exc_info=True)
        return Response({'detail': f'PDF indisponible : {exc}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = (
        f'attachment; filename="Fiche_remise_{chantier.reference}.pdf"')
    return resp
