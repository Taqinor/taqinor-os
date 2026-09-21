"""Shim de ré-export — la conversion en lettres a été promue en fondation (AOF108).

La conversion française « chiffres → lettres » (XFAC9, née pour la quittance de
paiement PDF marocaine) vit désormais dans `core.nombre_lettres`, la couche
fondation — car plusieurs domaines la consomment, et une app domaine ne peut
pas importer un module d'une autre app domaine (contrats import-linter).

Ce module reste un ré-export BIT-IDENTIQUE : les importeurs existants
(`from apps.ventes.utils.nombre_lettres import montant_en_lettres`) continuent
de marcher sans aucune édition, et obtiennent LE MÊME objet fonction que la
fondation. Ne rien ajouter ici — toute évolution (dont le mode « administratif »
de l'arrêté, AOF109) se fait dans `core/nombre_lettres.py`.

Même patron exact que `apps/ventes/utils/references.py` → `core.numbering` (ARC6).
"""
from core.nombre_lettres import (  # noqa: F401  (ré-export public — importeurs existants)
    _DIZAINES,
    _TRANCHES,
    _UNITES,
    _entier_en_lettres,
    _moins_de_cent,
    _moins_de_mille,
    montant_en_lettres,
)

__all__ = ['montant_en_lettres']
