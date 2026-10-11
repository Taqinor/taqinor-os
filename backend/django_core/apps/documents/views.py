"""
Endpoints de génération de PDF après-vente, à partir d'un chantier
(installations.Installation). Tout est scopé à la société de l'utilisateur :
un id de chantier d'une autre société renvoie 404.

Aucun de ces documents n'expose de prix d'achat / marge.
"""
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from apps.installations.models import Installation
from core.selectors import get_company_object

from . import builders
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema

# ADOC69 — champs propriétaires de la portée d'un chantier : la MÊME liste que
# le viewset chantier (installations/views/installation.py, get_queryset). Un
# document de chantier ne sort jamais vers un rôle qui ne voit pas la fiche.
CHANTIER_OWNER_FIELDS = ['technicien_responsable', 'created_by']


def _scope_chantier(qs, user):
    """ADOC69 — portée de rôle (``records_scope_*``) d'un chantier."""
    from authentication.scoping import scope_queryset
    return scope_queryset(qs, user, CHANTIER_OWNER_FIELDS)


def _get_chantier_or_404(request, pk):
    """Récupère un chantier scopé à la société ET à la portée du rôle de
    l'utilisateur, sinon 404.

    YRBAC11 — délègue au helper canonique ``core.selectors.get_company_object``
    (même comportement : 404 indistinct d'un id inexistant), sur un queryset
    pré-optimisé (select_related/prefetch_related préservés).

    ADOC69 — ``extra_scope`` applique la portée de la fiche chantier : un rôle
    restreint qui n'est ni technicien ni créateur reçoit 404, comme
    ``GET /api/django/installations/chantiers/<id>/``."""
    qs = Installation.objects.select_related(
        'client', 'devis', 'company', 'technicien_responsable',
    ).prefetch_related('devis__lignes__produit')
    return get_company_object(qs, pk, request.user, extra_scope=_scope_chantier)


# ADOC72 — messages des refus d'état (409 {detail}), forme d'erreur DRF déjà
# consommée par la fiche chantier (InstallationDetail.jsx, ADOC73).
MSG_CHANTIER_ANNULE = 'Chantier annulé'
MSG_PAS_INSTALLE = 'Disponible une fois le chantier installé'
MSG_RECETTE_NON_CONFORME = (
    "Attestation de fin de travaux impossible : recette non conforme")


def _chantier_installe(chantier):
    """ADOC72 — statut CANONIQUE (statuts hérités rabattus) au rang ≥
    « installé » dans ``Installation.STATUT_ORDER`` — même règle que
    ``pvReady`` de la fiche chantier. Un statut inconnu n'est pas installé."""
    canonique = Installation.canonical_statut(chantier.statut)
    ordre = [str(s) for s in Installation.STATUT_ORDER]
    if canonique not in ordre:
        return False
    return ordre.index(canonique) >= ordre.index(
        str(Installation.Statut.INSTALLE))


def _recette_non_conforme(chantier):
    record = getattr(chantier, 'commissioning_record', None)
    if record is None:
        return False
    return record.resultat == record.Resultat.NON_CONFORME


def _refus_etat(chantier, attestation_type=None):
    """ADOC72 — garde d'état serveur des documents de chantier (la règle N6 ne
    vit plus seulement dans l'écran). Renvoie une ``Response`` 409 nommée, ou
    ``None`` si le document peut être émis :

    * chantier annulé → 409 « Chantier annulé » (les quatre documents) ;
    * chantier pas encore installé → 409 (les quatre documents) ;
    * attestation « fin de travaux » d'un chantier à recette NON conforme →
      409 (le PV, qui constate les réserves, reste autorisé).
    """
    if chantier.annule:
        return Response({'detail': MSG_CHANTIER_ANNULE},
                        status=status.HTTP_409_CONFLICT)
    if not _chantier_installe(chantier):
        return Response({'detail': MSG_PAS_INSTALLE},
                        status=status.HTTP_409_CONFLICT)
    if attestation_type == 'fin_travaux' and _recette_non_conforme(chantier):
        return Response({'detail': MSG_RECETTE_NON_CONFORME},
                        status=status.HTTP_409_CONFLICT)
    return None


def _pdf_response(pdf_bytes, filename):
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


_PDF = {(200, 'application/pdf'): OpenApiTypes.BINARY}


class _BaseDocumentView(APIView):
    permission_classes = [IsAnyRole]


class PVReceptionView(_BaseDocumentView):
    """N21 — PV de réception des travaux (ADOC70 : figé en GED une fois
    signé, servi tel quel ensuite)."""

    @extend_schema(responses=_PDF)
    def get(self, request, pk):
        chantier = _get_chantier_or_404(request, pk)
        refus = _refus_etat(chantier)
        if refus is not None:
            return refus
        pdf = builders.pv_reception_pour_client(chantier)
        return _pdf_response(pdf, f'pv-reception-{chantier.reference}.pdf')


class BonLivraisonView(_BaseDocumentView):
    """N22 — Bon de livraison (ADOC70 : figé en GED une fois signé)."""

    @extend_schema(responses=_PDF)
    def get(self, request, pk):
        chantier = _get_chantier_or_404(request, pk)
        refus = _refus_etat(chantier)
        if refus is not None:
            return refus
        pdf = builders.bon_livraison_pour_client(chantier)
        return _pdf_response(pdf, f'bon-livraison-{chantier.reference}.pdf')


class DossierRemiseView(_BaseDocumentView):
    """N23 — Dossier de remise (handover pack)."""

    @extend_schema(responses=_PDF)
    def get(self, request, pk):
        chantier = _get_chantier_or_404(request, pk)
        refus = _refus_etat(chantier)
        if refus is not None:
            return refus
        pdf = builders.generate_dossier_remise(chantier)
        return _pdf_response(pdf, f'dossier-remise-{chantier.reference}.pdf')


class AttestationView(_BaseDocumentView):
    """N24 — Attestation (type via ?type=installation|fin_travaux).

    ADOC69 — l'attestation porte la signature de la société : réservée aux
    responsables et admins (``IsResponsableOrAdmin``), un compte portail reste
    refusé (``IsAnyRole``)."""
    permission_classes = [IsAnyRole, IsResponsableOrAdmin]

    @extend_schema(
        parameters=[
            OpenApiParameter('type', OpenApiTypes.STR, required=False,
                             enum=list(builders.ATTESTATION_TYPES)),
            OpenApiParameter('regenerer', OpenApiTypes.STR, required=False,
                             enum=['1', 'true', 'oui', '0', 'false']),
        ],
        responses=_PDF)
    def get(self, request, pk):
        chantier = _get_chantier_or_404(request, pk)
        attestation_type = request.query_params.get('type', 'installation')
        if attestation_type not in builders.ATTESTATION_TYPES:
            return Response(
                {'detail': "Type d'attestation inconnu.",
                 'types': list(builders.ATTESTATION_TYPES.keys())},
                status=status.HTTP_400_BAD_REQUEST,
            )
        refus = _refus_etat(chantier, attestation_type)
        if refus is not None:
            return refus
        # ADOC70 — figée à la première émission ; ?regenerer=1 = nouvelle
        # version datée du jour (la vue est déjà réservée aux responsables).
        regenerer = str(request.query_params.get('regenerer', '')).lower() \
            in ('1', 'true', 'oui')
        pdf = builders.attestation_pour_client(
            chantier, attestation_type, regenerer=regenerer)
        return _pdf_response(
            pdf, f'attestation-{attestation_type}-{chantier.reference}.pdf')
