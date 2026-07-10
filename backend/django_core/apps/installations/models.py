"""
Module Chantiers / Installations — l'objet pivot de l'après-vente.

Le chantier (Installation) est créé une fois le devis signé/accepté. C'est le
dossier de réalisation auquel tout l'après-vente (interventions, mise en
service, et plus tard parc équipements / garanties / SAV) viendra s'attacher.

Trois couches de statuts INDÉPENDANTES coexistent dans l'OS, à ne jamais
mélanger :
  1. l'étape du lead (STAGES.py — l'entonnoir commercial) ;
  2. le statut du document devis/facture (ventes) ;
  3. le statut du CHANTIER ci-dessous (réalisation physique).

Cet enum est une liste FERMÉE, en ordre d'entonnoir. « annulé » n'est PAS une
étape : c'est un drapeau (avec motif), comme « Perdu » sur un lead.

SURFACE D'IMPORT — le monolithe a été éclaté par domaine
(``models_installation`` / ``models_intervention`` / ``models_chantier`` /
``models_field``). Ce module ré-exporte toutes les classes pour que
``from apps.installations.models import …`` et la découverte des modèles par
Django (``app_label``, noms de table, migrations) restent strictement
inchangés.
"""
from .models_installation import Installation
from .models_equipe import (
    Equipe,
)
from .models_intervention import (
    TypeIntervention,
    Intervention,
    InterventionActivity,
    InstallationActivity,
    TypeInterventionPlan,
    RecurrenceIntervention,
)
from .models_chantier import (
    ChecklistTemplate,
    ChecklistEtapeModele,
    StageModele,
    CommissioningRecord,
    CommissioningIVReading,
    ReverificationMesure,
    HandoverPack,
    StockReservation,
    ChantierChecklistItem,
    ShotListSlot,
)
from .models_field import (
    InterventionPreparation,
    PreparationMaterielLigne,
    PreparationOutilLigne,
    ComponentSerial,
    PhotoAnnotation,
    MaterielConsommation,
    ConsommationLigne,
    VoiceMemo,
    Reserve,
    ToolReturn,
    SafetyChecklistSlot,
    SafetySignoff,
    SafetyCheckItem,
    FieldOp,
    FicheInterventionTemplate,
    FicheInterventionChamp,
    FicheInterventionReleve,
    FicheInterventionValeur,
)
from .models_projet import (
    JalonProjet,
    ModeleProjet,
    ModeleProjetJalon,
    ModeleProjetBomLigne,
    ReunionChantier,
)
from .models_document import (
    DocumentProjet,
    RevisionDocument,
)
from .models_program import (
    Projet,
    ProjetTache,
    ProjetChantier,
    ProjetDevis,
    ProjetTicket,
    BudgetProjet,
    BudgetEngagement,
)
from .models_indispo import (
    IndisponibiliteRessource,
)
from .models_astreinte import (
    Astreinte,
)
# DC34 — l'ancien référentiel parallèle (installations.SousTraitant, FG304) et
# l'AP dédiée (installations.FactureSousTraitant/PaiementSousTraitant, FG306) sont
# supprimés : un sous-traitant est un stock.Fournisseur(type='service') et son AP
# passe par la chaîne standard stock.FactureFournisseur/PaiementFournisseur.
from .models_ordre_soustraitance import (
    OrdreSousTraitance,
)
from .models_attestation_soustraitant import (
    AttestationSousTraitant,
)
from .models_evaluation_soustraitant import (
    EvaluationSousTraitant,
)
from .models_retenue_garantie import (
    RetenueGarantieSousTraitant,
)
from .models_demande_achat import (
    DemandeAchat,
    DemandeAchatLigne,
)
from .models_rfq import (
    RFQ,
    RFQOffre,
    RFQConsultation,
)
from .models_approbation_bcf import (
    SeuilApprobationBCF,
    ApprobationBCF,
)
from .models_commande_cadre import (
    CommandeCadre,
    CommandeCadreLigne,
    AppelCommande,
)
from .models_dossier_import import (
    DossierImport,
)
from .models_landed_cost import (
    FraisImport,
    LandedCostLigne,
)
from .models_gr_ir import (
    ReceptionNonFacturee,
)
from .models_contrat_prix import (
    ContratPrixFournisseur,
    ContratPrixLigne,
)
from .models_bin_location import (
    BinLocation,
    BinAffectation,
)
from .models_putaway import (
    PutAway,
)
from .models_picklist import (
    PickList,
    PickListLigne,
)
from .models_colisage import (
    Colis,
    ColisLigne,
)
from .models_serie_entrepot import (
    SerieEntrepot,
)
from .models_comptage import (
    SessionComptage,
    ComptageLigne,
)
from .models_demande_transfert import (
    DemandeTransfert,
)
from .models_reappro import (
    RegleReappro,
)
from .models_consignation import (
    MaterielConsigne,
)
from .models_kitting import (
    Kit,
    KitComposant,
    RevisionKit,
    OrdreAssemblage,
    ReservationAssemblage,
    OrdreAssemblageActivity,
    OrdreAssemblageLigne,
    SerieAssemblage,
    OrdreDemontage,
    OrdreDemontageLigne,
    ControleQualiteModele,
    ControleQualiteItemModele,
    ControleQualiteOrdre,
    EtapeAssemblage,
    EtapeOrdre,
)
from .models_livraison import (
    Livraison,
    LivraisonLigne,
)
from .models_pod import (
    PreuveLivraison,
)
from .models_transporteur import (
    Transporteur,
)
from .models_retour_materiel import (
    RetourMateriel,
    RetourMaterielLigne,
)
from .models_retour_livraison import (
    RetourLivraison,
    RetourLivraisonLigne,
)
from .models_storage_rules import (
    CategorieStockage,
    RegleRangement,
)
from .models_lot_prelevement import (
    LotPrelevement,
)
from .models_gps_tracking import (
    GpsConsentRecord,
    PositionTechnicien,
    GeofenceAlert,
)

