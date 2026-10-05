# -*- coding: utf-8 -*-
"""AOF69 — rendu d'un support en ARC : cotes radiales et tangentielles, murets.

La résidence en aile courbe de la consultation FRDISI (planche 06I) est le cas
qui casse tous les moteurs de calepinage rectangulaires : un développé de
68,05 m sur un rayon extérieur de 274 m, découpé en trois segments par des
murets au ras, et des tables qui restent des RECTANGLES RIGIDES posés au repère
tangent — elles ne se déforment pas pour suivre la courbe, donc l'espace entre
deux tables voisines n'est pas le même au bord intérieur et au bord extérieur.

C'est là qu'est le piège, et il est géométrique, pas arithmétique : un
calepinage peut être prouvé sans recouvrement **dans le repère curviligne**
(s, y) et produire, une fois RENDU, deux polygones qui se chevauchent au bord
intérieur. Le contrôle de non-recouvrement est donc rejoué ici par un test des
axes séparateurs (SAT) sur les polygones **effectivement dessinés**, relus sur
la feuille — pas sur les intervalles qui ont servi à les calculer.

Repère : ``s`` = abscisse curviligne le long du bord EXTÉRIEUR ; ``y`` = écart
depuis le bord INTÉRIEUR. ``point(s, y)`` projette sur la feuille, arc centré et
symétrique (mêmes conventions que la planche 06I remise le 27/07/2026).

Les grandeurs de contrôle produites ici (recouvrement évité min/max, marges par
segment) sont GÉOMÉTRIQUES. Le consommateur qui souhaite les imprimer les
déclare dans ``DonneesPlanche.nombres`` — c'est ainsi qu'elles franchissent la
garde de provenance d'AOF66 sans jamais être retapées.
"""

import math
from dataclasses import dataclass

#: Marqueur posé sur chaque table dessinée : c'est par lui que le contrôle
#: SAT retrouve la géométrie RENDUE sur la feuille.
GID_TABLE = "calepinage:table-arc"

#: Marqueur des murets inter-segments.
GID_MURET = "calepinage:muret"

#: Finesse de discrétisation d'un arc tracé (le bord d'un développé de 68 m
#: sur un rayon de 274 m est visuellement lisse à 80 cordes).
CORDES_PAR_ARC = 80


class TablesEnRecouvrement(ValueError):
    """Deux tables DESSINÉES se recouvrent — le calepinage n'est pas posable."""


@dataclass(frozen=True)
class GeometrieArc:
    """L'arc relevé : rayon extérieur, largeur de bande, développé total."""

    rayon_exterieur: float
    largeur: float
    developpe: float

    def __post_init__(self):
        if self.rayon_exterieur <= 0:
            raise ValueError("rayon extérieur strictement positif attendu")
        if self.largeur <= 0:
            raise ValueError("largeur de bande strictement positive attendue")
        if self.developpe <= 0:
            raise ValueError("développé strictement positif attendu")
        if self.largeur >= self.rayon_exterieur:
            raise ValueError("la bande ne peut pas être plus large que le rayon")

    @property
    def rayon_interieur(self):
        return self.rayon_exterieur - self.largeur

    @property
    def angle_total(self):
        """Angle au centre sous-tendu par le développé extérieur, en radians."""
        return self.developpe / self.rayon_exterieur

    @property
    def _recentrage(self):
        return self.rayon_exterieur * math.cos(self.angle_total / 2.0)

    def phi(self, s):
        """Angle du point d'abscisse curviligne ``s``, arc centré sur l'axe."""
        return (s - self.developpe / 2.0) / self.rayon_exterieur

    def point(self, s, y):
        """``(s, y)`` -> coordonnées feuille, en mètres."""
        rayon = self.rayon_interieur + y
        angle = self.phi(s)
        return (rayon * math.sin(angle),
                rayon * math.cos(angle) - self._recentrage)

    def repere_tangent(self, s):
        """``(tangente, normale)`` au point d'abscisse ``s``."""
        angle = self.phi(s)
        return ((math.cos(angle), -math.sin(angle)),
                (math.sin(angle), math.cos(angle)))

    def polygone_rigide(self, s0, s1, y0, y1):
        """Un RECTANGLE rigide posé au repère tangent de son centre.

        C'est la vraie forme d'une table : elle ne se plie pas à la courbe.
        """
        centre_s, centre_y = (s0 + s1) / 2.0, (y0 + y1) / 2.0
        cx, cy = self.point(centre_s, centre_y)
        tangente, normale = self.repere_tangent(centre_s)
        demi_long, demi_large = (s1 - s0) / 2.0, (y1 - y0) / 2.0
        return tuple(
            (cx + a * demi_long * tangente[0] + b * demi_large * normale[0],
             cy + a * demi_long * tangente[1] + b * demi_large * normale[1])
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)))

    def points_d_arc(self, s0, s1, y, cordes=CORDES_PAR_ARC):
        """La polyligne d'un bord courbe à ordonnée ``y`` constante."""
        return tuple(self.point(s0 + (s1 - s0) * i / cordes, y)
                     for i in range(cordes + 1))


