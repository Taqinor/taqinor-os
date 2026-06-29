"""FG253 — endpoint d'aide au calcul de charge structure toiture.

  GET  /ventes/toiture/charge/   → liste des types de toiture supportés.
  POST /ventes/toiture/charge/   → surcharge PV (kg/m²) vs capacité du type +
       alerte si dépassement.

Calcul PUR (aucune écriture base, aucun changement de statut de devis) ; jamais
de prix en sortie. Couche additive séparée du PDF premium et de `/proposal`.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from .roof_load import compute_roof_load, list_roof_types


@api_view(['GET', 'POST'])
@permission_classes([IsAnyRole])
def roof_load_check(request):
    """GET → types de toiture ; POST → calcul de charge + alerte."""
    if request.method == 'GET':
        return Response({"roof_types": list_roof_types()})

    data = request.data or {}
    result = compute_roof_load(
        roof_type=data.get('roof_type', 'autre'),
        n_modules=data.get('n_modules', 0),
        poids_module_kg=data.get('poids_module_kg'),
        surface_module_m2=data.get('surface_module_m2', 2.2),
        module_kg_m2=data.get('module_kg_m2'),
        surface_toiture_m2=data.get('surface_toiture_m2'),
        capacite_kg_m2=data.get('capacite_kg_m2'),
    )
    return Response(result)
