"""Vues de l'app Stock — surface d'import publique.

L'ancien ``views.py`` monolithe a été éclaté en un module par ressource pour
que plusieurs vues puissent évoluer en parallèle sans se gêner. Ce package
ré-exporte toutes les classes/fonctions publiques pour que
``from apps.stock.views import …`` (et ``urls.py``) continuent de fonctionner à
l'identique. Aucun changement de comportement ni d'endpoint."""
from .produit import ProduitViewSet
from .marque import MarqueViewSet, seed_marques
from .categorie import CategorieViewSet
from .fournisseur import (
    FournisseurViewSet, ContactFournisseurViewSet, CategorieFournisseurViewSet,
)
from .mouvement import MouvementStockViewSet
from .prix_fournisseur import PrixFournisseurViewSet
from .emplacement import EmplacementStockViewSet
from .transfert import TransfertStockViewSet
from .retour_fournisseur import RetourFournisseurViewSet
from .bon_commande_fournisseur import BonCommandeFournisseurViewSet
from .reception_fournisseur import ReceptionFournisseurViewSet
from .facture_fournisseur import FactureFournisseurViewSet
from .paiement_fournisseur import PaiementFournisseurViewSet
from .inventaire_session import InventaireSessionViewSet
from .kit import KitProduitViewSet
from .fiche_technique import FicheTechniqueViewSet
from .conformite_fournisseur import (
    DocumentConformiteFournisseurViewSet, AchatsParametresViewSet,
)
from .acompte_fournisseur import AcompteFournisseurViewSet
from .avoir_fournisseur import AvoirFournisseurViewSet
from .lot_entrepot import LotEntrepotViewSet
from .inventaire_annuel import InventaireAnnuelViewSet
from .revalorisation_stock import RevalorisationStockViewSet
from .conditionnement_produit import ConditionnementProduitViewSet
from .modele_bcf import ModeleBonCommandeFournisseurViewSet
from .nomenclature_code_barres import (
    NomenclatureCodeBarresViewSet, RegleCodeBarresViewSet,
)
# Groupe NTWMS - couche entrepot (vagues, unites logistiques, quais...).
from .wms import (
    VaguePickingViewSet, UniteLogistiqueViewSet, QuaiViewSet,
    RendezVousTransporteurViewSet, ExpeditionTransporteurViewSet,
    PlanComptageTournantViewSet, AlerteRappelViewSet,
    PortailTiersTokenViewSet, RetourClientViewSet,
    MouvementRebutViewSet, PlanChargementViewSet, BlocageQualiteViewSet,
    entrepot_productivite_view, entrepot_pertes_view,
    reslotting_suggestions_view, casiers_etiquettes_pdf_view,
)
from .scanner import (
    scanner_resoudre_view, scanner_mouvement_view,
    scanner_retour_fournisseur_view,
)
# Groupe NTWMS (vague 3) - pilotage d'entrepot (cockpit, capacite, retour).
from .entrepot import (
    entrepot_cockpit_view, simuler_capacite_view, zones_surcapacite_view,
    tache_retour_view, historique_casier_view,
)
# NTWMS34 - plans d'echantillonnage a reception (controle qualite bloquant).
from .qualite_reception import PlanEchantillonnageViewSet
# NTWMS38 - compatibilite casier <-> matiere dangereuse (hazmat).
from .hazmat import CompatibiliteHazmatCasierViewSet
# NTSCM9 - incidents qualite fournisseur (alimente scorecard + TCO).
from .fournisseur_scm import IncidentQualiteFournisseurViewSet
# NTWMS40 - reappro des casiers picking depuis le stockage.
from .reappro_casier import (
    SeuilReapproCasierViewSet, TacheReapproInterneViewSet,
    casiers_a_reapprovisionner_view,
)

__all__ = [
    'ProduitViewSet',
    'MarqueViewSet',
    'seed_marques',
    'CategorieViewSet',
    'FournisseurViewSet',
    'MouvementStockViewSet',
    'PrixFournisseurViewSet',
    'EmplacementStockViewSet',
    'TransfertStockViewSet',
    'RetourFournisseurViewSet',
    'BonCommandeFournisseurViewSet',
    'ReceptionFournisseurViewSet',
    'FactureFournisseurViewSet',
    'PaiementFournisseurViewSet',
    'InventaireSessionViewSet',
    'KitProduitViewSet',
    'FicheTechniqueViewSet',
    'DocumentConformiteFournisseurViewSet',
    'AchatsParametresViewSet',
    'ContactFournisseurViewSet',
    'CategorieFournisseurViewSet',
    'AcompteFournisseurViewSet',
    'AvoirFournisseurViewSet',
    'LotEntrepotViewSet',
    'InventaireAnnuelViewSet',
    'RevalorisationStockViewSet',
    'ConditionnementProduitViewSet',
    'ModeleBonCommandeFournisseurViewSet',
    'NomenclatureCodeBarresViewSet',
    'RegleCodeBarresViewSet',
    'VaguePickingViewSet',
    'UniteLogistiqueViewSet',
    'QuaiViewSet',
    'RendezVousTransporteurViewSet',
    'ExpeditionTransporteurViewSet',
    'PlanComptageTournantViewSet',
    'AlerteRappelViewSet',
    'PortailTiersTokenViewSet',
    'RetourClientViewSet',
    'MouvementRebutViewSet',
    'PlanChargementViewSet',
    'BlocageQualiteViewSet',
    'entrepot_productivite_view',
    'entrepot_pertes_view',
    'reslotting_suggestions_view',
    'casiers_etiquettes_pdf_view',
    'scanner_resoudre_view',
    'scanner_mouvement_view',
    'entrepot_cockpit_view',
    'simuler_capacite_view',
    'zones_surcapacite_view',
    'tache_retour_view',
    'PlanEchantillonnageViewSet',
    'CompatibiliteHazmatCasierViewSet',
    'historique_casier_view',
    'SeuilReapproCasierViewSet',
    'TacheReapproInterneViewSet',
    'casiers_a_reapprovisionner_view',
    'scanner_retour_fournisseur_view',
    'IncidentQualiteFournisseurViewSet',
]
