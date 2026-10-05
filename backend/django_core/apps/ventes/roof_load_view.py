"""FG253 / CIQ114 — endpoint INTERNE de vérification de charge de toiture.

  POST /ventes/toiture/charge/ → masse ajoutée vs charge admissible DÉCLARÉE
       (avec sa source) ; sans capacité déclarée, verdict « non déclarée ».
       Une capacité ou un coefficient sans source → 400 FR nommant le champ.

Calcul PUR (aucune écriture base, aucun statut changé) ; jamais de prix ;
résultat interne, jamais imprimé au client. Les anciennes capacités par type
de toit (GET) ont disparu avec CIQ114.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from .roof_load import ChargeNonSourcee, verifier_charge_toiture


@api_view(['POST'])
@permission_classes([IsAnyRole])
def roof_load_check(request):
    """POST → vérification de charge (interne)."""
    data = request.data or {}
    try:
        result = verifier_charge_toiture(
            charge_admissible_kg_m2=data.get('charge_admissible_kg_m2'),
            charge_admissible_source=data.get('charge_admissible_source'),
            struct_masse_kg_m2=data.get('struct_masse_kg_m2'),
            poids_module_kg=data.get('poids_module_kg'),
            aire_module_m2=data.get('aire_module_m2'),
            masse_layout_kg_m2=data.get('masse_layout_kg_m2'),
            couverture=data.get('couverture'),
            coefficient_securite=data.get('coefficient_securite'),
            coefficient_source=data.get('coefficient_source'),
        )
    except ChargeNonSourcee as refus:
        return Response({refus.champ: [refus.message]}, status=400)
    return Response(result)
