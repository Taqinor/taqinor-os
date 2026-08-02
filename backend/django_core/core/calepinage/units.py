# -*- coding: utf-8 -*-
"""AOF34 — unités, tolérances NOMMÉES PAR USAGE et formatage français.

Pourquoi un module dédié : les scripts d'origine disséminaient des ``1e-9`` et
des ``1e-6`` littéraux dans le comptage, la pose et les garde-fous. Le poste de
travail est Windows, la CI et la production sont Linux : un ``int((b - a) // p)``
qui bascule d'une unité DÉPLACE un module et change un chiffre remis à un maître
d'ouvrage. Chaque tolérance porte donc ici un NOM qui dit à quoi elle sert, et
aucun module du moteur ne réécrit un littéral.

Toutes les longueurs du moteur sont en MÈTRES. Le millimètre est l'unité de
comparaison canonique (``arrondi_mm``) : c'est sur des longueurs arrondies au mm
que ``serialisation.hash_entree`` travaille — jamais sur des floats bruts.
"""

import math

# --------------------------------------------------------------------- unités
#: 1 mm exprimé en mètres — l'unité de comparaison canonique du moteur.
MM = 0.001
#: 1 cm exprimé en mètres (les marges de robustesse se publient en cm).
CM = 0.01

# ----------------------------------------------------------------- tolérances
#: Tolérance de COMPTAGE : marge ajoutée avant la division entière qui compte
#: les modules d'un tronçon (``int((b - a + TOL_COMPTAGE_M) // pas)``). Elle
#: absorbe l'erreur d'accumulation d'une chaîne de sommes flottantes ; sans
#: elle, un tronçon de longueur EXACTEMENT k×pas peut rendre k-1.
TOL_COMPTAGE_M = 1e-9

#: Tolérance de COMPARAISON GÉOMÉTRIQUE : deux longueurs sont « la même » en
#: deçà. Sert aux contrôles de rive, d'allée et de largeur de rangée.
TOL_LONGUEUR_M = 1e-9

#: Tolérance de SÉPARATION des garde-fous : un contrôle de non-chevauchement ou
#: de dégagement tolère ce jeu. Volontairement PLUS LÂCHE que
#: ``TOL_LONGUEUR_M`` — un garde-fou qui refuse au picomètre serait rouge en CI
#: sans qu'aucune table ne bouge sur le chantier.
TOL_SEPARATION_M = 1e-6

#: Tolérance de FUSION d'intervalles bloqués : deux intervalles qui se touchent
#: à moins de ça n'en font qu'un.
TOL_FUSION_M = 1e-12

#: Tolérance de fermeture de chaîne de cotes PAR DÉFAUT. Le relevé FRDISI a
#: constaté 0,02 à 0,30 selon la chaîne : la tolérance est un attribut de la
#: CHAÎNE, celle-ci n'est qu'un défaut de dernier recours.
TOL_FERMETURE_DEFAUT_M = 0.30

#: Marge de tronçon minimale par défaut (reste de longueur après k tables) —
#: 2 cm constatés sur l'arc FRDISI.
MARGE_TRONCON_DEFAUT_M = 0.02
#: Marge de bande minimale par défaut (distance d'une bande au dégagement de
#: l'obstacle qu'elle esquive) — 4 cm constatés sur l'arc FRDISI.
MARGE_BANDE_DEFAUT_M = 0.04

#: Pas de recherche du DP exact (1 cm) et du balayage de phase historique (5 cm).
PAS_DP_DEFAUT_M = 0.01
PAS_PHASE_DEFAUT_M = 0.05


# ------------------------------------------------------------------ arrondis
def arrondi_mm(valeur):
    """Arrondit une longueur en mètres au MILLIMÈTRE le plus proche.

    C'est l'arrondi canonique du moteur : ``hash_entree`` ne voit que des
    longueurs passées par ici, donc un même relevé donne le même hash sur
    Windows et sur Linux. ``round`` du langage suit le « banker's rounding » ;
    on force ici l'arrondi mathématique (0,5 mm monte), stable et explicable à
    un maître d'ouvrage.
    """
    mm = valeur / MM
    return math.floor(mm + 0.5) * MM if mm >= 0 else -(math.floor(-mm + 0.5) * MM)


def en_mm(valeur):
    """Longueur en mètres -> ENTIER de millimètres (clé de hash, jamais un float)."""
    mm = valeur / MM
    return int(math.floor(mm + 0.5)) if mm >= 0 else -int(math.floor(-mm + 0.5))


def en_metres(millimetres):
    """Entier de millimètres -> longueur en mètres."""
    return millimetres * MM


def en_cm(valeur):
    """Longueur en mètres -> centimètres (float) — unité de publication des marges."""
    return valeur / CM


def proche(a, b, tolerance=TOL_LONGUEUR_M):
    """Égalité de longueurs à une tolérance NOMMÉE près."""
    return abs(a - b) <= tolerance


# ------------------------------------------------------------------ comptage
def nb_entier(longueur, pas):
    """Nombre de pas entiers tenant dans ``longueur``, tolérance de comptage incluse.

    C'est LE point de bascule du moteur : ``int((b - a) // pas)`` sans marge
    perd un module quand la longueur vaut exactement k×pas à 1e-15 près.
    """
    if pas <= 0:
        raise ValueError("le pas de pose doit être strictement positif")
    if longueur <= 0:
        return 0
    return int((longueur + TOL_COMPTAGE_M) // pas)


# ----------------------------------------------------------------- formatage
def fr(valeur, decimales=2):
    """Formatage FRANÇAIS d'un nombre : séparateur décimal virgule.

    Le moteur ne rend jamais de texte destiné au client, mais les MOTIFS de
    refus et les phrases de verdict sont générés (jamais rédigés en dur) et
    doivent être lisibles en français.
    """
    return ("%.*f" % (decimales, valeur)).replace(".", ",")


def fr_m(valeur, decimales=2):
    """« 4,70 m »."""
    return "%s m" % fr(valeur, decimales)


def fr_cm(valeur_m, decimales=1):
    """Longueur EN MÈTRES rendue « 4,2 cm » (les marges se publient en cm)."""
    return "%s cm" % fr(en_cm(valeur_m), decimales)
