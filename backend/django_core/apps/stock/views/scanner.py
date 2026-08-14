"""NTWMS5 — poste de travail SCANNER (RF workflow) : API sans saisie clavier.

Un magasinier doit pouvoir réceptionner, ranger, prélever et compter en ne
faisant QUE scanner puis confirmer. Ces vues fournissent les deux briques que
le poste mobile n'avait pas :

  * ``GET  stock/scanner/resoudre/?code=`` — résolution UNIVERSELLE d'un code
    scanné (produit/GTIN, casier FG319, emplacement, lot, ligne de vague) vers
    ``{type, id, label, …}``, pour que l'écran sache seul quoi afficher ;
  * ``POST stock/scanner/mouvement/`` — pose un ``MouvementStock`` scanné en
    traçant le casier source et le casier destination (NTWMS5).

Le RESTE du parcours réutilise l'existant, jamais un chemin parallèle :
réception (`receptions-fournisseur/{id}/suggestions-rangement/` NTWMS2 puis
`/confirmer/`), rangement guidé (`installations` `putaways/{id}/ranger/`,
FG320), prélèvement (`vagues-picking/{id}/lignes/{l}/prelever/` NTWMS4),
comptage (`inventaire-sessions/`).
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, HasPermissionOrLegacy


@api_view(['GET'])
@permission_classes([IsAnyRole])
def scanner_resoudre_view(request):
    """Résout un code scanné dans la société de l'utilisateur.

    Renvoie ``{type, id, label, detail}`` — ``type`` ∈ produit / casier /
    emplacement / lot / ligne_picking. 404 (sans fuite) si le code est inconnu
    ou hors société."""
    from ..selectors import resoudre_code_scanne

    code = (request.query_params.get('code') or '').strip()
    if not code:
        return Response({'detail': 'Code illisible.'},
                        status=status.HTTP_400_BAD_REQUEST)
    resultat = resoudre_code_scanne(request.user.company, code)
    if resultat is None:
        return Response({'detail': 'Code inconnu dans cette société.'},
                        status=status.HTTP_404_NOT_FOUND)
    return Response(resultat)


@api_view(['POST'])
@permission_classes([HasPermissionOrLegacy('stock_modifier')])
def scanner_mouvement_view(request):
    """Pose un mouvement de stock SCANNÉ, casiers tracés.

    Corps : ``{produit, type_mouvement, quantite, bin_source?,
    bin_destination?, reference?, note?}``. Refuse une quantité non positive,
    un produit hors société, un casier hors société, et un type de mouvement
    inconnu."""
    from ..services import enregistrer_mouvement_scanne

    try:
        mouvement = enregistrer_mouvement_scanne(
            company=request.user.company, user=request.user,
            produit_id=request.data.get('produit'),
            type_mouvement=request.data.get('type_mouvement'),
            quantite=request.data.get('quantite'),
            bin_source_id=request.data.get('bin_source'),
            bin_destination_id=request.data.get('bin_destination'),
            reference=request.data.get('reference') or 'SCAN',
            note=request.data.get('note') or '')
    except ValueError as exc:
        return Response({'detail': str(exc)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response({
        'id': mouvement.id,
        'produit': mouvement.produit_id,
        'type_mouvement': mouvement.type_mouvement,
        'quantite': mouvement.quantite,
        'quantite_avant': mouvement.quantite_avant,
        'quantite_apres': mouvement.quantite_apres,
        'bin_source': mouvement.bin_source_id,
        'bin_destination': mouvement.bin_destination_id,
    }, status=status.HTTP_201_CREATED)
