from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    InstallationViewSet, InterventionViewSet, TypeInterventionViewSet,
    ChecklistTemplateViewSet, ChecklistEtapeModeleViewSet, ShotListSlotViewSet,
    SafetyChecklistSlotViewSet,
    JalonProjetViewSet, ModeleProjetViewSet, ReunionChantierViewSet,
    DocumentProjetViewSet, RevisionDocumentViewSet, FieldSyncView,
    ProjetViewSet, ProjetTacheViewSet, ProjetChantierViewSet,
    ProjetDevisViewSet, ProjetTicketViewSet,
    BudgetProjetViewSet, BudgetEngagementViewSet,
    IndisponibiliteRessourceViewSet,
    SousTraitantViewSet,
    OrdreSousTraitanceViewSet,
    FactureSousTraitantViewSet,
    PaiementSousTraitantViewSet,
    AttestationSousTraitantViewSet,
    EvaluationSousTraitantViewSet,
    RetenueGarantieSousTraitantViewSet,
    DemandeAchatViewSet,
    DemandeAchatLigneViewSet,
    RFQViewSet,
    RFQOffreViewSet,
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
)

router = DefaultRouter()
router.register(r'chantiers', InstallationViewSet)
router.register(r'interventions', InterventionViewSet)
router.register(r'types-intervention', TypeInterventionViewSet)
router.register(r'checklist-templates', ChecklistTemplateViewSet)
router.register(r'checklist-etapes', ChecklistEtapeModeleViewSet)
router.register(r'shotlist-slots', ShotListSlotViewSet)
router.register(r'consignes-securite', SafetyChecklistSlotViewSet)
router.register(r'jalons-projet', JalonProjetViewSet)
router.register(r'modeles-projet', ModeleProjetViewSet)
router.register(r'reunions-chantier', ReunionChantierViewSet)
router.register(r'documents-projet', DocumentProjetViewSet)
router.register(r'revisions-document', RevisionDocumentViewSet)
router.register(r'programmes', ProjetViewSet)
router.register(r'programme-taches', ProjetTacheViewSet)
router.register(r'programme-chantiers', ProjetChantierViewSet)
router.register(r'programme-devis', ProjetDevisViewSet)
router.register(r'programme-tickets', ProjetTicketViewSet)
router.register(r'programme-budgets', BudgetProjetViewSet)
router.register(r'programme-engagements', BudgetEngagementViewSet)
router.register(r'indisponibilites-ressource', IndisponibiliteRessourceViewSet)
router.register(r'sous-traitants', SousTraitantViewSet)
router.register(r'ordres-sous-traitance', OrdreSousTraitanceViewSet)
router.register(r'factures-sous-traitant', FactureSousTraitantViewSet)
router.register(r'paiements-sous-traitant', PaiementSousTraitantViewSet)
router.register(r'attestations-sous-traitant', AttestationSousTraitantViewSet)
router.register(r'evaluations-sous-traitant', EvaluationSousTraitantViewSet)
router.register(r'retenues-garantie-sous-traitant', RetenueGarantieSousTraitantViewSet)
router.register(r'demandes-achat', DemandeAchatViewSet)
router.register(r'demandes-achat-lignes', DemandeAchatLigneViewSet)
router.register(r'rfq', RFQViewSet)
router.register(r'rfq-offres', RFQOffreViewSet)
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

urlpatterns = [
    # N91/F21 — synchro idempotente de la capture terrain hors-ligne.
    path('sync/', FieldSyncView.as_view(), name='installations-field-sync'),
    # FG313 — contrôle budgétaire consultatif avant commande.
    path('controle-budgetaire/', ControleBudgetaireCommandeView.as_view(),
         name='installations-controle-budgetaire'),
    path('', include(router.urls)),
]
