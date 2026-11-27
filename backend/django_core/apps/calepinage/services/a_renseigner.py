"""ACAL699 — ``cascade.a_renseigner`` : ce qu'il faut renseigner, et où LIRE.

``chaine_pertes.completude_de_la_chaine`` sait quelles omissions sont des
pertes « non renseignées » mais n'en publiait que le nombre. Ce module publie,
pour chacune, le champ qui manque (lu dans le motif posé par
``etapes.etape_omise`` : « Champ manquant : « … ». »), son libellé et une
phrase « où lire la valeur » SANS aucun chiffre : rien n'est proposé, la
société lit sa valeur à la source que le registre cite.

Un champ de site, de série, de plan ou d'ombrage n'est JAMAIS présenté comme
un réglage : il part dans ``non_localisables`` avec son motif.

Ce module porte aussi les textes de complétude (``textes_de_completude``)
extraits de ``completude_de_la_chaine`` pour que ``chaine_pertes.py`` ne
grossisse pas ; ses constantes de texte restent dans ``chaine_pertes.py``.
"""
from __future__ import annotations

import re

#: LE motif posé par ``etapes.etape_omise`` (même texte, test d'aller-retour
#: ``test_acal_completude_simulation.py::ARenseignerTest``).
FORMAT_CHAMP_MANQUANT = ' Champ manquant : « {champ} ».'
_MOTIF_CHAMP = re.compile(
    re.escape(FORMAT_CHAMP_MANQUANT.strip()).replace(
        re.escape('{champ}'), r'(?P<champ>.+)'))

#: Les préfixes de champ qui sont des RÉGLAGES société → section du registre
#: (``reglages_simulation.`` : nom du contexte employé par mismatch_fabricant).
SECTIONS_REGLAGE = {'simulation': 'simulation',
                    'reglages_simulation': 'simulation',
                    'electrique_societe': 'electrique_societe'}
#: ACAL1934 — la phrase posée par ``etapes.thermique`` quand la table société est
#: REMPLIE mais n'a pas de ligne pour la pose (« Table société : <phrase> »).
_MOTIF_TABLE = re.compile(r'Table société : (?P<phrase>.+?)(?: Champ manquant|$)')
PREFIXE_FICHE_PANNEAU = 'fiche_module'

OU_TROUVER_REGLAGE = ('Où lire la valeur : {reference}. Aucune valeur '
                      "n'est proposée ici.")
OU_TROUVER_FICHE = ('Fiche technique du panneau : champ « {champ} », à lire '
                    'sur la fiche du fabricant')
MOTIF_HORS_REGISTRE = ("« {champ} » n'est ni un réglage de la société ni un "
                       'champ de la fiche du panneau : il se corrige sur le '
                       'calepinage lui-même.')
MOTIF_SANS_CHAMP = "L'étape ne nomme aucun champ manquant."

__all__ = ['FORMAT_CHAMP_MANQUANT', 'construire', 'textes_de_completude']


def _champ_du_motif(motif):
    """Le champ nommé par le motif d'``etape_omise``, ou ``''``."""
    trouve = _MOTIF_CHAMP.search(motif or '')
    return trouve.group('champ').strip() if trouve else ''


#: ACAL1619 — « <clé> (réglages simulation) », la forme qu'une étape emploie
#: pour nommer un réglage société parmi plusieurs remèdes (« … ou … »).
_REGLAGE_SIMULATION_NOMME = re.compile(r'^(?P<cle>\w+) \(réglages simulation\)$')


def _ligne_du_champ(etape, champ):
    """La PREMIÈRE alternative (« A ou B ou C ») localisable : la ligne, sinon
    ``None`` (le champ part alors dans ``non_localisables``)."""
    for morceau in champ.split(' ou '):
        morceau = morceau.strip()
        nomme = _REGLAGE_SIMULATION_NOMME.match(morceau)
        ligne = _ligne(etape, 'simulation.' + nomme.group('cle')
                       if nomme else morceau)
        if ligne is not None:
            return ligne
    return None


def _ligne(etape, champ):
    from .parametres_cles import registre

    prefixe, _, reste = champ.partition('.')
    cle = reste.split(' ')[0]  # « lid_par_techno (ligne « … ») » → la clé
    section = SECTIONS_REGLAGE.get(prefixe, prefixe)
    base = {'etape': etape.get('etape'), 'libelle': etape.get('libelle')}
    if prefixe in SECTIONS_REGLAGE and cle in registre(section):
        libelle, unite, reference = registre(section)[cle]
        return dict(base, nature='reglage_societe', section=section, cle=cle,
                    libelle_champ=libelle, unite=unite,
                    ou_trouver=OU_TROUVER_REGLAGE.format(reference=reference),
                    cible={'onglet': 'reglages', 'champ': cle})
    if section == PREFIXE_FICHE_PANNEAU and cle:
        return dict(base, nature='fiche_panneau', section=section, cle=cle,
                    libelle_champ=cle, unite='',
                    ou_trouver=OU_TROUVER_FICHE.format(champ=cle),
                    cible={'onglet': 'fiches', 'champ': cle})
    return None


def construire(cascade, non_renseignees):
    """``{etapes_comptees, etapes_a_compter, lignes[], non_localisables[]}``."""
    etapes = (cascade or {}).get('etapes') or []
    noms = set(non_renseignees or ())
    lignes, ailleurs, vues = [], [], set()
    for etape in etapes:
        motif = etape.get('motif_omission')
        if not motif or etape.get('etape') not in noms:
            continue
        champ = _champ_du_motif(motif)
        if (etape.get('etape'), champ) in vues:
            continue
        vues.add((etape.get('etape'), champ))
        ligne = _ligne_du_champ(etape, champ) if champ else None
        table = _MOTIF_TABLE.search(motif)
        if (ligne is not None and table
                and ligne['nature'] == 'reglage_societe'):
            ligne['motif'] = table.group('phrase').strip()
        if ligne is not None:
            lignes.append(ligne)
            continue
        ailleurs.append({'etape': etape.get('etape'),
                         'libelle': etape.get('libelle'), 'champ': champ,
                         'motif': (MOTIF_HORS_REGISTRE.format(champ=champ)
                                   if champ else MOTIF_SANS_CHAMP)})
    comptees = sum(1 for etape in etapes if not etape.get('motif_omission'))
    return {'etapes_comptees': comptees,
            'etapes_a_compter': comptees + len(noms),
            'lignes': lignes, 'non_localisables': ailleurs}


def textes_de_completude(socle):
    """``{mention, motif, avertissement}`` de ``completude_de_la_chaine``.

    ACAL2037 — le N annonce la LONGUEUR du socle manquant servi avec la
    mention (une seule définition du compte) ; socle complet ⇒ mention vide
    (les pertes facultatives omises restent dans ``non_renseignees``)."""
    from .chaine_pertes import (
        AVERTISSEMENT_BORNE_HAUTE, MENTION_BORNE_HAUTE, MOTIF_SOCLE_MANQUANT)

    n = len(socle)
    mention = (MENTION_BORNE_HAUTE.format(
        n=n, pertes='perte' if n == 1 else 'pertes',
        s='' if n == 1 else 's') if n else '')
    motif = (MOTIF_SOCLE_MANQUANT.format(postes=', '.join(socle))
             if socle else '')
    avertissement = (AVERTISSEMENT_BORNE_HAUTE.format(
        mention=f'« {mention} »', postes=', '.join(socle)) if socle else '')
    return {'mention': mention, 'motif': motif,
            'avertissement': avertissement}
