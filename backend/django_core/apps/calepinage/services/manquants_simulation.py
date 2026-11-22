"""ACAL940 — TOUT ce qui manque à une simulation, collecté SANS lever.

``verifier_simulable`` (``services/simulation.py``) s'arrêtait au premier
manque : trois réglages vides coûtaient trois allers-retours (T1-F1-017). Ce
module rejoue les MÊMES contrôles, dans le MÊME ordre (mode météo, fenêtre
d'années, pan équipé, épingle, année type sans fichier), et rend une ligne par
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


def _ligne(champ, motif):
    cible = None
    if champ.startswith(_PREFIXE_REGLAGE):
        cible = {'onglet': 'reglages',
                 'champ': 'calx69-' + champ[len(_PREFIXE_REGLAGE):]}
    return {'champ': champ, 'motif': motif, 'cible': cible}


def _manques_meteo(contexte):
    """Les lignes météo et le mode décidé (``None`` sans décision)."""
    try:
        return [], _cp.decision_meteo(contexte)['mode']
    except _cp.MeteoIndecise as refus:
        lignes = [_ligne(refus.champ, refus.motif)]
    if lignes[0]['champ'] == _cp.CLE_REGLAGE_MODE_METEO:
        # Mode absent ou inconnu : la fenêtre, exigée par le seul mode qui
        # aboutit sans fichier (« pluriannuel »), est vérifiée aussi.
        try:
            _cp._fenetre_pluriannuelle(contexte)
        except _cp.MeteoIndecise as refus:
            lignes.append(_ligne(refus.champ, refus.motif))
    return lignes, None


def manquants_de_simulation(contexte, meta, fichier_depose=False):
    """Les manques d'une simulation, dans l'ordre de ``verifier_simulable`` ;
    liste vide = simulable."""
    from . import simulation as _sim

    lignes, mode = _manques_meteo(contexte)
    if not (meta or {}).get('plans_equipes'):
        lignes.append(_ligne('plans', _sim.MOTIF_SANS_PAN_EQUIPE))
    if not fichier_depose:
        site = (contexte or {}).get('site') or {}
        if site.get('lat') is None or site.get('lon') is None:
            lignes.append(_ligne('site.pin', _sim.MOTIF_SANS_POINT))
        if mode == 'tmy':
            lignes.append(_ligne(_cp.CLE_REGLAGE_MODE_METEO, _cp.MOTIF_TMY_HORIZONTAL))
    return lignes