@dataclass(frozen=True)
class SegmentArc:
    """Un tronçon du développé, borné par deux murets (ou par les extrémités)."""

    nom: str
    debut: float
    fin: float

    @property
    def developpe(self):
        return self.fin - self.debut


@dataclass(frozen=True)
class TableArc:
    """Une table posée, en coordonnées curvilignes."""

    debut: float
    fin: float
    bas: float
    haut: float
    segment: str = ""

    @property
    def milieu(self):
        return (self.debut + self.fin) / 2.0


@dataclass(frozen=True)
class Muret:
    """Un muret inter-segments, matérialisé au ras du développé."""

    abscisse: float
    epaisseur: float
    libelle: str = ""


# ---------------------------------------------------------------------------
# Test des axes séparateurs (SAT) — sur des polygones convexes quelconques.
# ---------------------------------------------------------------------------
def _axes_normaux(polygone):
    axes = []
    nombre = len(polygone)
    for i in range(nombre):
        x0, y0 = polygone[i]
        x1, y1 = polygone[(i + 1) % nombre]
        dx, dy = x1 - x0, y1 - y0
        longueur = math.hypot(dx, dy)
        if longueur > 0:
            axes.append((-dy / longueur, dx / longueur))
    return tuple(axes)


def _projection(polygone, axe):
    valeurs = [x * axe[0] + y * axe[1] for x, y in polygone]
    return min(valeurs), max(valeurs)


def separation(polygone_a, polygone_b):
    """Distance séparant deux polygones convexes ; NÉGATIVE s'ils se recouvrent.

    C'est le SAT dans sa forme utile : le meilleur axe séparateur donne la
    distance réellement disponible entre deux tables — au bord intérieur d'un
    arc, c'est elle qui décide, pas l'intervalle curviligne.
    """
    meilleure = None
    for axe in _axes_normaux(polygone_a) + _axes_normaux(polygone_b):
        a_min, a_max = _projection(polygone_a, axe)
        b_min, b_max = _projection(polygone_b, axe)
        jeu = max(b_min - a_max, a_min - b_max)
        if meilleure is None or jeu > meilleure:
            meilleure = jeu
    return 0.0 if meilleure is None else meilleure


def se_recouvrent(polygone_a, polygone_b, tolerance=1e-9):
    return separation(polygone_a, polygone_b) < -tolerance


def verifier_non_recouvrement(polygones, tolerance=1e-9):
    """Refuse la première paire de polygones qui se recouvrent, en les citant."""
    for i in range(len(polygones)):
        for j in range(i + 1, len(polygones)):
            if se_recouvrent(polygones[i], polygones[j], tolerance):
                raise TablesEnRecouvrement(
                    "tables dessinées en recouvrement (rangs %d et %d, "
                    "pénétration %.4f m)"
                    % (i, j, -separation(polygones[i], polygones[j])))
    return True


def recouvrement_evite(polygones):
    """``(min, max)`` de la séparation entre tables voisines, en mètres.

    Sur un arc, deux tables voisines ne sont pas également espacées de leurs
    deux bords : imprimer le MINIMUM (au bord intérieur) et le MAXIMUM (au bord
    extérieur) dit au maître d'ouvrage ce qui a réellement été évité.
    """
    if len(polygones) < 2:
        return (None, None)
    separations = [separation(polygones[i], polygones[i + 1])
                   for i in range(len(polygones) - 1)]
    return (min(separations), max(separations))


def marges_par_segment(segments, tables):
    """``((nom, marge_debut, marge_fin), …)`` — le vide laissé à chaque bout.

    Un segment sans table est déclaré avec ses deux marges à son développé
    entier : le lire à zéro laisserait croire qu'il est rempli.
    """
    resultats = []
    for segment in segments:
        posees = [t for t in tables if t.segment == segment.nom]
        if not posees:
            resultats.append((segment.nom, segment.developpe, segment.developpe))
            continue
        premiere = min(t.debut for t in posees)
        derniere = max(t.fin for t in posees)
        resultats.append((segment.nom, premiere - segment.debut,
                          segment.fin - derniere))
    return tuple(resultats)


