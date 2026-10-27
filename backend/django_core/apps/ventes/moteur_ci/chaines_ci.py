"""CMP1/CMP2 — chaînes C&I conçues APPAREIL PAR APPAREIL (D-CMP-1).

Le calepinage (``core.electrique.chaines.concevoir_chaines``) impose des
chaînes ÉGALES sur tout un pan et laisse des modules « en réserve » ; sur un
champ C&I de 282 modules il rend 47 chaînes de 6 (123 A sur une entrée de
48 A). Ici, un onduleur reçoit TOUS ses modules : des chaînes de deux
longueurs voisines (``base`` et ``base + 1``), chacune dans la fenêtre de
tension publiée (``fenetre_admissible``, lecture seule), groupées par entrée
MPPT (une longueur par entrée, au plus ``chaînes par entrée`` chaînes, courant
Imp ≤ courant maxi publié de l'entrée). Aucune découpe partielle : sinon
BLOQUANT nommé.

PUR : ni Django, ni base, ni ``apps.*``. Déterministe.
"""
from __future__ import annotations

import math

from core.electrique.chaines import LONGUEUR_MAX_NON_BORNEE, fenetre_admissible
from core.electrique.types import TEMP_CHAUD_DEFAUT_C, TEMP_FROID_DEFAUT_C


def _chaines_par_entree(module, spec, chaines_max_par_mppt=None):
    """Chaînes raccordables par entrée MPPT, ou ``None`` (fiche illisible)."""
    try:
        imp, i_max = float(module.imp_a), float(spec.i_max_mppt_a)
    except (AttributeError, TypeError, ValueError):
        return None
    if chaines_max_par_mppt:
        spm = int(chaines_max_par_mppt)
    elif imp > 0 and i_max > 0:
        spm = max(1, int(math.floor(i_max / imp + 1e-9)))
    else:
        return None
    isc_max = getattr(spec, 'courant_isc_max_a', None)
    try:
        isc = float(module.isc_a)
        if isc_max and isc > 0:
            limite = int(math.floor(float(isc_max) / isc + 1e-9))
            spm = min(spm, max(1, limite))
    except (AttributeError, TypeError, ValueError):
        pass
    return max(1, spm)


def _fenetre(module, spec):
    """``(longueur_min, longueur_max, motif_trop_etroite)`` ou ``None`` quand
    aucune borne haute n'est vérifiable."""
    try:
        f = fenetre_admissible(module, spec, TEMP_FROID_DEFAUT_C,
                               TEMP_CHAUD_DEFAUT_C)
    except (AttributeError, TypeError, ValueError):
        return None
    if f.trop_etroite:
        return f.longueur_min, f.longueur_max, f.motif
    if f.longueur_max >= LONGUEUR_MAX_NON_BORNEE:
        return None
    return f.longueur_min, f.longueur_max, ''


def capacite_modules(module, spec, chaines_max_par_mppt=None):
    """Nombre maxi de modules qu'un appareil raccorde (entrées × chaînes par
    entrée × longueur maxi) ; ``None`` quand la fiche ne permet pas de le dire
    ou que la fenêtre est vide."""
    spm = _chaines_par_entree(module, spec, chaines_max_par_mppt)
    fen = _fenetre(module, spec)
    if spm is None or fen is None or fen[2]:
        return None
    try:
        return int(spec.n_mppt) * spm * fen[1]
    except (AttributeError, TypeError, ValueError):
        return None


def _decouper(n, spm, n_mppt, lmin, lmax):
    """Le moins de chaînes qui raccordent ``n`` modules : ``[(longueur,
    nb_chaines)]`` groupé par entrée, ou ``None``."""
    s = max(1, -(-n // lmax))
    while s * lmin <= n and s <= n_mppt * spm:
        base, extra = divmod(n, s)
        lots = [(base + 1, extra), (base, s - extra)]
        lots = [(lon, nb) for lon, nb in lots if nb]
        if base >= lmin and all(lon <= lmax for lon, _ in lots) \
                and sum(-(-nb // spm) for _, nb in lots) <= n_mppt:
            return lots
        s += 1
    return None


def concevoir_chaines_ci(module, spec, nb_modules, *, produit=None, nom='',
                         chaines_max_par_mppt=None):
    """Chaînes d'UN onduleur pour ``nb_modules`` modules : ``{produit,
    nb_modules, nb_chaines, bloquants, entrees:[{mppt, nb_chaines,
    longueur}]}`` — ``None`` si la fiche ne permet pas de concevoir (le
    parent dit « chaînes à vérifier »)."""
    spm = _chaines_par_entree(module, spec, chaines_max_par_mppt)
    fen = _fenetre(module, spec)
    sortie = {'produit': produit, 'nb_modules': nb_modules, 'nb_chaines': 0,
              'bloquants': [], 'entrees': []}
    if spm is None or fen is None:
        return None
    lmin, lmax, motif = fen
    if nb_modules <= 0:
        return sortie
    nom = nom or str(produit)
    if motif:
        sortie['bloquants'].append(motif)
        return sortie
    lots = _decouper(nb_modules, spm, int(spec.n_mppt), lmin, lmax)
    if lots is None:
        sortie['bloquants'].append(
            'aucune découpe ne raccorde les %d modules sur %s (%d entrées × '
            '%d chaîne(s), chaînes de %d à %d modules)'
            % (nb_modules, nom, int(spec.n_mppt), spm, lmin, lmax))
        return sortie
    mppt = 0
    for longueur, nb in lots:
        while nb > 0:
            mppt += 1
            pris = min(nb, spm)
            sortie['entrees'].append(
                {'mppt': mppt, 'nb_chaines': pris, 'longueur': longueur})
            nb -= pris
    sortie['nb_chaines'] = sum(e['nb_chaines'] for e in sortie['entrees'])
    return sortie
