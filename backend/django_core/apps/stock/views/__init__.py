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
]