# ---------------------------------------------------------------------------
# Dessin
# ---------------------------------------------------------------------------
def dessiner_bandes(feuille, geometrie, couleur, epaisseur=2.0, zorder=10):
    """Les deux bords courbes du développé, du bord intérieur à l'extérieur."""
    for ordonnee in (0.0, geometrie.largeur):
        feuille.polyligne(geometrie.points_d_arc(0.0, geometrie.developpe,
                                                 ordonnee),
                          couleur, lw=epaisseur, zorder=zorder)


def dessiner_murets(feuille, geometrie, murets, couleur, remplissage,
                    zorder=13):
    """Matérialise les murets : un joint n'est pas une ligne, c'est un volume."""
    poses = []
    for muret in murets:
        demi = muret.epaisseur / 2.0
        polygone = geometrie.polygone_rigide(
            muret.abscisse - demi, muret.abscisse + demi, 0.0, geometrie.largeur)
        artiste = feuille.polygone(polygone, contour=couleur,
                                   remplissage=remplissage, lw=1.2,
                                   zorder=zorder, hachure="xx")
        artiste.set_gid(GID_MURET)
        poses.append(polygone)
    return tuple(poses)


def dessiner_tables(feuille, geometrie, tables, contour, remplissage,
                    faitage=True, zorder=5):
    """Pose les tables en polygones RIGIDES et retourne la géométrie dessinée."""
    polygones = []
    for table in tables:
        polygone = geometrie.polygone_rigide(table.debut, table.fin,
                                             table.bas, table.haut)
        artiste = feuille.polygone(polygone, contour=contour,
                                   remplissage=remplissage, lw=0.35,
                                   zorder=zorder)
        artiste.set_gid(GID_TABLE)
        if faitage:
            milieu = (table.bas + table.haut) / 2.0
            feuille.ligne(geometrie.point(table.debut, milieu),
                          geometrie.point(table.fin, milieu), contour, lw=0.5,
                          zorder=zorder + 1)
        polygones.append(polygone)
    return tuple(polygones)


def tables_dessinees(feuille):
    """Relit sur la FEUILLE les polygones des tables réellement posées."""
    trouves = []
    for artiste in feuille.axe.patches:
        if artiste.get_gid() == GID_TABLE:
            sommets = artiste.get_xy()
            points = [tuple(point) for point in sommets]
            if len(points) > 1 and points[0] == points[-1]:
                points = points[:-1]
            trouves.append(tuple(points))
    return tuple(trouves)


def verifier_tables_dessinees(feuille, tolerance=1e-9):
    """Rejoue le SAT sur la géométrie RENDUE, pas sur celle qui l'a produite.

    C'est le contrôle exigé par la tâche : un calepinage peut être prouvé
    disjoint en coordonnées curvilignes et se recouvrir une fois posé en
    rectangles rigides sur la courbe.
    """
    return verifier_non_recouvrement(tables_dessinees(feuille), tolerance)


# ---------------------------------------------------------------------------
# Cotes radiales et tangentielles
# ---------------------------------------------------------------------------
def rdim(feuille, geometrie, s, bas, haut, couleur, contenu=None, off=0.0,
         taille=6.2, cadre=True):
    """Cote RADIALE : à abscisse constante, du bord intérieur vers l'extérieur."""
    return feuille.cote(geometrie.point(s, bas), geometrie.point(s, haut),
                        couleur, off=off, contenu=contenu, taille=taille,
                        cadre=cadre)


def tdim(feuille, geometrie, debut, fin, y, couleur, contenu=None, off=0.0,
         taille=6.2, cadre=True):
    """Cote TANGENTIELLE : à ordonnée constante, le long du développé.

    La corde tracée est plus COURTE que le développé qu'elle cote : laisser la
    cote se libeller toute seule ferait imprimer la corde à la place de l'arc.
    Le texte est donc obligatoire et vient de la donnée.
    """
    if contenu is None:
        raise ValueError(
            "une cote tangentielle doit porter le développé relevé : la corde "
            "tracée est plus courte que l'arc qu'elle cote")
    return feuille.cote(geometrie.point(debut, y), geometrie.point(fin, y),
                        couleur, off=off, contenu=contenu, taille=taille,
                        cadre=cadre)
