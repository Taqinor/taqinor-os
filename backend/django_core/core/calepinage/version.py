# -*- coding: utf-8 -*-
"""Version SÉMANTIQUE du moteur de calepinage (AOF33).

Tout artefact rendu (plan, planche, étude, JSON) porte le couple
``(hash_entree, version_moteur)`` : sans lui, deux planches identiques à l'œil
peuvent sortir de deux moteurs différents et personne ne sait laquelle fait foi.

Convention MAJEUR.MINEUR.CORRECTIF :

* MAJEUR  — le contrat de données (``types.py`` / ``serialisation.py``) change
  de façon incompatible, OU un compte publiable change à entrée identique ;
* MINEUR  — capacité ajoutée (nouvelle surface, nouvelle politique de pas,
  nouvelle recommandation) sans changer un compte existant ;
* CORRECTIF — correction interne strictement sans effet sur les comptes.

Un changement de MAJEUR invalide les études déjà publiées : elles doivent être
rejouées avant d'être re-remises à un maître d'ouvrage.
"""

VERSION_MOTEUR = "1.0.0"

#: Version du schéma JSON d'entrée/sortie (``serialisation.py``). Elle évolue
#: indépendamment de ``VERSION_MOTEUR`` : un moteur peut gagner une capacité
#: sans changer le format d'échange.
SCHEMA_VERSION = 1


def version_tuple(version=VERSION_MOTEUR):
    """``"1.2.3"`` -> ``(1, 2, 3)`` — comparable par tuple."""
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError("version sémantique attendue MAJEUR.MINEUR.CORRECTIF")
    return tuple(int(p) for p in parts)


def compatible(version_artefact, version_moteur=VERSION_MOTEUR):
    """Un artefact reste rejouable tant que le MAJEUR n'a pas bougé."""
    return version_tuple(version_artefact)[0] == version_tuple(version_moteur)[0]