__all__ = [
    'Installation',
    'Equipe',
    'TypeIntervention',
    'Intervention',
    'InterventionActivity',
    'InstallationActivity',
    'TypeInterventionPlan',
    'RecurrenceIntervention',
    'ChecklistTemplate',
    'ChecklistEtapeModele',
    'StageModele',
    'CommissioningRecord',
    'CommissioningIVReading',
    'ReverificationMesure',
    'HandoverPack',
    'StockReservation',
    'ChantierChecklistItem',
    'ShotListSlot',
    'InterventionPreparation',
    'PreparationMaterielLigne',
    'PreparationOutilLigne',
    'ComponentSerial',
    'PhotoAnnotation',
    'MaterielConsommation',
    'ConsommationLigne',
    'VoiceMemo',
    'Reserve',
    'ToolReturn',
    'SafetyChecklistSlot',
    'SafetySignoff',
    'SafetyCheckItem',
    'FieldOp',
    'FicheInterventionTemplate',
    'FicheInterventionChamp',
    'FicheInterventionReleve',
    'FicheInterventionValeur',
    'JalonProjet',
    'ModeleProjet',
    'ModeleProjetJalon',
    'ModeleProjetBomLigne',
    'ReunionChantier',
    'DocumentProjet',
    'RevisionDocument',
    'Projet',
    'ProjetTache',
    'ProjetChantier',
    'ProjetDevis',
    'ProjetTicket',
    'BudgetProjet',
    'BudgetEngagement',
    'IndisponibiliteRessource',
    'Astreinte',
    'OrdreSousTraitance',
    'AttestationSousTraitant',
    'EvaluationSousTraitant',
    'RetenueGarantieSousTraitant',
    'DemandeAchat',
    'DemandeAchatLigne',
    'RFQ',
    'RFQOffre',
    'RFQConsultation',
    'SeuilApprobationBCF',
    'ApprobationBCF',
    'CommandeCadre',
    'CommandeCadreLigne',
    'AppelCommande',
    'DossierImport',
    'FraisImport',
    'LandedCostLigne',
    'ReceptionNonFacturee',
    'ContratPrixFournisseur',
    'ContratPrixLigne',
    'BinLocation',
    'BinAffectation',
    'PutAway',
    'PickList',
    'PickListLigne',
    'Colis',
    'ColisLigne',
    'SerieEntrepot',
    'SessionComptage',
    'ComptageLigne',
    'DemandeTransfert',
    'RegleReappro',
    'MaterielConsigne',
    'Kit',
    'KitComposant',
    'RevisionKit',
    'OrdreAssemblage',
    'ReservationAssemblage',
    'OrdreAssemblageActivity',
    'OrdreAssemblageLigne',
    'SerieAssemblage',
    'OrdreDemontage',
    'OrdreDemontageLigne',
    'ControleQualiteModele',
    'ControleQualiteItemModele',
    'ControleQualiteOrdre',
    'EtapeAssemblage',
    'EtapeOrdre',
    'Livraison',
    'LivraisonLigne',
    'PreuveLivraison',
    'Transporteur',
    'RetourMateriel',
    'RetourMaterielLigne',
    'RetourLivraison',
    'RetourLivraisonLigne',
    'CategorieStockage',
    'RegleRangement',
    'LotPrelevement',
    'GpsConsentRecord',
    'PositionTechnicien',
    'GeofenceAlert',
]
