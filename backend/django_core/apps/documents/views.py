"""
Endpoints de génération de PDF après-vente, à partir d'un chantier
(installations.Installation). Tout est scopé à la société de l'utilisateur :
un id de chantier d'une autre société renvoie 404.

Aucun de ces documents n'expose de prix d'achat / marge.
"""
from django.http import HttpResponse, Http404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from authentication.permissions import IsAnyRole
from apps.installations.models import Installation

from . import builders


def _get_chantier_or_404(request, pk):
    """Récupère un chantier scopé à la société de l'utilisateur, sinon 404."""
    user = request.user
    qs = Installation.objects.select_related(
        'client', 'devis', 'company', 'technicien_responsable',
    ).prefetch_related('devis__lignes__produit')
    if user.company_id:
        qs = qs.filter(company_id=user.company_id)
    elif not user.is_superuser:
        qs = qs.none()
    chantier = qs.filter(pk=pk).first()
    if chantier is None:
        raise Http404("Chantier inconnu.")
    return chantier


def _pdf_response(pdf_bytes, filename):
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


class _BaseDocumentView(APIView):
    permission_classes = [IsAnyRole]


class PVReceptionView(_BaseDocumentView):
    """N21 — PV de réception des travaux."""

    def get(self, request, pk):
        chantier = _get_chantier_or_404(request, pk)
        pdf = builders.generate_pv_reception(chantier)
        return _pdf_response(pdf, f'pv-reception-{chantier.reference}.pdf')


class BonLivraisonView(_BaseDocumentView):
    """N22 — Bon de livraison."""

    def get(self, request, pk):
        chantier = _get_chantier_or_404(request, pk)
        pdf = builders.generate_bon_livraison(chantier)
        return _pdf_response(pdf, f'bon-livraison-{chantier.reference}.pdf')


class DossierRemiseView(_BaseDocumentView):
    """N23 — Dossier de remise (handover pack)."""

    def get(self, request, pk):
        chantier = _get_chantier_or_404(request, pk)
        pdf = builders.generate_dossier_remise(chantier)
        return _pdf_response(pdf, f'dossier-remise-{chantier.reference}.pdf')


class AttestationView(_BaseDocumentView):
    """N24 — Attestation (type via ?type=installation|fin_travaux)."""

    def get(self, request, pk):
        chantier = _get_chantier_or_404(request, pk)
        attestation_type = request.query_params.get('type', 'installation')
        if attestation_type not in builders.ATTESTATION_TYPES:
            return Response(
                {'detail': "Type d'attestation inconnu.",
                 'types': list(builders.ATTESTATION_TYPES.keys())},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pdf = builders.generate_attestation(chantier, attestation_type)
        return _pdf_response(
            pdf, f'attestation-{attestation_type}-{chantier.reference}.pdf')
