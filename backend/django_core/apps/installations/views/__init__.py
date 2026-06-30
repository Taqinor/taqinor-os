"""Vues de l'app Installations (chantiers) — surface d'import publique.

L'ancien ``views.py`` monolithe a été éclaté en un module par ressource pour
que plusieurs vues puissent évoluer en parallèle sans se gêner. Ce package
ré-exporte toutes les classes/fonctions publiques pour que
``from apps.installations.views import …`` (et ``urls.py``) continuent de
fonctionner à l'identique. Aucun changement de comportement ni d'endpoint."""
from .type_intervention import TypeInterventionViewSet, seed_types_intervention
from .installation import InstallationViewSet
from .checklist_template import ChecklistTemplateViewSet
from .checklist_etape import ChecklistEtapeModeleViewSet
from .intervention import InterventionViewSet
from .shotlist import ShotListSlotViewSet
from .safety import SafetyChecklistSlotViewSet
from .projet import (
    JalonProjetViewSet, ModeleProjetViewSet, ReunionChantierViewSet,
)
from .document import DocumentProjetViewSet, RevisionDocumentViewSet
from .program import (
    ProjetViewSet, ProjetTacheViewSet, ProjetChantierViewSet,
    ProjetDevisViewSet, ProjetTicketViewSet,
    BudgetProjetViewSet, BudgetEngagementViewSet,
)
from .indispo import IndisponibiliteRessourceViewSet
from .soustraitant import SousTraitantViewSet
from .ordre_soustraitance import OrdreSousTraitanceViewSet
from .facture_soustraitant import (
    FactureSousTraitantViewSet, PaiementSousTraitantViewSet,
)
from .attestation_soustraitant import AttestationSousTraitantViewSet
from .evaluation_soustraitant import EvaluationSousTraitantViewSet
from .retenue_garantie import RetenueGarantieSousTraitantViewSet
from .demande_achat import DemandeAchatViewSet, DemandeAchatLigneViewSet
from .rfq import RFQViewSet, RFQOffreViewSet
from .approbation_bcf import (
    SeuilApprobationBCFViewSet, ApprobationBCFViewSet,
)
from .controle_budgetaire import ControleBudgetaireCommandeView
from .commande_cadre import (
    CommandeCadreViewSet, CommandeCadreLigneViewSet, AppelCommandeViewSet,
)
from .dossier_import import DossierImportViewSet
from .landed_cost import FraisImportViewSet, LandedCostLigneViewSet
from .gr_ir import ReceptionNonFactureeViewSet
from .contrat_prix import (
    ContratPrixFournisseurViewSet, ContratPrixLigneViewSet,
)
from .bin_location import BinLocationViewSet, BinAffectationViewSet
from .putaway import PutAwayViewSet
from .picklist import PickListViewSet, PickListLigneViewSet
from .colisage import ColisViewSet, ColisLigneViewSet
from .serie_entrepot import SerieEntrepotViewSet
from .comptage import SessionComptageViewSet, ComptageLigneViewSet
from .demande_transfert import DemandeTransfertViewSet
from .reappro import RegleReapproViewSet
from .consignation import MaterielConsigneViewSet
from .kitting import (
    KitViewSet, KitComposantViewSet, OrdreAssemblageViewSet,
)
from .livraison import LivraisonViewSet, LivraisonLigneViewSet
from .pod import PreuveLivraisonViewSet
from .transporteur import TransporteurViewSet
from .field_sync import FieldSyncView

__all__ = [
    'TypeInterventionViewSet',
    'seed_types_intervention',
    'InstallationViewSet',
    'ChecklistTemplateViewSet',
    'ChecklistEtapeModeleViewSet',
    'InterventionViewSet',
    'ShotListSlotViewSet',
    'SafetyChecklistSlotViewSet',
    'JalonProjetViewSet',
    'ModeleProjetViewSet',
    'ReunionChantierViewSet',
    'DocumentProjetViewSet',
    'RevisionDocumentViewSet',
    'ProjetViewSet',
    'ProjetTacheViewSet',
    'ProjetChantierViewSet',
    'ProjetDevisViewSet',
    'ProjetTicketViewSet',
    'BudgetProjetViewSet',
    'BudgetEngagementViewSet',
    'IndisponibiliteRessourceViewSet',
    'SousTraitantViewSet',
    'OrdreSousTraitanceViewSet',
    'FactureSousTraitantViewSet',
    'PaiementSousTraitantViewSet',
    'AttestationSousTraitantViewSet',
    'EvaluationSousTraitantViewSet',
    'RetenueGarantieSousTraitantViewSet',
    'DemandeAchatViewSet',
    'DemandeAchatLigneViewSet',
    'RFQViewSet',
    'RFQOffreViewSet',
    'SeuilApprobationBCFViewSet',
    'ApprobationBCFViewSet',
    'ControleBudgetaireCommandeView',
    'CommandeCadreViewSet',
    'CommandeCadreLigneViewSet',
    'AppelCommandeViewSet',
    'DossierImportViewSet',
    'FraisImportViewSet',
    'LandedCostLigneViewSet',
    'ReceptionNonFactureeViewSet',
    'ContratPrixFournisseurViewSet',
    'ContratPrixLigneViewSet',
    'BinLocationViewSet',
    'BinAffectationViewSet',
    'PutAwayViewSet',
    'PickListViewSet',
    'PickListLigneViewSet',
    'ColisViewSet',
    'ColisLigneViewSet',
    'SerieEntrepotViewSet',
    'SessionComptageViewSet',
    'ComptageLigneViewSet',
    'DemandeTransfertViewSet',
    'RegleReapproViewSet',
    'MaterielConsigneViewSet',
    'KitViewSet',
    'KitComposantViewSet',
    'OrdreAssemblageViewSet',
    'LivraisonViewSet',
    'LivraisonLigneViewSet',
    'PreuveLivraisonViewSet',
    'TransporteurViewSet',
    'FieldSyncView',
]
