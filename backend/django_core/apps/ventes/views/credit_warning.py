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

    Renvoie {plafond, encours, encours_avec_nouveau, depasse, depassera, message,
    recouvrement}. 404 si le client n'appartient pas à la société de
    l'utilisateur.

    YCASH4 — ``recouvrement`` enrichit ce warning avec l'état des RELANCES
    (retard max, niveau de relance atteint, encours ÉCHU — distinct de
    l'encours total FG41) via ``ventes.selectors.etat_recouvrement_client``.
    Reste un AVERTISSEMENT (le blocage dur est XFAC28, jamais dupliqué ici) ;
    ``a_jour=True`` dès que l'encours échu revient à 0 (facture réglée)."""
    from apps.crm.models import Client
    from apps.crm.selectors import client_credit_warning as _warning
    from ..selectors import etat_recouvrement_client
    company = request.user.company

    # Scoping tenant : le client doit appartenir à la société.
    try:
        client = Client.objects.get(pk=client_id, company=company)
    except Client.DoesNotExist:
        return Response({'detail': 'Client introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)

    montant_ttc = request.query_params.get('montant_ttc')
    result = _warning(client, montant_ttc_nouveau=montant_ttc)
    recouvrement = etat_recouvrement_client(company, client_id)

    message = result['message']
    if not recouvrement['a_jour']:
        niveau = recouvrement['niveau_relance']
        niveau_txt = f", niveau relance « {niveau['nom']} »" if niveau else ''
        recouvrement_msg = (
            f"⚠ Client {client.nom} : facture(s) en retard de "
            f"{recouvrement['retard_max_jours']} j{niveau_txt} "
            f"(encours échu {recouvrement['encours_echu']:.2f} MAD)."
        )
        message = f'{message}\n{recouvrement_msg}' if message else recouvrement_msg

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
        'message': message,
        'recouvrement': {
            'a_jour': recouvrement['a_jour'],
            'retard_max_jours': recouvrement['retard_max_jours'],
            'niveau_relance': recouvrement['niveau_relance'],
            'encours_echu': str(recouvrement['encours_echu']),
        },
    })
