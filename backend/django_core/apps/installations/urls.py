from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    InstallationViewSet, InterventionViewSet, TypeInterventionViewSet,
    CommissioningRecordViewSet, StageModeleViewSet,
    ChecklistTemplateViewSet, ChecklistEtapeModeleViewSet, ShotListSlotViewSet,
    SafetyChecklistSlotViewSet,
    FicheInterventionTemplateViewSet, FicheInterventionChampViewSet,
    FieldSyncView,
    ProjetViewSet, ProjetTacheViewSet, ProjetChantierViewSet,
    ProjetDevisViewSet, ProjetTicketViewSet,
    BudgetProjetViewSet, BudgetEngagementViewSet,
    EquipeViewSet,
    SousTraitantViewSet,
    DemandeAchatViewSet,
    DemandeAchatLigneViewSet,
    RegleApprobationAchatViewSet,
    SeuilApprobationBCFViewSet,
    ApprobationBCFViewSet,
    ControleBudgetaireCommandeView,
    CommandeCadreViewSet,
    CommandeCadreLigneViewSet,
    AppelCommandeViewSet,
    DossierImportViewSet,
    FraisImportViewSet,
    LandedCostLigneViewSet,
    ReceptionNonFactureeViewSet,
    ContratPrixFournisseurViewSet,
    ContratPrixLigneViewSet,
    BinLocationViewSet,
    BinAffectationViewSet,
    CategorieStockageViewSet,
    RegleRangementViewSet,
    PutAwayViewSet,
    PickListViewSet,
    PickListLigneViewSet,
    ColisViewSet,
    ColisLigneViewSet,
    SerieEntrepotViewSet,
    SessionComptageViewSet,
    ComptageLigneViewSet,
    DemandeTransfertViewSet,
    RegleReapproViewSet,
    MaterielConsigneViewSet,
    KitViewSet,
    KitComposantViewSet,
    OrdreAssemblageViewSet,
    OrdreAssemblageLigneViewSet,
    OrdreDemontageViewSet,
    OrdreDemontageLigneViewSet,
    ControleQualiteModeleViewSet,
    EtapeAssemblageViewSet,
    LivraisonViewSet,
    LivraisonLigneViewSet,
    PreuveLivraisonViewSet,
    TransporteurViewSet,
    TourneeLivraisonView,
    RetourMaterielViewSet,
    RetourMaterielLigneViewSet,
    RetourLivraisonViewSet,
    RetourLivraisonLigneViewSet,
    LotPrelevementViewSet,
    GpsConsentRecordViewSet,
    PositionTechnicienViewSet,
    GeofenceAlertViewSet,
)

router = DefaultRouter()
router.register(r'chantiers', InstallationViewSet)
router.register(r'interventions', InterventionViewSet)
router.register(r'types-intervention', TypeInterventionViewSet)
router.register(r'recettes-commissioning', CommissioningRecordViewSet)
router.register(r'etapes-chantier', StageModeleViewSet)
router.register(r'checklist-templates', ChecklistTemplateViewSet)
router.register(r'checklist-etapes', ChecklistEtapeModeleViewSet)
router.register(r'shotlist-slots', ShotListSlotViewSet)
router.register(r'fiche-intervention-templates', FicheInterventionTemplateViewSet)
router.register(r'fiche-intervention-champs', FicheInterventionChampViewSet)
router.register(r'consignes-securite', SafetyChecklistSlotViewSet)
router.register(r'programmes', ProjetViewSet)
router.register(r'programme-taches', ProjetTacheViewSet)
router.register(r'programme-chantiers', ProjetChantierViewSet)
router.register(r'programme-devis', ProjetDevisViewSet)
router.register(r'programme-tickets', ProjetTicketViewSet)
router.register(r'programme-budgets', BudgetProjetViewSet)
router.register(r'programme-engagements', BudgetEngagementViewSet)
router.register(r'equipes', EquipeViewSet)
# DC34 — annuaire des sous-traitants (référentiel UNIFIÉ, consommé aussi par
# btp_chantier et gestion_projet) : ViewSet façade au-dessus de stock
# (Fournisseur type=service) sans queryset propre → basename explicite requis.
router.register(r'sous-traitants', SousTraitantViewSet,
                basename='soustraitant')
