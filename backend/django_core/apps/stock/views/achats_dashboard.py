"""NTP2P17 — Dashboard spend management (lecture seule).

Périmètre : endpoint dédié `stock/tableau-bord-achats/` (l'écran React
`AchatsDashboard` évoqué par la tâche vit hors du périmètre backend de cette
lane). Réutilise `stock.selectors.tableau_bord_achats` — aucune logique
dupliquée ici, cette vue ne fait que router la requête HTTP.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin


@extend_schema(responses=inline_serializer('TableauBordAchats', {
    'debut': drf_serializers.CharField(allow_null=True),
    'fin': drf_serializers.CharField(allow_null=True),
    'budgets_departement': drf_serializers.JSONField(),
    'top_fournisseurs': drf_serializers.JSONField(),
    'delai_demande_bcf_jours': drf_serializers.FloatField(allow_null=True),
    'delai_bcf_reception_jours': drf_serializers.FloatField(allow_null=True),
    'exceptions_3_voies': drf_serializers.JSONField(),
    'notes_frais_en_attente': drf_serializers.JSONField(),
}))
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
