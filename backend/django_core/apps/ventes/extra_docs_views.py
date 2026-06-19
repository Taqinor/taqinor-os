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
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole

from .models import Facture


def _scope(qs, user):
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()


@api_view(['GET'])
@permission_classes([IsAnyRole])
def lettre_relance_premium(request, facture_id):
    """Lettre de relance premium pour une facture en retard.

    ?niveau=1 (courtois) / 2 (ferme) / 3 (mise en demeure). Défaut : 1.
    """
    facture = _scope(
        Facture.objects.select_related('client'), request.user).filter(
        pk=facture_id).first()
    if facture is None:
        return Response({'detail': 'Facture introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    try:
        niveau = int(request.query_params.get('niveau', 1))
    except (TypeError, ValueError):
        niveau = 1
    if niveau not in (1, 2, 3):
        return Response({'detail': 'Niveau de relance invalide (1, 2 ou 3).'},
                        status=status.HTTP_400_BAD_REQUEST)
    from .quote_engine.extra_docs import render_lettre_relance_pdf
    try:
        pdf_bytes = render_lettre_relance_pdf(facture, niveau)
    except Exception as exc:
        return Response({'detail': f'PDF indisponible : {exc}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = (
        f'inline; filename="Relance_{facture.reference}_N{niveau}.pdf"')
    return resp


@api_view(['GET'])
@permission_classes([IsAnyRole])
def fiche_remise_premium(request, chantier_id):
    """Fiche de remise / garantie après-vente (une page) pour un chantier."""
    # Import local : lecture seule du modèle d'une autre app (jamais modifié).
    from apps.installations.models import Installation
    qs = Installation.objects.select_related(
        'client', 'devis', 'company', 'technicien_responsable',
    ).prefetch_related('devis__lignes__produit')
    chantier = _scope(qs, request.user).filter(pk=chantier_id).first()
    if chantier is None:
        return Response({'detail': 'Chantier introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    from .quote_engine.extra_docs import render_fiche_remise_pdf
    try:
        pdf_bytes = render_fiche_remise_pdf(chantier)
    except Exception as exc:
        return Response({'detail': f'PDF indisponible : {exc}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = (
        f'attachment; filename="Fiche_remise_{chantier.reference}.pdf"')
    return resp
