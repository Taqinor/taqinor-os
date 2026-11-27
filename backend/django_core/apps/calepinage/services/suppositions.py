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

from core.calepinage.types import Parametres

from .degagements import SECTION, allee_technique

__all__ = ['liste_des_suppositions', 'reference_de_longueur', 'repli_longueur_dossier']

CHAMP_FICHES = 'fiche technique du module et de l\'onduleur'
CHAMP_ALLEE = ("panneau Allées de l'atelier (largeur de l'allée technique)")
# ACAL1630 (revue) — OÙ renseigner chaque champ : la même forme que `a_renseigner.lignes[].cible` (lue par
# `lienManque`) ; les allées ont leur propre écran des réglages de la société.
CIBLE_FICHES = {'onglet': 'fiches'}
CIBLE_ALLEE = {'onglet': 'reglages', 'champ': 'allees'}


def reference_de_longueur(calepinage):
    """ACAL2014 — la longueur de chaîne de RÉFÉRENCE : pour un dossier d'appel
    d'offres, la longueur de son cahier des charges (``core.calepinage.electrique.
    MODULES_PAR_CHAINE``, lue sur ce chemin SEUL) ; sinon celle de la conception
    courante (``equipements.materiel_de_la_conception``), ou ``None``."""
    if getattr(calepinage, 'appel_offre_id', None):
        from core.calepinage.electrique import MODULES_PAR_CHAINE
        return MODULES_PAR_CHAINE
    from .equipements import materiel_de_la_conception
    return materiel_de_la_conception(calepinage).get('longueur')


def repli_longueur_dossier(dossier, origine):
    """La longueur de chaîne retenue quand les fiches ne permettent pas de
    calculer la fenêtre de tension (``longueur_chaine``, CAL170) : la longueur
    de référence (``reference_de_longueur``), ou ``None`` quand il n'y en a pas
    (ACAL2014 : jamais la constante d'appel d'offres pour un lead)."""
    detail = ("longueur de dossier (%d modules par chaîne) : les fiches ne permettent "
              "pas de calculer la fenêtre de tension — repli assumé, "
              "jamais présenté comme un calcul" % dossier if dossier else
              "longueur de chaîne non calculée : les fiches ne permettent pas de calculer "
              "la fenêtre de tension — renseigner la fiche du module et de l'onduleur")
    return {
        'longueur': dossier or None,
        'origine': origine,
        'detail': detail,
        'longueur_dossier': dossier or None,
        'ecart': None,
        'hors_tolerance': False,
        'par_pan': {},
    }


def _allee_du_moteur():
    """L'allée par défaut du moteur, lue sur le champ de ``Parametres``."""
    champs = {champ.name: champ for champ in dataclasses.fields(Parametres)}
    return champs['allee_m'].default


def _libelle_longueur(valeur, manquantes):
    """ACAL1648 — la ligne en mots de métier : ce qui manque (l'onduleur, ou la fiche
    du module), puis la longueur par défaut « à confirmer » ; ``manquantes`` =
    ``Conception.manquantes`` (préfixes « module : » / « onduleur : »)."""
    module = any(str(m).startswith('module') for m in manquantes or ())
    onduleur = any(str(m).startswith('onduleur') for m in manquantes or ())
    if not (module or onduleur):
        return None
    action = ("Complétez la fiche du module" if module else "Choisissez l'onduleur")
    defaut = " (%d modules par défaut, à confirmer)" % valeur if valeur else ''
    return "%s pour vérifier la longueur des chaînes%s" % (action, defaut)


def liste_des_suppositions(longueur, societe, origine_dossier, manquantes=()):
    """``[{code, libelle, valeur, champ, cible}]`` — un repli caché par entrée.

    ``manquantes`` : ce que la conception dit manquer (ACAL1648).
    ``longueur`` : le dictionnaire ``longueur_chaine`` ; ``societe`` : les
    réglages société ; ``origine_dossier`` : l'origine qui marque le repli.
    """
    suppose = []
    if (longueur or {}).get('origine') == origine_dossier:
        valeur = (longueur or {}).get('longueur')  # ACAL2014 — la longueur retenue, jamais la constante
        suppose.append({
            'code': 'longueur_chaine_dossier',
            'libelle': _libelle_longueur(valeur, manquantes) or (
                        "%d modules par chaîne (longueur retenue au dossier : fiche du module ou de "
                        "l'onduleur incomplète)" % valeur if valeur else
                        "longueur de chaîne non calculée (fiche du module ou de l'onduleur incomplète)"),
            'valeur': valeur, 'champ': CHAMP_FICHES,
            'cible': dict(CIBLE_FICHES)})
    if allee_technique((societe or {}).get(SECTION))[0] is None:
        allee = _allee_du_moteur()
        suppose.append({
            'code': 'allee_par_defaut',
            'libelle': "allée technique de %s m (valeur du moteur : rien "
                       "n'est réglé)" % ('%.2f' % allee).replace('.', ','),
            'valeur': allee, 'champ': CHAMP_ALLEE,
            'cible': dict(CIBLE_ALLEE)})
    return suppose
