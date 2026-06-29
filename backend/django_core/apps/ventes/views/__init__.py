"""Vues de l'app Ventes — surface d'import publique.

L'ancien ``views.py`` monolithe a été éclaté en un module par ressource pour
que plusieurs vues puissent évoluer en parallèle sans se gêner. Ce package
ré-exporte toutes les classes/fonctions publiques pour que
``from apps.ventes.views import …`` (et ``urls.py``) continuent de fonctionner à
l'identique. Aucun changement de comportement ni d'endpoint."""
from .devis import DevisViewSet
from .ligne_devis import LigneDevisViewSet
from .bon_commande import BonCommandeViewSet
from .facture import FactureViewSet
from .avoir import AvoirViewSet
from .paiement import PaiementViewSet
from .ligne_facture import LigneFactureViewSet
from .email import email_config
from .credit_warning import client_credit_warning
from .releve_import import releve_dry_run, releve_commit
from .roof_config import roof_config
from .roof_layout import RoofLayoutViewSet  # FG245
from .fiche_technique import FicheTechniqueViewSet  # FG254
from .preset import DevisPresetViewSet  # QJ16-wiring

__all__ = [
    'DevisViewSet',
    'LigneDevisViewSet',
    'BonCommandeViewSet',
    'FactureViewSet',
    'AvoirViewSet',
    'PaiementViewSet',
    'LigneFactureViewSet',
    'email_config',
    'client_credit_warning',
    'releve_dry_run',
    'releve_commit',
    'roof_config',
    'RoofLayoutViewSet',
    'FicheTechniqueViewSet',
    'DevisPresetViewSet',
]
