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
from .models_intervention import (
    TypeIntervention,
    Intervention,
    InterventionActivity,
    InstallationActivity,
    TypeInterventionPlan,
)
from .models_chantier import (
    ChecklistTemplate,
    ChecklistEtapeModele,
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
)

__all__ = [
    'Installation',
    'TypeIntervention',
    'Intervention',
    'InterventionActivity',
    'InstallationActivity',
    'TypeInterventionPlan',
    'ChecklistTemplate',
    'ChecklistEtapeModele',
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
]
