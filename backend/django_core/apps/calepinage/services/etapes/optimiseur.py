"""ACAL723 — l'étape « optimiseur » : le rendement de la fiche, sur les SEULS
modules équipés.

Un optimiseur n'est pas gratuit : sa conversion perd ``100 − rendement`` % de
l'énergie des modules qu'il équipe (PVsyst compte cette perte dans les pertes
du champ). L'étape applique le rendement PUBLIÉ sur la fiche
(``FicheTechnique.opt_rendement_pct``) à la part d'énergie des modules équipés
— jamais au pan entier.

QUI EST ÉQUIPÉ (``_modules_equipes``) : une ligne d'affectation qui dit
``optimiseur: true`` l'est, ``optimiseur: false`` ne l'est pas ; sans drapeau,
elle l'est quand un produit optimiseur est déclaré pour tout le document.

LA PART D'ÉNERGIE : pondérée par l'accès solaire de chaque module quand le
document le porte pour TOUS les modules (un module ombré produit moins), sinon
par les effectifs. Aucun chiffre n'est supposé : sans produit déclaré l'étape
est omise (sans compter) ; sans rendement sur la fiche, omise en nommant le
champ (comptée).
"""
from __future__ import annotations

from apps.calepinage.services import etapes
from apps.calepinage.services.ombrage_chaines import acces_des_modules
from apps.calepinage.services.valeurs import nombre as _nombre

from .mismatch_ombrage import (
    MOTIF_SANS_AFFECTATION, _affectation, _layout, _optimiseur_du_document,
    _repere_du_pan,
)

POSTE = 'optimiseur'

CHAMP_RENDEMENT = 'FicheTechnique.opt_rendement_pct'

MOTIF_AUCUN_OPTIMISEUR = (
    "Aucun optimiseur n'est déclaré (ni produit pour le document, ni module "
    'marqué) : aucune perte de conversion à compter, et aucun 0 % supposé.')

MOTIF_RENDEMENT_ABSENT = (
    "Un optimiseur est déclaré mais sa fiche ne publie pas son rendement : "
    "la perte de conversion ne se calcule pas, aucune valeur n'est supposée.")

MOTIF_AUCUN_MODULE_EQUIPE = (
    "Un optimiseur est déclaré mais aucun module de ce pan n'en est équipé "
    '(chaque ligne dit « sans optimiseur »).')

REFERENCE = (
    "PVsyst compte la perte de rendement des optimiseurs dans les pertes du "
    "champ. Le rendement est celui de la fiche de l'optimiseur ; il ne "
    's\'applique qu\'à la part d\'énergie des modules équipés.')

__all__ = ['POSTE', 'MOTIF_AUCUN_OPTIMISEUR', 'REFERENCE', 'appliquer',
           'optimiseur_declare']


def _lignes_cablees(affectation):
    return [ligne for ligne in affectation if ligne.get('chaine') is not None]


def optimiseur_declare(contexte):
    """Un optimiseur est-il déclaré : produit du document, ou module marqué ?"""
    contexte = contexte if isinstance(contexte, dict) else {}
    return bool(_optimiseur_du_document(contexte)
                or any(ligne.get('optimiseur') is True
                       for ligne in _affectation(contexte)))


def _modules_equipes(contexte, affectation):
    """``{module: équipé ?}`` pour les modules câblés de ``affectation``.

    Le drapeau de la ligne prime ; sans drapeau, le produit déclaré pour tout
    le document équipe le module.
    """
    global_ = bool(_optimiseur_du_document(contexte))
    equipes = {}
    for ligne in _lignes_cablees(affectation):
        drapeau = ligne.get('optimiseur')
        equipes[str(ligne.get('module'))] = (
            drapeau if isinstance(drapeau, bool) else global_)
    return equipes


def _poids(equipes, layout):
    """``({module: poids}, pondération)`` — l'accès solaire quand il est lu
    pour TOUS les modules (et non nul au total), sinon les effectifs."""
    acces = acces_des_modules(layout) if layout else {}
    lus = {module: acces.get(module) for module in equipes}
    if lus and all(v is not None for v in lus.values()) and sum(lus.values()) > 0:
        return lus, 'accès solaire'
    return {module: 1.0 for module in equipes}, 'effectifs'


def appliquer(serie, contexte):
    """``(serie, etape)`` — la perte de conversion des optimiseurs, ou son
    silence. Fonction PURE : ``serie`` n'est pas modifiée sur place."""
    from apps.calepinage.services.chaine_pertes import LIBELLES

    contexte = contexte if isinstance(contexte, dict) else {}
    libelle = LIBELLES[POSTE]
    if not optimiseur_declare(contexte):
        return serie, etapes.etape_omise(libelle, MOTIF_AUCUN_OPTIMISEUR)
    fiche = contexte.get('fiche_optimiseur')
    rendement = _nombre(fiche.get('rendement_pct')) if isinstance(
        fiche, dict) else None
    if rendement is None or not 0 < rendement <= 100:
        return serie, etapes.etape_omise(libelle, MOTIF_RENDEMENT_ABSENT,
                                         champ=CHAMP_RENDEMENT)
    repere = _repere_du_pan(contexte)
    lignes = [ligne for ligne in _affectation(contexte)
              if repere is None or str(ligne.get('pan') or '') == repere]
    if not _lignes_cablees(lignes):
        return serie, etapes.etape_omise(libelle, MOTIF_SANS_AFFECTATION,
                                         champ='affectation')
    equipes = _modules_equipes(contexte, lignes)
    if not any(equipes.values()):
        return serie, etapes.etape_omise(libelle, MOTIF_AUCUN_MODULE_EQUIPE)

    poids, ponderation = _poids(equipes, _layout(contexte))
    part = (sum(p for m, p in poids.items() if equipes[m])
            / sum(poids.values()))
    perte = part * (100.0 - rendement)
    entree = {
        'modules_equipes': sum(1 for e in equipes.values() if e),
        'modules': len(equipes),
        'part_energie': round(part, 6),
        'ponderation': ponderation,
        'rendement_pct': rendement,
        'source_rendement': 'fiche',
        'perte_pct': round(perte, 4),
        'pan': repere,
    }
    return (etapes.mettre_a_l_echelle(serie, 1.0 - perte / 100.0),
            etapes.etape_appliquee(libelle, source='fiche',
                                   reference=REFERENCE, entree=entree))
