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

Journal des MAJEUR :

* **2.0.0 — PV65, élévation solaire dérivée de la LATITUDE.** ``AntiOmbrage``
  sait désormais calculer le soleil de dimensionnement du lieu (déclinaison du
  solstice + angle horaire de 10 h) au lieu de la seule constante nationale de
  21°. Une villa d'Agadir et une villa de Tanger cessent d'être espacées
  pareil, donc **un compte publiable change à toiture identique** dès que la
  latitude est déclarée : c'est la définition même d'un MAJEUR ici. Le chemin
  sans latitude reste IDENTIQUE au bit près (les golden villa passent sans
  être régénérés) — le MAJEUR dit qu'une étude publiée sous 1.x doit être
  rejouée avant d'être re-remise, pas que son chiffre a bougé tout seul.
"""

VERSION_MOTEUR = "2.0.0"

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
