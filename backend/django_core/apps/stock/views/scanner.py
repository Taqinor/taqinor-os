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
from drf_spectacular.utils import extend_schema, inline_serializer
from ..openapi_helpers import INT, P, STR, corps
from rest_framework import serializers, status
from rest_framework.parsers import JSONParser
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, HasPermissionOrLegacy
from core.champs_stricts import MOTIF_NON_BLANC_SANS_NUL, QUANTITE_MAX, ChaineStricte
from ..services_wms import TYPES_MOUVEMENT_SCANNABLES
from ..erreurs_achats import debordement_compteur_en_409, statut_refus_metier


@extend_schema(parameters=[P('code', STR, True, 'Code scanné', pattern=MOTIF_NON_BLANC_SANS_NUL)], responses={
    200: inline_serializer('StockScannerResoudreResultat', {
        'type': serializers.CharField(),
        'id': serializers.IntegerField(),
        'label': serializers.CharField(),
        # Forme variable selon `type` (casier/produit/emplacement/lot) —
        # un DictField documente honnêtement « objet », jamais des clés
        # qui n'existent pas dans toutes les branches.
        'detail': serializers.DictField(),
    }),
    # ``detail`` (code illisible) OU l'erreur de validation générique d'un paramètre
    # (nul, doublon) qui garde ses clés à la racine — ``detail`` n'y figure pas.
    400: inline_serializer('StockScannerErreur', {
        'detail': serializers.CharField(required=False),
    }),
    404: inline_serializer('StockScannerCodeInconnu', {
        'detail': serializers.CharField(),
    }),
})
@api_view(['GET'])
@permission_classes([IsAnyRole])
def scanner_resoudre_view(request):
    """Résout un code scanné dans la société de l'utilisateur.

    Renvoie ``{type, id, label, detail}`` — ``type`` ∈ produit / casier /
    emplacement / lot / ligne_picking. 404 (sans fuite) si le code est inconnu
    ou hors société."""
    from ..selectors import resoudre_code_scanne

    code = (request.query_params.get('code') or '').strip()
    if not code or '\x00' in code:
        return Response({'detail': 'Code illisible.'},
                        status=status.HTTP_400_BAD_REQUEST)
    resultat = resoudre_code_scanne(request.user.company, code)
    if resultat is None:
        return Response({'detail': 'Code inconnu dans cette société.'},
                        status=status.HTTP_404_NOT_FOUND)
    return Response(resultat)


# CI #997 fuzz (2) — identifiants publiés 1..ID_MAX (``id_corps`` refuse 0).
_ID = {'min_value': 1, 'max_value': 2147483647}
#: Colonne ``MouvementStock.reference`` (varchar 100) : plafond publié ET appliqué.
_REFERENCE_MAX = 100


