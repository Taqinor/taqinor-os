"""FG272 — endpoint de la déclaration de raccordement BT/MT pré-remplie.

  GET /ventes/devis/<id>/declaration-raccordement/         → JSON pré-rempli.
  GET /ventes/devis/<id>/declaration-raccordement/?format=pdf → PDF.

Lecture seule, scopé société (un devis d'une autre société → 404). Ne change
aucun statut de devis (RULE #4) ; le PDF est un document RÉGLEMENTAIRE autonome,
distinct du PDF de devis client (``/proposal`` reste l'unique chemin de celui-ci
et le moteur premium n'est pas touché). Jamais de prix d'achat / marge en sortie.
"""
from django.http import HttpResponse, Http404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from .models import Devis
from .connection_declaration import (
    build_declaration_data, render_declaration_pdf)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def declaration_raccordement(request, pk):
    """GET /ventes/devis/<id>/declaration-raccordement/

    Déduit les champs (client/site/kWc/onduleur/schéma) du devis et du chantier
    lié. ``?regime=`` ajoute la liste des pièces du régime. ``?format=pdf`` rend
    le PDF, sinon JSON.
    """
    user = request.user
    qs = Devis.objects.select_related('client')
    if getattr(user, 'company_id', None):
        qs = qs.filter(company=user.company)
    elif not user.is_superuser:
        qs = qs.none()
    try:
        devis = qs.prefetch_related('lignes').get(pk=pk)
    except Devis.DoesNotExist:
        raise Http404("Devis introuvable.")

    # Lien chantier en LECTURE via le sélecteur cross-app (jamais d'import
    # du modèle installations).
    chantier = None
    try:
        from apps.installations.selectors import installation_for_devis
        chantier = installation_for_devis(devis)
    except Exception:
        chantier = None

    regime = request.query_params.get('regime')
    # Repli : si non fourni, prendre le régime du chantier lié s'il existe.
    if not regime and chantier is not None:
        regime = getattr(chantier, 'regime_8221', None)

    data = build_declaration_data(devis, chantier=chantier, regime_8221=regime)

    if request.query_params.get('format') == 'pdf':
        try:
            pdf_bytes = render_declaration_pdf(data)
        except Exception as exc:
            return Response({'detail': f'PDF indisponible : {exc}'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="declaration-raccordement-'
            f'{devis.reference}.pdf"')
        return resp
    return Response(data)
