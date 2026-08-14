# -*- coding: utf-8 -*-
"""``core.electrique`` — le moteur de CONCEPTION ÉLECTRIQUE PV, paquet PUR.

Frère de ``core.calepinage`` : là où le calepinage répond « combien de modules
tiennent sur cette toiture et où », celui-ci répond « comment on les câble » —
chaînes, onduleurs, protections, sections de câble, nomenclature, schéma
unifilaire. Les deux consommateurs (``apps.ao`` pour la réponse à appel
d'offres, ``apps.ventes`` pour le devis/villa) ne peuvent pas s'importer l'un
l'autre : le moteur vit donc dans la couche fondation ``core``, et sa PURETÉ est
la contrepartie :

* stdlib UNIQUEMENT — zéro ``django``, zéro ``rest_framework``, zéro ``apps.*``,
  zéro autre module de ``core`` ;
* zéro I/O — le moteur ne lit ni n'écrit aucun fichier ; le rendu du schéma
  unifilaire retourne du TEXTE SVG que l'appelant écrit où il veut ;
* zéro globale mutable — toute configuration passe par une ``EntreeElectrique``
  immuable passée en ARGUMENT ;
* AUCUN PRIX — le moteur ne manipule que des grandeurs électriques publiques et
  des quantités. Le chiffrage reste l'affaire du devis.

Bénéfice décisif, identique à celui du calepinage : le paquet est testable SANS
base de données, donc ses tests tournent hors du gate migrations — le poste de
coût CI dominant.

Chaque constante NORMATIVE du moteur cite sa source en commentaire (NF C 15-100,
UTE C 15-712-1, IEC 62548, EN 50618) : un calibre ou une section qu'on ne sait
pas rattacher à une règle est un calibre qu'on ne sait pas défendre devant un
bureau de contrôle.

La pureté est armée en CI par le contrat import-linter
``electrique-est-un-noyau-pur`` ET par ``core/tests/test_electrique_purete.py``
(analyse AST : tout import interdit rend le test ROUGE).
"""

from core.electrique.types import (
    Cable,
    Chaine,
    Conformite,
    EntreeElectrique,
    GroupePan,
    LigneNomenclature,
    Protection,
    Ratio,
    ResultatElectrique,
    SpecModule,
    SpecOnduleur,
)
from core.electrique.version import (
    SCHEMA_VERSION,
    VERSION_MOTEUR,
    compatible,
    version_tuple,
)

__all__ = [
    "SCHEMA_VERSION",
    "VERSION_MOTEUR",
    "compatible",
    "version_tuple",
    "Cable",
    "Chaine",
    "Conformite",
    "EntreeElectrique",
    "GroupePan",
    "LigneNomenclature",
    "Protection",
    "Ratio",
    "ResultatElectrique",
    "SpecModule",
    "SpecOnduleur",
]
