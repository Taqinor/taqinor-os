"""ACAL980 — « Ce qui est supposé » : chaque repli CACHÉ du moteur, nommé.

``parametres_cles.py::registre`` annonce « aucun forfait », mais deux replis
restent silencieux dans ``GET resultat/`` : la longueur de chaîne de dossier
(``core.calepinage.electrique.MODULES_PAR_CHAINE``, prise quand les fiches ne
permettent pas de calculer la fenêtre de tension) et l'allée technique par
défaut du moteur (``core.calepinage.types.Parametres.allee_m``, prise quand la
société n'a rien réglé). Chaque entrée de ``suppose[]`` dit le repli, sa valeur
(LUE des constantes du moteur, jamais recopiée ici) et le champ à renseigner.
Aucun repli ⇒ liste vide. Le profil de consommation de départ n'est pas listé
ici (ACAL404 / ACAL405).
"""
from __future__ import annotations

import dataclasses

from core.calepinage.electrique import MODULES_PAR_CHAINE
from core.calepinage.types import Parametres

from .degagements import SECTION, allee_technique

__all__ = ['liste_des_suppositions', 'repli_longueur_dossier']

CHAMP_FICHES = 'fiche technique du module et de l\'onduleur'
CHAMP_ALLEE = ("panneau Allées de l'atelier (largeur de l'allée technique)")


def repli_longueur_dossier(dossier, origine):
    """La longueur de chaîne retenue quand les fiches ne permettent pas de
    calculer la fenêtre de tension (``longueur_chaine``, CAL170)."""
    return {
        'longueur': dossier,
        'origine': origine,
        'detail': "longueur de dossier (%d modules par chaîne) : les fiches "
                  "ne permettent "
                  "pas de calculer la fenêtre de tension — repli assumé, "
                  "jamais présenté comme un calcul" % dossier,
        'longueur_dossier': dossier,
        'ecart': None,
        'hors_tolerance': False,
        'par_pan': {},
    }


def _allee_du_moteur():
    """L'allée par défaut du moteur, lue sur le champ de ``Parametres``."""
    champs = {champ.name: champ for champ in dataclasses.fields(Parametres)}
    return champs['allee_m'].default


def liste_des_suppositions(longueur, societe, origine_dossier):
    """``[{code, libelle, valeur, champ}]`` — un repli caché par entrée.

    ``longueur`` : le dictionnaire ``longueur_chaine`` ; ``societe`` : les
    réglages société ; ``origine_dossier`` : l'origine qui marque le repli.
    """
    suppose = []
    if (longueur or {}).get('origine') == origine_dossier:
        suppose.append({
            'code': 'longueur_chaine_dossier',
            'libelle': "%d modules par chaîne (longueur retenue au dossier : "
                       "fiche du module ou de l'onduleur incomplète)"
                       % MODULES_PAR_CHAINE,
            'valeur': MODULES_PAR_CHAINE, 'champ': CHAMP_FICHES})
    if allee_technique((societe or {}).get(SECTION))[0] is None:
        allee = _allee_du_moteur()
        suppose.append({
            'code': 'allee_par_defaut',
            'libelle': "allée technique de %s m (valeur du moteur : rien "
                       "n'est réglé)" % ('%.2f' % allee).replace('.', ','),
            'valeur': allee, 'champ': CHAMP_ALLEE})
    return suppose
