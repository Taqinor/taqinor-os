from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .public_views import quai_checkin_view, portail_tiers_solde_view
from .views import (
    ProduitViewSet, CategorieViewSet, FournisseurViewSet,
    MouvementStockViewSet, MarqueViewSet, BonCommandeFournisseurViewSet,
    EmplacementStockViewSet, TransfertStockViewSet, PrixFournisseurViewSet,
    RetourFournisseurViewSet, ReceptionFournisseurViewSet,
    FactureFournisseurViewSet, PaiementFournisseurViewSet,
    InventaireSessionViewSet, KitProduitViewSet,
    FicheTechniqueViewSet,
    DocumentConformiteFournisseurViewSet, AchatsParametresViewSet,
    ContactFournisseurViewSet, CategorieFournisseurViewSet,
    AcompteFournisseurViewSet, AvoirFournisseurViewSet,
    LotEntrepotViewSet, InventaireAnnuelViewSet, RevalorisationStockViewSet,
    ConditionnementProduitViewSet, ModeleBonCommandeFournisseurViewSet,
    NomenclatureCodeBarresViewSet, RegleCodeBarresViewSet,
    VaguePickingViewSet, UniteLogistiqueViewSet, QuaiViewSet,
    RendezVousTransporteurViewSet, ExpeditionTransporteurViewSet,
    PlanComptageTournantViewSet, AlerteRappelViewSet,
    PortailTiersTokenViewSet, DemandeTransfertViewSet,
    entrepot_productivite_view,
    scanner_resoudre_view, scanner_mouvement_view,
)

router = DefaultRouter()
router.register(r'produits', ProduitViewSet)
router.register(r'categories', CategorieViewSet)
router.register(r'fournisseurs', FournisseurViewSet)
router.register(r'mouvements', MouvementStockViewSet)
router.register(r'marques', MarqueViewSet)
router.register(r'bons-commande-fournisseur', BonCommandeFournisseurViewSet)
router.register(r'emplacements', EmplacementStockViewSet)
router.register(r'transferts', TransfertStockViewSet)
router.register(r'prix-fournisseurs', PrixFournisseurViewSet)
router.register(r'retours-fournisseur', RetourFournisseurViewSet)
router.register(r'receptions-fournisseur', ReceptionFournisseurViewSet)
router.register(r'factures-fournisseur', FactureFournisseurViewSet)
router.register(r'paiements-fournisseur', PaiementFournisseurViewSet)
router.register(r'inventaire-sessions', InventaireSessionViewSet)
router.register(r'kits', KitProduitViewSet)
router.register(r'fiches-techniques', FicheTechniqueViewSet)
router.register(
    r'documents-conformite-fournisseur', DocumentConformiteFournisseurViewSet)
router.register(
    r'achats-parametres', AchatsParametresViewSet,
    basename='achats-parametres')
router.register(r'contacts-fournisseur', ContactFournisseurViewSet)
router.register(r'categories-fournisseur', CategorieFournisseurViewSet)
router.register(r'acomptes-fournisseur', AcompteFournisseurViewSet)
router.register(r'avoirs-fournisseur', AvoirFournisseurViewSet)
router.register(r'lots-entrepot', LotEntrepotViewSet)
router.register(r'inventaires-annuels', InventaireAnnuelViewSet)
router.register(r'revalorisations-stock', RevalorisationStockViewSet)
router.register(r'conditionnements', ConditionnementProduitViewSet)
router.register(r'modeles-bcf', ModeleBonCommandeFournisseurViewSet)
router.register(
    r'nomenclatures-code-barres', NomenclatureCodeBarresViewSet)
router.register(r'regles-code-barres', RegleCodeBarresViewSet)
# -- Groupe NTWMS -- couche ENTREPOT --
router.register(r'vagues-picking', VaguePickingViewSet)
router.register(r'unites-logistiques', UniteLogistiqueViewSet)
router.register(r'quais', QuaiViewSet)
router.register(r'rendez-vous-transporteur', RendezVousTransporteurViewSet)
router.register(r'expeditions', ExpeditionTransporteurViewSet)
router.register(
    r'plans-comptage-tournant', PlanComptageTournantViewSet)
router.register(r'alertes-rappel', AlerteRappelViewSet)
router.register(r'portails-tiers', PortailTiersTokenViewSet)
router.register(r'demandes-transfert', DemandeTransfertViewSet)

urlpatterns = [
    # NTWMS8 - kiosque de quai (chemin nomme par la tache : /stock/public/...).
    path('public/quai-checkin/', quai_checkin_view,
         name='stock-quai-checkin'),
    # NTWMS20 - portail 3PL : solde du SEUL depositaire porteur du jeton.
    path('public/tiers/<str:token>/solde/', portail_tiers_solde_view,
         name='stock-portail-tiers-solde'),
    # NTWMS18 - productivite entrepot par operateur (responsable/admin).
    # L'endpoint vit dans `stock` (et non dans `reporting`) : cette lane ne
    # possede que l'app stock -- la donnee et sa garde restent au meme endroit.
    path('entrepot/productivite/', entrepot_productivite_view,
         name='stock-entrepot-productivite'),
    # NTWMS5 - poste scanner mobile (resolution universelle + mouvement scanne).
    path('scanner/resoudre/', scanner_resoudre_view,
         name='stock-scanner-resoudre'),
    path('scanner/mouvement/', scanner_mouvement_view,
         name='stock-scanner-mouvement'),
    path('', include(router.urls)),
]
