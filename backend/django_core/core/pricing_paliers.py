"""FG364 — Calcul de prix par paliers (tiered/volume pricing), fondation pure — NTSUB3.

Comme :mod:`core.stock_reorder`, :mod:`core.churn_risk` et :mod:`core.clv`, ce
module reste une couche de BASE — contrat import-linter
``core-foundation-is-a-base-layer`` : il n'importe AUCUNE app métier. L'app
appelante (``apps.sav`` pour XCTR16, ``apps.contrats`` pour NTSUB2/4) agrège ses
propres paliers (``PalierUsage`` en base) et son usage via SA couche
``selectors``/``models``, puis passe ces ENTRÉES à
:func:`calculer_prix_paliers` ; ce module fournit uniquement le moteur de calcul
générique — pas de base de données, pas de réseau, bibliothèque standard
seulement.

Deux modes de facturation par palier :

  * ``volume``    : la TOTALITÉ de l'usage est facturée au tarif du DERNIER
    palier ATTEINT (le palier dont ``seuil_min <= usage``). Ex. paliers
    ``[0-100 @ 2, 100-∞ @ 1.5]`` et un usage de 150 → 150 × 1.5.
  * ``graduated`` : CHAQUE tranche d'usage est facturée à SON tarif propre, puis
    les montants des tranches sont additionnés. Ex. mêmes paliers, usage 150 →
    (100 × 2) + (50 × 1.5) = 275.

RÉTROCOMPATIBILITÉ : une liste de paliers VIDE (ou ``None``) signifie « pas de
palier configuré » — l'appelant garde alors son tarif unique existant
(``calculer_prix_paliers`` renvoie ``None`` dans ce cas, jamais ``0`` : un
``0`` serait ambigu avec « paliers configurés mais montant nul »).

GARDES : un usage nul/négatif renvoie ``Decimal('0')`` (jamais d'erreur, jamais
de montant négatif) ; un palier sans ``seuil_max`` (``None``) est traité comme
« jusqu'à l'infini ».
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Optional

MODE_VOLUME = 'volume'
MODE_GRADUATED = 'graduated'


def _to_decimal(value, default=Decimal('0')) -> Decimal:
    """Convertit ``value`` en ``Decimal`` ou renvoie ``default`` si non numérique."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — entrée non numérique quelconque
        return default


@dataclass
class Palier:
    """Une tranche de tarif normalisée (entrée interne du moteur).

    ``seuil_max`` à ``None`` = tranche ouverte jusqu'à l'infini.
    """
    seuil_min: Decimal
    seuil_max: Optional[Decimal]
    prix_unitaire: Decimal


def _normaliser_paliers(paliers: Iterable) -> list:
    """Normalise ``paliers`` (dicts, tuples ou objets ``PalierUsage``-like) en
    une liste de :class:`Palier` triée par ``seuil_min`` croissant.

    Accepte des dicts ``{seuil_min, seuil_max, prix_unitaire}``, des tuples
    ``(seuil_min, seuil_max, prix_unitaire)``, ou tout objet portant ces trois
    attributs (ex. une instance ``apps.contrats.models.PalierUsage``) — jamais
    d'import du modèle ici (le module reste pur).
    """
    normalises = []
    for p in paliers or []:
        if isinstance(p, dict):
            seuil_min = p.get('seuil_min')
            seuil_max = p.get('seuil_max')
            prix_unitaire = p.get('prix_unitaire')
        elif isinstance(p, (tuple, list)):
            seuil_min, seuil_max, prix_unitaire = (list(p) + [None, None, None])[:3]
        else:
            seuil_min = getattr(p, 'seuil_min', None)
            seuil_max = getattr(p, 'seuil_max', None)
            prix_unitaire = getattr(p, 'prix_unitaire', None)
        normalises.append(Palier(
            seuil_min=_to_decimal(seuil_min, Decimal('0')),
            seuil_max=(
                None if seuil_max is None else _to_decimal(seuil_max)),
            prix_unitaire=_to_decimal(prix_unitaire, Decimal('0')),
        ))
    normalises.sort(key=lambda pl: pl.seuil_min)
    return normalises


def calculer_prix_paliers(usage, paliers: Iterable, mode: str = MODE_VOLUME) -> Optional[Decimal]:
    """Calcule le montant facturable d'un ``usage`` selon des ``paliers`` de prix.

    Renvoie ``None`` si ``paliers`` est vide/``None`` (rétrocompatibilité —
    l'appelant retombe sur son tarif unique existant, comportement XCTR16
    inchangé). Renvoie ``Decimal('0')`` pour un usage nul/négatif (jamais
    d'erreur). Le résultat est arrondi à 2 décimales (``ROUND_HALF_UP``,
    cohérent avec le reste de l'ERP 100 % TTC).

    ``mode`` :
      * ``'volume'``    (:data:`MODE_VOLUME`)    — tarif du dernier palier
        ATTEINT appliqué à la TOTALITÉ de l'usage ;
      * ``'graduated'`` (:data:`MODE_GRADUATED`) — chaque tranche à son tarif,
        cumulée.

    Pur, déterministe, sans base de données ni réseau.
    """
    normalises = _normaliser_paliers(paliers)
    if not normalises:
        return None

    usage_decimal = _to_decimal(usage, Decimal('0'))
    if usage_decimal <= 0:
        return Decimal('0.00')

    if mode == MODE_GRADUATED:
        total = Decimal('0')
        for palier in normalises:
            borne_haute = (
                palier.seuil_max if palier.seuil_max is not None
                else usage_decimal)
            if usage_decimal <= palier.seuil_min:
                continue
            tranche_haute = min(usage_decimal, borne_haute)
            largeur = tranche_haute - palier.seuil_min
            if largeur > 0:
                total += largeur * palier.prix_unitaire
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Mode 'volume' (par défaut) : tarif du DERNIER palier atteint appliqué à
    # la totalité de l'usage.
    palier_atteint = normalises[0]
    for palier in normalises:
        if usage_decimal >= palier.seuil_min:
            palier_atteint = palier
        else:
            break
    total = usage_decimal * palier_atteint.prix_unitaire
    return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
