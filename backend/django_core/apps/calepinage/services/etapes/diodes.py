"""ACAL722 — l'étape « diodes » : la dispersion d'ombrage affinée PAR BANDE.

CE QUE L'ÉTAPE FAIT
-------------------
``mismatch_ombrage`` mesure la dispersion I-V de chaque chaîne PAR MODULE (le
module entier est dérivé quand son accès passe sous le seuil de la société).
Un module à diodes de dérivation se comporte pourtant par SOUS-CHAÎNES : seule
la bande ombrée est mise hors chaîne. Quand la fiche du module publie son
nombre de sous-chaînes (``FicheTechnique.sous_chaines_par_module``, ACAL720)
et que le document porte l'accès solaire PAR BANDE (``solarAccess.bandes``,
ACAL721 / ACAL731), cette étape refait le calcul avec la MÊME règle, bande par
bande : une bande sous le seuil de dérivation de la société est mise hors
chaîne, sinon elle impose son courant en série.

LA BORNE : le résultat d'une chaîne ne sort JAMAIS de l'intervalle de ses deux
bornes (celles de ``mismatch_ombrage``, ACAL711) — la perte AJOUTÉE par cette
étape est donc au plus l'écart des deux bornes.

AUCUN FORFAIT : sans nombre de sous-chaînes ou sans bandes, l'étape est omise
(``sans_donnees``) ; PV*SOL assume 0,5 % de pertes de diodes, chiffre de leur
logiciel que nous n'employons jamais.
"""
from __future__ import annotations

from apps.calepinage.services.etapes import fiche_du_module

from apps.calepinage.services import etapes
from apps.calepinage.services.ombrage_chaines import acces_par_bande
from apps.calepinage.services.production import (
    cle_de_module, cle_de_pan, numeros_des_modules,
)
from apps.calepinage.services.valeurs import nombre as _nombre

from .mismatch_ombrage import CLE_REGLAGE, mesurer_les_chaines

POSTE = 'diodes'

CHAMP_SOUS_CHAINES = 'sous_chaines_par_module'

MOTIF_SANS_DONNEES = (
    'Les diodes se calculent par sous-chaînes : il faut le nombre de '
    'sous-chaînes de la fiche du module et l\'accès solaire par bande du '
    'document. Aucun forfait n\'est appliqué à leur place.')

MOTIF_AUCUNE_CHAINE_AFFINEE = (
    'Aucune chaîne ne porte, sur TOUS ses modules, des bandes en nombre égal '
    'aux sous-chaînes de la fiche : rien n\'est affiné, et aucun chiffre '
    'n\'est supposé.')

RAISON_NON_AFFINEE = (
    'Un module de cette chaîne n\'a pas de bandes en nombre égal aux '
    'sous-chaînes de la fiche : la chaîne garde son calcul par module.')

REFERENCE = (
    'PV*SOL et PVsyst modélisent les diodes de dérivation par sous-chaînes. '
    'Règle : une bande sous le seuil de dérivation de la société est mise '
    'hors chaîne, sinon elle impose son courant en série ; le résultat est '
    'borné par les deux bornes de l\'étape « dispersion d\'ombrage ».')

__all__ = ['POSTE', 'MOTIF_SANS_DONNEES', 'MOTIF_AUCUNE_CHAINE_AFFINEE',
           'REFERENCE', 'appliquer', 'sans_donnees']


def _sous_chaines(contexte):
    """Le nombre de sous-chaînes de la FICHE du module, ou ``None``."""
    fiche = fiche_du_module(contexte)
    brut = fiche.get(CHAMP_SOUS_CHAINES) if isinstance(fiche, dict) else None
    lu = _nombre(brut)
    return int(lu) if lu is not None and lu >= 1 and lu == int(lu) else None


def _bandes_par_module(layout):
    """``{'<pan>#<n>': [accès de bande, …]}`` — les bandes lues dans le
    document, rangées sous la MÊME clé que l'affectation (ACAL265)."""
    par_pan = acces_par_bande(layout)
    zones = layout.get('zones') if isinstance(layout, dict) else None
    sortie = {}
    for rang_zone, zone in enumerate(zones or (), start=1):
        if not isinstance(zone, dict):
            continue
        lues = (par_pan.get(str(zone.get('id')))
                or par_pan.get(str(zone.get('label'))))
        cle = cle_de_pan(zone, rang_zone)
        numeros = numeros_des_modules(zone.get('geometry'))
        for rang, bandes in enumerate(lues or (), start=1):
            if bandes is not None:
                sortie[cle_de_module(cle, rang, numeros)] = bandes
    return sortie


def _layout(contexte):
    ombrage = contexte.get('ombrage')
    layout = ombrage.get('layout') if isinstance(ombrage, dict) else None
    layout = layout or contexte.get('layout')
    return layout if isinstance(layout, dict) else None


