"""Shim de ré-export — la numérotation anti-collision a été relogée en fondation (ARC6).

L'algorithme canonique race-safe (DEV-/BC-/FAC-YYYYMM-NNNN ; plus-haut-utilisé+1
par société+période, savepoint+retry) vit désormais dans `core.numbering`, la
couche fondation — car ~15 apps l'importaient déjà en travers des frontières
d'apps (l'équivalent d'`ir.sequence` d'Odoo qui aurait vécu dans le module Sales).

Ce module reste un ré-export bit-identique : les ~53 importeurs existants
(`from apps.ventes.utils.references import next_reference, create_with_reference`)
continuent de marcher sans aucune édition. Ne rien ajouter ici — toute évolution
de l'algorithme se fait dans `core/numbering.py`.
"""
from core.numbering import (  # noqa: F401  (ré-export public — importeurs existants)
    MAX_ATTEMPTS,
    _SUFFIX_RE,
    _bucket_prefix,
    _period_segment,
    create_with_reference,
    next_reference,
)

__all__ = ['next_reference', 'create_with_reference']