@extend_schema(request=corps('ScannerMouvementCorps', produit=serializers.IntegerField(**_ID),
                             type_mouvement=serializers.ChoiceField(choices=TYPES_MOUVEMENT_SCANNABLES),
                             quantite=serializers.IntegerField(min_value=1, max_value=QUANTITE_MAX),
                             bin_source=serializers.IntegerField(required=False, allow_null=True, **_ID),
                             bin_destination=serializers.IntegerField(required=False, allow_null=True, **_ID),
                             reference=ChaineStricte(required=False, max_length=_REFERENCE_MAX),
                             note=ChaineStricte(required=False, allow_blank=True)), responses={
    201: inline_serializer('StockScannerMouvementResultat', {
        'id': serializers.IntegerField(),
        'produit': serializers.IntegerField(),
        'type_mouvement': serializers.CharField(),
        'quantite': serializers.IntegerField(),
        'quantite_avant': serializers.IntegerField(),
        'quantite_apres': serializers.IntegerField(),
        'bin_source': serializers.IntegerField(allow_null=True),
        'bin_destination': serializers.IntegerField(allow_null=True),
    }),
    # ``{detail}`` (refus du service) ou l'erreur de validation DRF nommant le
    # champ (transfert sans casier, casier hazmat incompatible — contrats WMS).
    400: inline_serializer('StockScannerMouvementErreur', {
        'detail': serializers.CharField(required=False),
    }),
})
@api_view(['POST'])
@parser_classes([JSONParser])
@permission_classes([HasPermissionOrLegacy('stock_modifier')])
def scanner_mouvement_view(request):
    """Pose un mouvement de stock SCANNÉ, casiers tracés.

    Corps : ``{produit, type_mouvement, quantite, bin_source?,
    bin_destination?, reference?, note?}``. Refuse une quantité non positive,
    un produit hors société, un casier hors société, et un type de mouvement
    inconnu."""
    from ..services import enregistrer_mouvement_scanne

    # ERR fuzz : corps non objet -> 400 au format DÉCLARÉ ({detail}), pas 500.
    if not hasattr(request.data, 'get'):
        return Response({'detail': 'Le corps doit être un objet JSON.'},
                        status=status.HTTP_400_BAD_REQUEST)
    donnees = request.data
    # CI #997 fuzz — un id non entier (``produit: {}``) faisait un TypeError ORM
    # (500) ; un texte non textuel était enregistré tel quel.
    from ..utils.params import id_corps
    if any(donnees.get(c) is not None and id_corps(donnees.get(c)) is None
           for c in ('produit', 'bin_source', 'bin_destination')) or any(
               not isinstance(donnees.get(c, ''), str) for c in ('type_mouvement', 'reference', 'note')) or (
               # CI #997 fuzz (2) : quantité ENTIÈRE JSON, référence non blanche.
               isinstance(donnees.get('quantite'), bool) or not isinstance(donnees.get('quantite'), int)) or (
               'reference' in donnees and not donnees['reference'].strip()) or (
               # api-fuzz-full 24/10 : publié « sans nul » (reference/note) et reference <= 100.
               any('\x00' in donnees.get(c, '') for c in ('type_mouvement', 'reference', 'note'))
               or len(donnees.get('reference', '')) > _REFERENCE_MAX):
        return Response({'detail': 'Corps invalide : identifiants entiers, quantité entière et textes attendus.'},
                        status=status.HTTP_400_BAD_REQUEST)
    # CI #997 fuzz (3) — plafond métier publié (``maximum``), AVANT tout calcul.
    if donnees['quantite'] > QUANTITE_MAX:
        return Response({'detail': f'Quantité au plus égale à {QUANTITE_MAX}.'},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        # Un casier (ou le stock) qui déborderait sa colonne : 409, pas 500.
        with debordement_compteur_en_409():
            mouvement = enregistrer_mouvement_scanne(
                company=request.user.company, user=request.user,
                produit_id=donnees.get('produit'),
                type_mouvement=donnees.get('type_mouvement'),
                quantite=donnees.get('quantite'),
                bin_source_id=donnees.get('bin_source'),
                bin_destination_id=donnees.get('bin_destination'),
                reference=donnees.get('reference') or 'SCAN',
                note=donnees.get('note') or '')
    except ValueError as exc:
        return Response({'detail': str(exc)},
                        status=statut_refus_metier(exc))
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


@extend_schema(parameters=[P('code', STR, True, 'GTIN ou SKU', pattern=MOTIF_NON_BLANC_SANS_NUL),
                           P('quantite', INT)], responses={
    200: inline_serializer('StockScannerRetourFournisseurLigne', {
        'produit': serializers.IntegerField(),
        'produit_nom': serializers.CharField(),
        'sku': serializers.CharField(allow_blank=True),
        'quantite': serializers.IntegerField(),
        'bin_source': serializers.IntegerField(allow_null=True),
        'bin_source_code': serializers.CharField(allow_blank=True),
        'bin_destination': serializers.IntegerField(allow_null=True),
        'bin_destination_code': serializers.CharField(allow_blank=True),
        'fournisseur': serializers.IntegerField(allow_null=True),
        'fournisseur_nom': serializers.CharField(allow_blank=True),
    }),
    # Idem résoudre : la validation générique des paramètres (``quantite=null``) n'a pas de ``detail``.
    400: inline_serializer('StockScannerRetourErreur', {
        'detail': serializers.CharField(required=False),
    }),
    # CI #1001 — un code conforme qui désigne un casier/autre objet : l'ÉTAT
    # du référentiel s'oppose au retour (409), pas la forme de la requête.
    409: inline_serializer('StockScannerRetourConflit', {
        'detail': serializers.CharField(),
    }),
})
@api_view(['GET'])
@permission_classes([IsAnyRole])
def scanner_retour_fournisseur_view(request):
    """NTWMS41 — mode « Retour fournisseur » du poste scanner.

    ``?code=<GTIN|SKU>[&quantite=]`` résout le produit ET son casier actuel
    (NTWMS3/FG319) et pré-remplit la ligne de retour, avec le casier de
    départs fournisseur en destination. LECTURE SEULE : rien n'est écrit tant
    que le retour n'est pas validé (``retours-fournisseur/{id}/
    valider-scanne/``).
    """
    from ..services_retour_scanne import (
        CodeInconnu, preparer_ligne_retour_scannee,
    )

    if '\x00' in (request.query_params.get('code') or ''):  # nul publié interdit (500 SQL avant)
        return Response({'detail': 'Code illisible.'},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        ligne = preparer_ligne_retour_scannee(
            request.user.company,
            request.query_params.get('code'),
            quantite=request.query_params.get('quantite') or 1)
    except CodeInconnu as exc:
        return Response({'detail': str(exc)},
                        status=status.HTTP_404_NOT_FOUND)
    except ValueError as exc:
        conflit = str(exc).startswith('Ce code désigne')
        return Response({'detail': str(exc)},
                        status=status.HTTP_409_CONFLICT if conflit else status.HTTP_400_BAD_REQUEST)
    return Response(ligne)
