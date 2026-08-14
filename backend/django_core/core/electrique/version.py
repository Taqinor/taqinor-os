# -*- coding: utf-8 -*-
"""PV33 — Version SÉMANTIQUE du moteur électrique (miroir de calepinage/version).

Tout artefact produit par le moteur (conception de chaînes, note de calcul,
nomenclature, schéma unifilaire) porte la version du moteur qui l'a produit :
sans elle, deux dossiers techniques identiques à l'œil peuvent sortir de deux
moteurs différents et personne ne sait lequel fait foi devant l'ONEE.

Convention MAJEUR.MINEUR.CORRECTIF :

* MAJEUR  — le contrat de données (``types.py``) change de façon incompatible,
  OU un nombre publiable change à entrée identique (une section de câble, un
  calibre de protection, une longueur de chaîne) ;
* MINEUR  — capacité ajoutée (nouvelle règle, nouveau format de schéma) sans
  changer un nombre existant ;
* CORRECTIF — correction interne strictement sans effet sur les nombres.

Un changement de MAJEUR invalide les dossiers déjà déposés : ils doivent être
rejoués avant d'être re-remis à un client ou au gestionnaire de réseau.
"""

VERSION_MOTEUR = "1.0.0"

#: Version du schéma d'échange (dictionnaires de projection ``tiroirs`` et
#: nomenclature). Elle évolue indépendamment de ``VERSION_MOTEUR`` : le moteur
#: peut gagner une règle sans changer le format d'échange.
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
