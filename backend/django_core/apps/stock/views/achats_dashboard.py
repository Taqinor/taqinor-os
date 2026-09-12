"""NTP2P17 — Dashboard spend management (lecture seule).

Périmètre : endpoint dédié `stock/tableau-bord-achats/` (l'écran React
`AchatsDashboard` évoqué par la tâche vit hors du périmètre backend de cette
lane). Réutilise `stock.selectors.tableau_bord_achats` — aucune logique
dupliquée ici, cette vue ne fait que router la requête HTTP.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def tableau_bord_achats_view(request):
    """NTP2P17 — spend management : budgets départementaux (NTP2P4), top
    fournisseurs par volume, délais demande→BCF→réception, taux
    d'exceptions 3 voies, notes de frais en attente. Paramètres facultatifs
    ``?debut=&fin=`` (ISO)."""
    from ..selectors import tableau_bord_achats

    return Response(tableau_bord_achats(
        request.user.company,
        debut=request.query_params.get('debut'),
        fin=request.query_params.get('fin'),
    ))
