"""FG41 — Avertissement plafond de crédit client.

Endpoint de LECTURE SEULE appelé par le frontend (DevisGenerator, FactureForm)
pour afficher un warning doux quand l'encours du client dépasse son plafond.
Jamais un blocage dur : l'encours est calculé à la volée depuis les factures
ouvertes et renvoyé avec un message prêt à l'affichage.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from authentication.permissions import IsAnyRole


@api_view(['GET'])
@permission_classes([IsAnyRole])
def client_credit_warning(request, client_id):
    """GET /ventes/clients/<client_id>/credit-warning/

    Paramètres de requête optionnels :
      - ``montant_ttc`` : montant TTC du nouveau document (devis/facture en cours)
                         pour calculer l'encours prévisionnel.

    Renvoie {plafond, encours, encours_avec_nouveau, depasse, depassera, message}.
    404 si le client n'appartient pas à la société de l'utilisateur.
    """
    from apps.crm.models import Client
    from apps.crm.selectors import client_credit_warning as _warning
    company = request.user.company

    # Scoping tenant : le client doit appartenir à la société.
    try:
        client = Client.objects.get(pk=client_id, company=company)
    except Client.DoesNotExist:
        return Response({'detail': 'Client introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)

    montant_ttc = request.query_params.get('montant_ttc')
    result = _warning(client, montant_ttc_nouveau=montant_ttc)

    # Sérialiser les Decimal en str pour la réponse JSON.
    return Response({
        'plafond': str(result['plafond']) if result['plafond'] is not None else None,
        'encours': str(result['encours']),
        'encours_avec_nouveau': (
            str(result['encours_avec_nouveau'])
            if result['encours_avec_nouveau'] is not None else None
        ),
        'depasse': result['depasse'],
        'depassera': result['depassera'],
        'message': result['message'],
    })