def sans_donnees(contexte):
    """Vrai quand la fiche ne dit pas ses sous-chaînes ou que le document ne
    porte aucune bande : l'étape n'a rien à calculer et n'est PAS comptée
    comme une perte manquante."""
    contexte = contexte if isinstance(contexte, dict) else {}
    layout = _layout(contexte)
    return (_sous_chaines(contexte) is None or layout is None
            or not _bandes_par_module(layout))


def _pct(depart, arrivee, base):
    """``100 × (depart − arrivee) / base``, arrondi — ``None`` sans base."""
    return round(100.0 * (depart - arrivee) / base, 4) if base else None


def _affiner_chaine(mesure, bandes, n, seuil):
    """``(puissance affinée, chaîne publiée)`` — ou ``None`` si une bande manque.

    La règle est celle de ``mismatch_ombrage._mesurer_chaine``, bande par
    bande : les bandes sous le seuil sortent de la chaîne, sinon le courant
    série est celui de la plus faible. L'énergie est ramenée à la perte
    linéaire de la chaîne, puis BORNÉE entre ses deux bornes.
    """
    toutes = []
    for module in mesure['modules']:
        if module['acces'] is None:
            continue
        lues = bandes.get(str(module['module']))
        if lues is None or len(lues) != n:
            return None
        toutes.extend(lues)
    lineaire_b = sum(toutes) / n
    if lineaire_b <= 0:
        return None
    serie_b = len(toutes) * min(toutes) / n
    derivation_b = max(sum(b for b in toutes if b >= seuil) / n, serie_b)
    brute = mesure['lineaire'] * derivation_b / lineaire_b
    affinee = min(max(brute, mesure['courant_serie']), mesure['derivation'])
    lineaire = mesure['lineaire']
    return affinee, {
        'chaine': mesure['chaine'], 'pan': mesure['pan'],
        'excedent_par_bande_pct': _pct(lineaire_b, derivation_b, lineaire_b),
        'excedent_borne_pct': _pct(lineaire, affinee, lineaire),
        'borne_basse_pct': _pct(lineaire, mesure['derivation'], lineaire),
        'borne_haute_pct': _pct(lineaire, mesure['courant_serie'], lineaire),
        'bornee': abs(affinee - brute) > 1e-12,
    }


def appliquer(serie, contexte):
    """``(serie, etape)`` — la perte de diodes par sous-chaînes, ou son silence.

    Fonction PURE : ni ``serie`` ni ses points ne sont modifiés sur place.
    """
    from apps.calepinage.services.chaine_pertes import LIBELLES

    contexte = contexte if isinstance(contexte, dict) else {}
    libelle = LIBELLES[POSTE]
    if sans_donnees(contexte):
        return serie, etapes.etape_omise(libelle, MOTIF_SANS_DONNEES)
    mesure = mesurer_les_chaines(contexte)
    if 'omission' in mesure:
        motif, champ = mesure['omission']
        return serie, etapes.etape_omise(
            libelle, "L'étape « dispersion d'ombrage » est omise, les diodes "
            'qui la raffinent le sont aussi : ' + motif, champ=champ)

    n = _sous_chaines(contexte)
    bandes = _bandes_par_module(_layout(contexte))
    seuil = mesure['valeur_seuil']
    affinees, ignorees = [], []
    base = affine = 0.0
    for chaine in mesure['mesures']:
        rendu = (None if chaine['sans_contrainte']
                 else _affiner_chaine(chaine, bandes, n, seuil))
        base += chaine['derivation']
        if rendu is None:
            ignorees.append({'chaine': chaine['chaine'], 'pan': chaine['pan'],
                             'raison': RAISON_NON_AFFINEE})
            affine += chaine['derivation']
            continue
        affine += rendu[0]
        affinees.append(rendu[1])
    if not affinees:
        return serie, etapes.etape_omise(
            libelle, MOTIF_AUCUNE_CHAINE_AFFINEE, champ='solarAccess.bandes')

    lineaire = sum(chaine['lineaire'] for chaine in mesure['mesures'])
    haute = sum(chaine['courant_serie'] for chaine in mesure['mesures'])
    facteur = affine / base if base > 0 else 1.0
    entree = {
        'granularite': 'bande',
        'sous_chaines_par_module': n,
        'seuil_acces_derivation': {
            'valeur': seuil, 'cle': CLE_REGLAGE,
            'source': mesure['seuil'].get('source'),
            'reference': mesure['seuil'].get('reference')},
        'excedent_par_bande_pct': _pct(lineaire, affine, lineaire),
        'bornes': {
            'basse': {'excedent_pct': _pct(lineaire, base, lineaire)},
            'haute': {'excedent_pct': _pct(lineaire, haute, lineaire)},
        },
        'facteur_applique': round(facteur, 6),
        'pan': mesure['repere'],
        'chaines': affinees,
        'chaines_non_affinees': ignorees,
    }
    return etapes.mettre_a_l_echelle(serie, facteur), etapes.etape_appliquee(
        libelle, source='fiche', reference=REFERENCE, entree=entree)