router.register(r'demandes-achat', DemandeAchatViewSet)
router.register(r'demandes-achat-lignes', DemandeAchatLigneViewSet)
# NTP2P2 — règles d'approbation des demandes d'achat (seuil + périmètre).
router.register(r'regles-approbation-achat', RegleApprobationAchatViewSet)
router.register(r'seuils-approbation-bcf', SeuilApprobationBCFViewSet)
router.register(r'approbations-bcf', ApprobationBCFViewSet)
router.register(r'commandes-cadre', CommandeCadreViewSet)
router.register(r'commandes-cadre-lignes', CommandeCadreLigneViewSet)
router.register(r'appels-commande', AppelCommandeViewSet)
router.register(r'dossiers-import', DossierImportViewSet)
router.register(r'frais-import', FraisImportViewSet)
router.register(r'landed-cost-lignes', LandedCostLigneViewSet)
router.register(r'receptions-non-facturees', ReceptionNonFactureeViewSet)
router.register(r'contrats-prix-fournisseur', ContratPrixFournisseurViewSet)
router.register(r'contrats-prix-lignes', ContratPrixLigneViewSet)
router.register(r'bin-locations', BinLocationViewSet)
router.register(r'bin-affectations', BinAffectationViewSet)
router.register(r'categories-stockage', CategorieStockageViewSet)
router.register(r'regles-rangement', RegleRangementViewSet)
router.register(r'putaways', PutAwayViewSet)
router.register(r'pick-lists', PickListViewSet)
router.register(r'pick-list-lignes', PickListLigneViewSet)
router.register(r'colis', ColisViewSet)
router.register(r'colis-lignes', ColisLigneViewSet)
router.register(r'series-entrepot', SerieEntrepotViewSet)
router.register(r'sessions-comptage', SessionComptageViewSet)
router.register(r'comptage-lignes', ComptageLigneViewSet)
router.register(r'demandes-transfert', DemandeTransfertViewSet)
router.register(r'regles-reappro', RegleReapproViewSet)
router.register(r'materiels-consignes', MaterielConsigneViewSet)
router.register(r'kits', KitViewSet)
router.register(r'kit-composants', KitComposantViewSet)
router.register(r'ordres-assemblage', OrdreAssemblageViewSet)
router.register(r'ordre-assemblage-lignes', OrdreAssemblageLigneViewSet)
router.register(r'ordres-demontage', OrdreDemontageViewSet)
router.register(r'ordre-demontage-lignes', OrdreDemontageLigneViewSet)
router.register(r'controle-qualite-modeles', ControleQualiteModeleViewSet)
router.register(r'etapes-assemblage', EtapeAssemblageViewSet)
router.register(r'livraisons', LivraisonViewSet)
router.register(r'livraison-lignes', LivraisonLigneViewSet)
router.register(r'preuves-livraison', PreuveLivraisonViewSet)
router.register(r'transporteurs', TransporteurViewSet)
router.register(r'retours-materiel', RetourMaterielViewSet)
router.register(r'retour-materiel-lignes', RetourMaterielLigneViewSet)
router.register(r'retours-livraison', RetourLivraisonViewSet)
router.register(r'retour-livraison-lignes', RetourLivraisonLigneViewSet)
router.register(r'lots-prelevement', LotPrelevementViewSet)
# XFSM23 — consentement GPS + positions live + alertes géofence.
router.register(r'gps-consentements', GpsConsentRecordViewSet)
router.register(r'positions-techniciens', PositionTechnicienViewSet,
                basename='positiontechnicien')
router.register(r'geofence-alertes', GeofenceAlertViewSet,
                basename='geofencealert')

from .views_meteo import meteo_terrain  # noqa: E402  (NTMOB21)

urlpatterns = [
    # NTMOB21 — météo terrain du jour (Open-Meteo, cache serveur 1 h),
    # purement informative pour « Ma journée ».
    path('meteo/', meteo_terrain, name='installations-meteo-terrain'),
    # N91/F21 — synchro idempotente de la capture terrain hors-ligne.
    path('sync/', FieldSyncView.as_view(), name='installations-field-sync'),
    # FG313 — contrôle budgétaire consultatif avant commande.
    path('controle-budgetaire/', ControleBudgetaireCommandeView.as_view(),
         name='installations-controle-budgetaire'),
    # FG332 — tournée de livraison optimisée pour un jour (consultatif).
    path('tournee-livraison/', TourneeLivraisonView.as_view(),
         name='installations-tournee-livraison'),
    path('', include(router.urls)),
]
