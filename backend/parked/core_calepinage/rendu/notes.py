# -*- coding: utf-8 -*-
"""AOF68 — bloc de notes auto-replié et gardes de mise en page.

Un dossier d'appel d'offres se perd aussi sur la forme. Deux défauts silencieux
guettent une planche générée :

* **des notes tassées jusqu'à l'illisible.** Sur les scripts d'origine, la
  taille de police et l'interligne étaient saisis à la main : ajouter deux
  phrases faisait chevaucher le bloc et le cartouche, sans que rien ne
  proteste. Ici, la mise en page est CALCULÉE, et quand le texte ne tient plus
  dans la hauteur disponible au-dessus du cartouche à une taille encore
  lisible, le rendu ÉCHOUE avec ``notes illisibles : alléger le texte``. Un
  échec est réparable ; une planche illisible remise à un maître d'ouvrage ne
  l'est pas.
* **un élément hors cadre.** Une cote posée trop loin, un panneau trop haut :
  matplotlib rogne sans rien dire. ``verifier_dans_le_cadre`` mesure la boîte
  englobante de CHAQUE artiste de la figure et refuse le premier qui dépasse,
  en le nommant.

L'algorithme de mise en page est délibérément déterministe (essai des tailles
par pas décroissant, jamais de solveur) : deux rendus de la même donnée
produisent la même planche, ce qui est une exigence de traçabilité avant d'être
une commodité.
"""

import textwrap
from dataclasses import dataclass

#: Un point typographique vaut 1/72 de pouce.
POINTS_PAR_POUCE = 72.0

#: Interligne : hauteur de ligne rapportée à la taille de police.
FACTEUR_INTERLIGNE = 1.35

#: Largeur moyenne d'un glyphe, en cadratins (mesuré sur DejaVu Sans, la
#: police par défaut de matplotlib, sur du texte technique français).
LARGEUR_GLYPHE = 0.52

#: En dessous, un lecteur ne lit plus : il devine. C'est le seuil de refus.
TAILLE_MINIMALE = 5.0

#: Au-dessus, les notes concurrenceraient le corps de la planche.
TAILLE_MAXIMALE = 7.0

#: Pas d'essai des tailles — fin pour ne pas gaspiller de hauteur, fixe pour
#: que le rendu reste reproductible.
PAS_DE_TAILLE = 0.1

#: Le message exact que la tâche exige, mot pour mot.
MESSAGE_ILLISIBLE = "notes illisibles : alléger le texte"


class NotesIllisibles(ValueError):
    """Le texte ne tient pas dans la hauteur disponible à une taille lisible."""


class ElementHorsCadre(ValueError):
    """Un artiste de la figure déborde du cadre — rognage silencieux évité."""


@dataclass(frozen=True)
class MiseEnPageNotes:
    """Le résultat du calcul : ce qui sera écrit, et comment."""

    lignes: tuple
    taille: float
    interligne: float
    caracteres_par_ligne: int

    @property
    def hauteur(self):
        """Hauteur totale occupée, en fraction de figure."""
        return len(self.lignes) * self.interligne


def caracteres_par_ligne(largeur_colonne, largeur_pouces, taille):
    """Combien de caractères tiennent dans une colonne, à cette taille."""
    largeur_points = largeur_colonne * largeur_pouces * POINTS_PAR_POUCE
    return max(1, int(largeur_points / (taille * LARGEUR_GLYPHE)))


def replier(textes, caracteres):
    """Replie chaque note à la largeur de colonne. Une note vide = une respiration."""
    lignes = []
    for texte in textes:
        if not (texte or "").strip():
            lignes.append("")
            continue
        lignes.extend(textwrap.wrap(texte.strip(), width=caracteres) or [""])
    return tuple(lignes)


def calculer_mise_en_page(textes, largeur_colonne, hauteur_disponible,
                          largeur_pouces, hauteur_pouces,
                          taille_maximale=TAILLE_MAXIMALE,
                          taille_minimale=TAILLE_MINIMALE):
    """La plus grande taille lisible à laquelle le bloc tient. Sinon : refus.

    ``hauteur_disponible`` est la hauteur, en fraction de figure, entre le haut
    du bloc et le HAUT DU CARTOUCHE : le bloc s'arrête au-dessus de lui, il ne
    le chevauche jamais.
    """
    if hauteur_disponible <= 0:
        raise NotesIllisibles(MESSAGE_ILLISIBLE)
    taille = taille_maximale
    while taille >= taille_minimale - 1e-9:
        caracteres = caracteres_par_ligne(largeur_colonne, largeur_pouces,
                                          taille)
        lignes = replier(textes, caracteres)
        interligne = (taille * FACTEUR_INTERLIGNE
                      / POINTS_PAR_POUCE / hauteur_pouces)
        if len(lignes) * interligne <= hauteur_disponible + 1e-12:
            return MiseEnPageNotes(lignes=lignes, taille=round(taille, 2),
                                   interligne=interligne,
                                   caracteres_par_ligne=caracteres)
        taille -= PAS_DE_TAILLE
    raise NotesIllisibles(MESSAGE_ILLISIBLE)


def dessiner_notes(feuille, textes, couleur, x, haut, bas_reserve,
                   largeur_colonne, taille_maximale=TAILLE_MAXIMALE,
                   taille_minimale=TAILLE_MINIMALE, zorder=45):
    """Pose le bloc de notes en coordonnées FIGURE, entre ``haut`` et le cartouche.

    ``bas_reserve`` est l'ordonnée du HAUT du cartouche : la mise en page
    s'arrête au-dessus, quoi qu'il arrive.
    """
    mise_en_page = calculer_mise_en_page(
        textes, largeur_colonne, haut - bas_reserve,
        feuille.format.largeur_pouces, feuille.format.hauteur_pouces,
        taille_maximale=taille_maximale, taille_minimale=taille_minimale)
    for indice, ligne in enumerate(mise_en_page.lignes):
        if not ligne:
            continue
        feuille.texte_figure(x, haut - indice * mise_en_page.interligne, ligne,
                             couleur, taille=mise_en_page.taille, ha="left",
                             va="top", zorder=zorder)
    return mise_en_page


def _nom_de_l_artiste(artiste):
    contenu = getattr(artiste, "get_text", None)
    if contenu is not None:
        texte = contenu()
        if texte:
            return "texte « %s »" % (texte,)
    return type(artiste).__name__


def verifier_dans_le_cadre(feuille, tolerance_points=0.5):
    """Refuse le premier artiste qui déborde du cadre, en le NOMMANT.

    Sans cette garde, matplotlib rogne en silence : la planche part avec une
    cote coupée et personne ne s'en aperçoit avant le dépôt.
    """
    moteur = feuille.rendu()
    cadre = feuille.figure.bbox
    tolerance = tolerance_points / POINTS_PAR_POUCE * feuille.dpi
    debordements = []
    for artiste in feuille.artistes():
        if not artiste.get_visible():
            continue
        boite = artiste.get_window_extent(moteur)
        if boite.width <= 0 and boite.height <= 0:
            continue
        if (boite.x0 < cadre.x0 - tolerance or boite.y0 < cadre.y0 - tolerance
                or boite.x1 > cadre.x1 + tolerance
                or boite.y1 > cadre.y1 + tolerance):
            debordements.append(_nom_de_l_artiste(artiste))
    if debordements:
        raise ElementHorsCadre(
            "élément hors cadre : %s" % (" ; ".join(debordements),))
    return True
