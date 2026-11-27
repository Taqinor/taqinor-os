"""ACAL940 — TOUT ce qui manque à une simulation, collecté SANS lever.

``verifier_simulable`` (``services/simulation.py``) s'arrêtait au premier
manque : trois réglages vides coûtaient trois allers-retours (T1-F1-017). Ce
module rejoue les MÊMES contrôles, dans le MÊME ordre (mode météo, fenêtre
d'années, pan équipé, épingle, transposition de l'année type), et rend une ligne par
manque ``{champ, motif, cible}`` ; ``cible`` mène au champ du réglage société
(``{onglet: 'reglages', champ: 'calx69-<clé>'}``, forme ``cible`` d'ACAL386),
``None`` pour un manque qui n'est pas un réglage. Les motifs sont ceux des
refus existants, mot pour mot : aucun texte recopié.
"""
from __future__ import annotations

from . import chaine_pertes as _cp

__all__ = ['manquants_de_simulation']

#: Le préfixe des clés de réglage société (``parametres.simulation.<clé>``).
_PREFIXE_REGLAGE = 'parametres.simulation.'


#: ACAL1715 — l'année type à transposer : le réglage manquant, en mots (ACAL1649).
_MOTIFS_TRANSPOSITION = {
    _PREFIXE_REGLAGE + 'modele_transposition': (
        "Choisissez le modèle de transposition : l'année type ne donne que "
        "l'ensoleillement horizontal, à reporter sur le plan des panneaux."),
    _PREFIXE_REGLAGE + 'albedo_mensuel': (
        "Saisissez l'albédo du sol, avec sa source : il entre dans le report de "
        "l'année type sur le plan des panneaux."),
}


def _ligne(champ, motif):
    cible = None
    if champ.startswith(_PREFIXE_REGLAGE):
        cible = {'onglet': 'reglages',
                 'champ': 'calx69-' + champ[len(_PREFIXE_REGLAGE):]}
    return {'champ': champ, 'motif': motif, 'cible': cible}


MOTIF_MODE_METEO_ABSENT = "Choisissez le mode météo : année type ou plusieurs années."
MOTIF_MODE_METEO_INCONNU = (
    "Le mode météo choisi n'est pas reconnu : choisissez année type ou plusieurs années.")


def motif_mode_meteo_du_refus(refus):
    """Fonction pure (revue ACAL1629) : la phrase de métier d'un refus du champ
    ``mode_meteo``, tirée de la RAISON du refus (mode non choisi, ou non reconnu)."""
    if "n'est pas choisi" in (refus.motif or '').replace('’', "'"):
        return MOTIF_MODE_METEO_ABSENT
    return MOTIF_MODE_METEO_INCONNU


def _motif_meteo(refus, contexte):
    """ACAL1649 — le refus d'un réglage météo en mots de métier, sans clé ni valeur
    d'énumération (``champ`` garde le chemin pour le lien) ; un autre champ : motif tel quel."""
    saisi = _cp._etapes.reglage(contexte, refus.champ.rsplit('.', 1)[-1])
    if refus.champ == _cp.CLE_REGLAGE_MODE_METEO:
        if saisi is None:
            return MOTIF_MODE_METEO_ABSENT
        return MOTIF_MODE_METEO_INCONNU
    if refus.champ == _cp.CLE_REGLAGE_FENETRE_ANNEES:
        if saisi is None:
            return ("Choisissez la fenêtre d'années météo : toute la base disponible, dans la limite de %s ans."
                    % _cp.PLAFOND_FENETRE_ANNEES)
        return "La fenêtre d'années météo est illisible : saisissez deux années, par exemple 2015-2024."
    return refus.motif


def _manques_meteo(contexte):
    """Les lignes météo et le mode décidé (``None`` sans décision)."""
    try:
        return [], _cp.decision_meteo(contexte)['mode']
    except _cp.MeteoIndecise as refus:
        lignes = [_ligne(refus.champ, _motif_meteo(refus, contexte))]
    if lignes[0]['champ'] == _cp.CLE_REGLAGE_MODE_METEO:
        # Mode absent ou inconnu : la fenêtre, exigée par le seul mode qui
        # aboutit sans fichier (« pluriannuel »), est vérifiée aussi.
        try:
            _cp._fenetre_pluriannuelle(contexte)
        except _cp.MeteoIndecise as refus:
            lignes.append(_ligne(refus.champ, _motif_meteo(refus, contexte)))
    return lignes, None


def _cible_sans_module(contexte):
    """ACAL1639 — où agir quand aucun pan n'est équipé : l'étape « Toit » sans
    aucun pan, « Panneaux » quand un pan existe sans module, ``None`` sinon (des
    modules posés mais sans module PV désigné : l'onglet Matériel, côté écran)."""
    pans = (contexte or {}).get('plans_poses') or (contexte or {}).get('plans') or []
    if not pans:
        etape = 'toit'
    elif not any(pan.get('modules') for pan in pans):
        etape = 'panneaux'
    else:
        return None
    return {'etape': etape, 'onglet': '', 'champ': ''}


def manquants_de_simulation(contexte, meta, fichier_depose=False):
    """Les manques d'une simulation, dans l'ordre de ``verifier_simulable`` ;
    liste vide = simulable."""
    from . import simulation as _sim

    lignes, mode = _manques_meteo(contexte)
    if not (meta or {}).get('plans_equipes'):
        ligne = _ligne('plans', _sim.MOTIF_SANS_PAN_EQUIPE)
        ligne['cible'] = _cible_sans_module(contexte)
        lignes.append(ligne)
    if not fichier_depose:
        site = (contexte or {}).get('site') or {}
        if site.get('lat') is None or site.get('lon') is None:
            lignes.append(_ligne('site.pin', _sim.MOTIF_SANS_POINT))
        if mode == 'tmy':
            # ACAL1715 — l'année type se transpose : modèle et albédo saisis.
            from .transposition import refus_de_reglages
            for refus in refus_de_reglages(contexte):
                lignes.append(_ligne(refus.champ, _MOTIFS_TRANSPOSITION.get(refus.champ, str(refus))))
    return lignes
