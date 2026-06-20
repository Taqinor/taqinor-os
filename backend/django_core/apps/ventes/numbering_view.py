"""N31 — endpoint d'audit de la numérotation séquentielle (lecture seule).

Réservé à l'admin : signale les numéros manquants (trous laissés par une
suppression) et d'éventuels doublons, par type de pièce. Ne renumérote rien.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier, IsAdminRole
from .utils.numbering_audit import audit_company


@api_view(['GET'])
@permission_classes([IsAdminRole])
def numerotation_audit(request):
    """GET → rapport des trous/doublons de numérotation pour la société."""
    user = request.user
    if not user.company_id and not user.is_superuser:
        return Response({'detail': 'Accès refusé.'}, status=403)
    if not user.company_id:
        return Response({'detail': 'Aucune société.'}, status=400)
    return Response(audit_company(user.company))


# Types de pièces couverts par l'aperçu de numérotation (L770/L786).
_PREVIEW_TYPES = {
    'devis': 'Devis',
    'facture': 'Facture',
    'avoir': 'Avoir',
    'bon_commande': 'BonCommande',
}


@api_view(['GET'])
@permission_classes([IsAdminOrResponsableTier])
def numerotation_preview(request):
    """GET → prochain numéro RÉEL par type de pièce (L770/L786).

    Pour chaque type (devis/facture/avoir/bon_commande), calcule le prochain
    numéro libre à partir de la séquence la plus haute réellement utilisée par
    la société, en appliquant le préfixe + largeur + période de
    réinitialisation enregistrés (mêmes règles que `create_numbered`). Lecture
    seule : aucune pièce n'est créée, aucun numéro n'est consommé.
    """
    from apps.ventes import models as ventes_models
    from .utils.company_settings import numbering_config
    from .utils.references import next_reference

    user = request.user
    if not user.company_id:
        return Response({'detail': 'Aucune société.'}, status=400)
    company = user.company
    out = {}
    for cle, model_name in _PREVIEW_TYPES.items():
        model = getattr(ventes_models, model_name)
        cfg = numbering_config(company, cle)
        out[cle] = next_reference(
            model, cfg['prefix'], company,
            padding=cfg['padding'], period=cfg['period'])
    return Response(out)
