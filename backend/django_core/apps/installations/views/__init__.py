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
)
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
    'FieldSyncView',
]
