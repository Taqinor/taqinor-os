"""NTMIG8/12/13 — kits de migration par source×entité.

Chaque sous-module (:mod:`odoo`, :mod:`sage`, :mod:`generique`) déclare un
``KIT_REGISTRY`` clé → :class:`Kit`, fusionnés ici dans un seul registre
public. La clé est TOUJOURS produite par :func:`cle_kit` — jamais recomposée
à la main ailleurs, pour que la même paire (source, entité) résolve
identiquement le kit partout (analyse NTMIG7, validation NTMIG32, gabarit
NTMIG20).

Un kit ne s'IMPOSE jamais : ``apps.migration.validation``/``services``
l'importent en PARESSEUX (``importlib``) et retombent proprement sur les
règles locales/le mapping automatique du moteur d'import quand ce paquet — ou
la clé demandée — est absent.
"""
from dataclasses import dataclass, field


def cle_kit(source, entite):
    """Clé STABLE d'un kit — SEUL point de fabrication (NTMIG8/12/13/7/32/20).

    Forme ``"<source>:<entite>"`` (ex. ``"odoo:clients"``) : lisible, stable,
    et compatible avec le paramètre ``kit_cle`` (chaîne opaque) déjà consommé
    par ``validation.regles_effectives`` (NTMIG32, déjà livré).
    """
    return f'{source}:{entite}'


@dataclass(frozen=True)
class Kit:
    """Un kit de migration pour UN couple (source, entité).

    * ``mapping`` — colonne source (normalisée, minuscule) → champ cible
      ``dataimport`` ; fusionné avec le mapping automatique du moteur, jamais
      un remplacement total (une colonne non couverte par le kit reste
      mappée si le moteur la reconnaît déjà).
    * ``colonnes_montant`` — colonnes SOURCE dont la somme alimente le
      reconcile financier (NTMIG4/7) — noms de colonnes SOURCE, pas de champs
      cible (elles peuvent ne pas être mappées du tout, ex. un total TTC
      informatif non importé ligne à ligne).
    * ``cle_dedup`` — colonne source servant d'identifiant externe stable
      (rapprochement upsert / ``ExternalRef``).
    * ``regles_format`` — champ cible → liste de noms de règles
      (``apps.migration.validation.REGLES``), consommé par NTMIG32.
    * ``transformations`` — champ cible → liste de transformations
      (``apps.migration.transforms``, NTMIG14), appliquées à la volée entre
      le mapping et le commit (ex. normaliser un téléphone marocain avant que
      le moteur d'import ne l'enregistre).
    """

    mapping: dict = field(default_factory=dict)
    colonnes_montant: tuple = ()
    cle_dedup: str = ''
    regles_format: dict = field(default_factory=dict)
    transformations: dict = field(default_factory=dict)


def _fusionner(*modules_registres):
    fusion = {}
    for registre in modules_registres:
        fusion.update(registre)
    return fusion


def _registres():
    from . import generique, odoo, sage
    return odoo.KIT_REGISTRY, sage.KIT_REGISTRY, generique.KIT_REGISTRY


KIT_REGISTRY = _fusionner(*_registres())
