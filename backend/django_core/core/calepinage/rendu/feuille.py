# -*- coding: utf-8 -*-
"""AOF63 — ``Feuille`` : industrialisation de ``dessin.py``.

Port de ``new_sheet`` / ``dim`` / ``caisson`` / ``bloc`` / ``legende`` /
``scale_bar`` en un objet sans état global, sans chemin en dur et rendant des
OCTETS.

Trois choix structurants, chacun corrige un défaut MESURÉ des scripts d'origine :

1. **``Figure`` + ``FigureCanvasAgg`` explicites, jamais ``pyplot``.**
   ``pyplot`` tient un registre global de figures : ``plt.subplots()`` y inscrit
   la figure, et un script qui ne la ferme pas la fuite. Trois planches par
   dossier d'appel d'offres × un worker Celery de longue durée = une fuite
   linéaire. ``pyplot`` n'est de surcroît pas sûr entre fils d'exécution.
   Instancier ``Figure`` directement supprime les deux problèmes d'un coup :
   il n'y a plus de registre, donc plus rien à fuiter, et deux ``Feuille``
   n'ont aucun état commun. C'est aussi pour cela qu'il n'y a **aucun**
   ``matplotlib.use("Agg")`` ici : le backend n'est plus un réglage global, il
   est choisi par le canevas, planche par planche.
2. **Retour d'octets.** ``png()`` et ``pdf()`` écrivent dans un tampon mémoire.
   Le sous-paquet ne connaît aucun chemin, donc aucun chemin local ne peut se
   retrouver dans un livrable (voir ``rendu/metadata.py``).
3. **Aucune couleur codée ici.** Les primitives reçoivent leurs couleurs en
   argument : la palette a un propriétaire unique (``rendu/couleurs.py``).

Unités : le repère du dessin est en MÈTRES (comme les relevés) ; les formats de
feuille sont en pouces (matplotlib) ; les marges du cartouche sont en fraction
de figure.
"""

import math
from dataclasses import dataclass
from io import BytesIO

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.image import imread
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle


class FormatInconnu(ValueError):
    """Format de feuille demandé hors du catalogue."""


@dataclass(frozen=True)
class FormatFeuille:
    """Format normalisé, en POUCES (l'unité de ``figsize`` de matplotlib)."""

    nom: str
    largeur_pouces: float
    hauteur_pouces: float

    @property
    def figsize(self):
        return (self.largeur_pouces, self.hauteur_pouces)


#: Catalogue des formats. Un tuple (jamais une liste ni un dict au niveau
#: module) : le paquet interdit toute globale MUTABLE — reconfigurer le moteur
#: en mutant une globale est exactement ce qui rendait les scripts d'origine
#: non parallélisables.
FORMATS = (
    FormatFeuille("A3", 16.54, 11.69),
    FormatFeuille("A2", 23.39, 16.54),
    FormatFeuille("A1", 33.11, 23.39),
)

#: Format par défaut : A3 PAYSAGE, celui des trois planches remises.
FORMAT_DEFAUT = "A3"


def format_feuille(nom):
    """``"A3"`` -> ``FormatFeuille``. Lève ``FormatInconnu`` sinon."""
    for fmt in FORMATS:
        if fmt.nom == nom:
            return fmt
    raise FormatInconnu(
        "format de feuille inconnu : %r — formats connus : %s"
        % (nom, ", ".join(f.nom for f in FORMATS)))


@dataclass(frozen=True)
class GeometrieCote:
    """Le TRACÉ d'une cote, calculé sans matplotlib (donc testable seul).

    ``attaches`` : les deux lignes d'attache (chacune un couple de points).
    ``ligne`` : la ligne de cote à double flèche (couple de points).
    ``ancre_texte`` / ``angle_texte`` : position et orientation du texte.
    ``longueur`` : la longueur RÉELLE p1->p2, en mètres.
    """

    attaches: tuple
    ligne: tuple
    ancre_texte: tuple
    angle_texte: float
    longueur: float


def _vecteur_unitaire(p1, p2):
    """Vecteur unitaire p1->p2 et longueur. Longueur nulle -> 1,0 (comme l'original)."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    longueur = math.hypot(dx, dy) or 1.0
    return dx / longueur, dy / longueur, longueur


def geometrie_cote(p1, p2, off=0.8, gap=0.12, ext=0.18, text_off=0.22,
                   flip_text=False):
    """Géométrie EXACTE de ``dessin.dim`` (lignes d'attache + double flèche).

    ``off`` > 0 place la cote à GAUCHE du vecteur p1->p2 ; les lignes d'attache
    partent du point avec un jeu ``gap`` et dépassent la ligne de cote de
    ``ext``. Le texte est orienté le long de la cote, jamais tête en bas.
    """
    ux, uy, longueur = _vecteur_unitaire(p1, p2)
    nx, ny = -uy, ux                       # normale gauche
    q1 = (p1[0] + nx * off, p1[1] + ny * off)
    q2 = (p2[0] + nx * off, p2[1] + ny * off)
    sens = 1 if off >= 0 else -1
    attaches = tuple(
        ((p[0] + nx * gap * sens, p[1] + ny * gap * sens),
         (q[0] + nx * ext * sens, q[1] + ny * ext * sens))
        for p, q in ((p1, q1), (p2, q2)))
    milieu = ((q1[0] + q2[0]) / 2.0, (q1[1] + q2[1]) / 2.0)
    angle = math.degrees(math.atan2(uy, ux))
    if angle > 90 or angle <= -90:
        angle += 180
    decalage = text_off if not flip_text else -text_off - 0.1
    ancre = (milieu[0] + nx * decalage * sens, milieu[1] + ny * decalage * sens)
    return GeometrieCote(attaches=attaches, ligne=(q1, q2), ancre_texte=ancre,
                         angle_texte=angle, longueur=longueur)


def texte_de_longueur(longueur, decimales=2):
    """``10.87`` -> ``"10,87"`` — virgule décimale française."""
    return ("%%.%df" % decimales % longueur).replace(".", ",")


class Feuille:
    """Une planche : une ``Figure``, un axe en mètres, des primitives de dessin.

    S'utilise en gestionnaire de contexte — la figure est TOUJOURS fermée :

        with Feuille("TITRE", "sous-titre", (-5, 45), (-4, 58)) as f:
            octets = f.pdf()
    """

    def __init__(self, titre, sous_titre, xlim, ylim, format_nom=FORMAT_DEFAUT,
                 dpi=170, couleur_titre="black", couleur_sous_titre=None,
                 marge_titre=0.015, hauteur_titre=0.975,
                 hauteur_sous_titre=0.952):
        self._format = format_feuille(format_nom)
        self._dpi = float(dpi)
        self._figure = Figure(figsize=self._format.figsize, dpi=self._dpi)
        # Canevas Agg attaché explicitement : le backend est un choix LOCAL à
        # la feuille, jamais un réglage global du processus.
        self._canevas = FigureCanvasAgg(self._figure)
        self._axe = self._figure.subplots()
        self._axe.set_xlim(*xlim)
        self._axe.set_ylim(*ylim)
        self._axe.set_aspect("equal")
        self._axe.axis("off")
        self._titre = titre
        self._sous_titre = sous_titre
        if titre:
            self._figure.text(marge_titre, hauteur_titre, titre, fontsize=13,
                              fontweight="bold", va="top", color=couleur_titre)
        if sous_titre:
            self._figure.text(
                marge_titre, hauteur_sous_titre, sous_titre, fontsize=8.5,
                va="top",
                color=couleur_titre if couleur_sous_titre is None
                else couleur_sous_titre)

    # ------------------------------------------------------------ cycle de vie
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.fermer()
        return False

    def fermer(self):
        """Libère la figure. Idempotent.

        Sans ``pyplot`` il n'y a aucun registre global où la figure resterait
        accrochée : vider ses artistes et lâcher les références suffit, et le
        ramasse-miettes fait le reste. C'est précisément ce que les scripts
        d'origine ne faisaient pas.
        """
        if self._figure is not None:
            self._figure.clear()
        self._figure = None
        self._canevas = None
        self._axe = None

    def _exiger_ouverte(self):
        if self._figure is None:
            raise RuntimeError("feuille déjà fermée")
        return self._figure

    # ------------------------------------------------------------- accesseurs
    @property
    def figure(self):
        return self._exiger_ouverte()

    @property
    def axe(self):
        self._exiger_ouverte()
        return self._axe

    @property
    def format(self):
        return self._format

    @property
    def dpi(self):
        return self._dpi

    @property
    def titre(self):
        return self._titre

    @property
    def sous_titre(self):
        return self._sous_titre

    def rendu(self):
        """Le moteur de rendu Agg — nécessaire pour mesurer les textes."""
        self._exiger_ouverte()
        self._canevas.draw()
        return self._canevas.get_renderer()

    def artistes(self):
        """Tous les artistes de la figure ET de l'axe, à plat."""
        figure = self._exiger_ouverte()
        trouves = list(figure.artists) + list(figure.texts)
        for axe in figure.axes:
            trouves.extend(axe.patches)
            trouves.extend(axe.texts)
            trouves.extend(axe.lines)
        return tuple(trouves)

    # ------------------------------------------------------------- primitives
    def ligne(self, p1, p2, couleur, lw=1.0, zorder=10, style="-"):
        self.axe.plot([p1[0], p2[0]], [p1[1], p2[1]], color=couleur, lw=lw,
                      zorder=zorder, linestyle=style)

    def polyligne(self, points, couleur, lw=1.0, zorder=10, style="-"):
        points = tuple(points)
        if len(points) < 2:
            raise ValueError("une polyligne exige au moins deux points")
        self.axe.plot([p[0] for p in points], [p[1] for p in points],
                      color=couleur, lw=lw, zorder=zorder, linestyle=style)

    def rectangle(self, x, y, largeur, hauteur, contour, remplissage=None,
                  lw=1.0, zorder=10, hachure=None, style="-", angle=0.0):
        rect = Rectangle((x, y), largeur, hauteur,
                         facecolor="none" if remplissage is None else remplissage,
                         fill=remplissage is not None,
                         edgecolor=contour, lw=lw, hatch=hachure, angle=angle,
                         zorder=zorder)
        rect.set_linestyle(style)
        self.axe.add_patch(rect)
        return rect

    def polygone(self, points, contour, remplissage=None, lw=1.0, zorder=10,
                 hachure=None, style="-"):
        poly = Polygon(tuple(points), closed=True,
                       facecolor="none" if remplissage is None else remplissage,
                       fill=remplissage is not None,
                       edgecolor=contour, lw=lw, hatch=hachure, zorder=zorder)
        poly.set_linestyle(style)
        self.axe.add_patch(poly)
        return poly

    def texte(self, x, y, contenu, couleur, taille=7.0, ha="center",
              va="center", rotation=0.0, gras=False, zorder=20, cadre=False):
        options = dict(fontsize=taille, color=couleur, ha=ha, va=va,
                       rotation=rotation, rotation_mode="anchor",
                       zorder=zorder,
                       fontweight="bold" if gras else "normal")
        if cadre:
            options["bbox"] = dict(fc="white", ec="none", alpha=0.85, pad=0.5)
        return self.axe.text(x, y, contenu, **options)

    def texte_figure(self, x, y, contenu, couleur, taille=7.0, ha="left",
                     va="top", gras=False, zorder=51):
        return self.figure.text(x, y, contenu, fontsize=taille, color=couleur,
                                ha=ha, va=va, zorder=zorder,
                                fontweight="bold" if gras else "normal")

    def cadre_figure(self, x, y, largeur, hauteur, contour, remplissage="white",
                     lw=1.2, zorder=50):
        """Rectangle en coordonnées FIGURE (cartouche, encadrés de marge)."""
        figure = self._exiger_ouverte()
        rect = Rectangle((x, y), largeur, hauteur, transform=figure.transFigure,
                         facecolor=remplissage, edgecolor=contour, lw=lw,
                         zorder=zorder)
        figure.add_artist(rect)
        return rect

    def image_figure(self, octets_png, x, y, largeur, hauteur, zorder=52):
        """Pose une image (OCTETS PNG) en coordonnées FIGURE — logo de cartouche.

        L'image entre par des OCTETS, jamais par un chemin : c'est ce qui
        permet à une marque blanche de fournir son logo depuis la base sans
        qu'aucun chemin de poste de travail ne touche le rendu.
        """
        figure = self._exiger_ouverte()
        tableau = imread(BytesIO(bytes(octets_png)), format="png")
        axe = figure.add_axes((x, y, largeur, hauteur), zorder=zorder)
        axe.imshow(tableau, aspect="equal")
        axe.axis("off")
        axe.set_frame_on(False)
        return axe

    def fleche_double(self, p1, p2, couleur, lw=0.8, echelle=7, zorder=21):
        fleche = FancyArrowPatch(p1, p2, arrowstyle="<|-|>",
                                 mutation_scale=echelle, lw=lw, color=couleur,
                                 shrinkA=0, shrinkB=0, zorder=zorder)
        self.axe.add_patch(fleche)
        return fleche

    # ------------------------------------------------------------------ cotes
    def cote(self, p1, p2, couleur, off=0.8, contenu=None, taille=7.2,
             gap=0.12, ext=0.18, text_off=0.22, flip_text=False, cadre=False,
             echelle_fleche=7, zorder=20):
        """Cote linéaire — port fidèle de ``dessin.dim``.

        Retourne la ``GeometrieCote`` effectivement tracée : le test témoin
        compare ce tracé à un oracle indépendant, trait par trait.
        """
        geo = geometrie_cote(p1, p2, off=off, gap=gap, ext=ext,
                             text_off=text_off, flip_text=flip_text)
        for a, b in geo.attaches:
            self.ligne(a, b, couleur, lw=0.55, zorder=zorder)
        self.fleche_double(geo.ligne[0], geo.ligne[1], couleur, lw=0.8,
                           echelle=echelle_fleche, zorder=zorder + 1)
        libelle = texte_de_longueur(geo.longueur) if contenu is None else contenu
        self.texte(geo.ancre_texte[0], geo.ancre_texte[1], libelle, couleur,
                   taille=taille, rotation=geo.angle_texte, zorder=zorder + 2,
                   cadre=cadre)
        return geo

    # ------------------------------------------------------------- volumes bâtis
    def caisson(self, x, y, largeur, hauteur, contour, remplissage,
                etiquette=None, couleur_etiquette=None, incertain=False,
                taille=6.2, position_etiquette="above", angle=0.0,
                hachure="////", zorder=15):
        """Caisson béton : rectangle hachuré + étiquette (port de ``dessin.caisson``).

        ``incertain`` -> contour TIRETÉ : la donnée porte l'incertitude, le
        tracé ne fait que la refléter (voir ``rendu/couleurs.py``).
        """
        self.rectangle(x, y, largeur, hauteur, contour=contour,
                       remplissage=remplissage, lw=1.0, zorder=zorder,
                       hachure=hachure, style="--" if incertain else "-",
                       angle=angle)
        if etiquette:
            ex, ey, va = x + largeur / 2.0, y + hauteur + 0.15, "bottom"
            if position_etiquette == "below":
                ex, ey, va = x + largeur / 2.0, y - 0.15, "top"
            elif position_etiquette == "left":
                ex, ey, va = x - 0.15, y + hauteur / 2.0, "center"
            elif position_etiquette == "right":
                ex, ey, va = x + largeur + 0.15, y + hauteur / 2.0, "center"
            self.texte(ex, ey, etiquette,
                       couleur_etiquette if couleur_etiquette else contour,
                       taille=taille, va=va, gras=True, zorder=zorder + 1)

    def bloc(self, x, y, largeur, hauteur, contour, remplissage,
             etiquette=None, couleur_etiquette=None, taille=7.0, zorder=14):
        """Volume relevé plein (port de ``dessin.bloc``)."""
        self.rectangle(x, y, largeur, hauteur, contour=contour,
                       remplissage=remplissage, lw=1.6, zorder=zorder,
                       hachure="xx")
        if etiquette:
            self.texte(x + largeur / 2.0, y + hauteur / 2.0, etiquette,
                       couleur_etiquette if couleur_etiquette else contour,
                       taille=taille, gras=True, zorder=zorder + 2)

    # --------------------------------------------------------------- légende
    def legende(self, x, y, entrees, couleur_texte, taille=7.0, pas=0.62,
                zorder=30):
        """Légende : une entrée = ``(dessin_de_l_echantillon, libellé)``.

        ``dessin_de_l_echantillon`` est un appelable ``(feuille, x, y) -> None``
        : la ``Feuille`` ne connaît AUCUN vocabulaire métier, c'est l'appelant
        (``rendu/couleurs.py``) qui sait à quoi ressemble un statut de cote.
        """
        for indice, (echantillon, libelle) in enumerate(entrees):
            yy = y - indice * pas
            if echantillon is not None:
                echantillon(self, x, yy)
            self.texte(x + 1.1, yy, libelle, couleur_texte, taille=taille,
                       ha="left", va="center", zorder=zorder)

    # ---------------------------------------------------------- barre d'échelle
    def barre_echelle(self, x0, y0, couleur_trait, couleur_texte, total=10.0,
                      pas=2.0, hauteur=0.35, unite="mètres", taille=6.5,
                      couleur_pleine="black", couleur_vide="white", zorder=40):
        """Barre d'échelle GRAPHIQUE, alternée (port de ``dessin.scale_bar``).

        Jamais d'échelle numérique (« 1/200 ») : l'impression du dossier n'est
        pas garantie à l'échelle, seule une barre graphique reste vraie après
        une photocopie réduite.
        """
        if pas <= 0 or total <= 0:
            raise ValueError("barre d'échelle : total et pas doivent être positifs")
        segments = int(round(total / pas))
        for i in range(segments):
            self.rectangle(x0 + i * pas, y0, pas, hauteur,
                           contour=couleur_trait,
                           remplissage=couleur_pleine if i % 2 == 0 else couleur_vide,
                           lw=0.8, zorder=zorder)
        for i in range(segments + 1):
            self.texte(x0 + i * pas, y0 - 0.25, "%d" % int(round(i * pas)),
                       couleur_texte, taille=taille, ha="center", va="top",
                       zorder=zorder)
        self.texte(x0 + total / 2.0, y0 + hauteur + 0.15, unite, couleur_texte,
                   taille=taille, ha="center", va="bottom", zorder=zorder)

    # ------------------------------------------------------------------ sorties
    def _octets(self, format_sortie, dpi, bbox_serre, metadonnees):
        figure = self._exiger_ouverte()
        tampon = BytesIO()
        options = dict(format=format_sortie, dpi=dpi or self._dpi,
                       facecolor="white", edgecolor="white")
        if bbox_serre:
            options["bbox_inches"] = "tight"
        if metadonnees is not None:
            options["metadata"] = dict(metadonnees)
        # ``print_figure`` (et non ``savefig``) : l'API bas niveau du canevas.
        # Elle bascule seule sur le canevas du format demandé et ne passe par
        # aucun état global.
        FigureCanvasAgg(figure).print_figure(tampon, **options)
        return tampon.getvalue()

    def png(self, dpi=None, bbox_serre=True, metadonnees=None):
        """Rendu PNG — retourne des OCTETS, n'écrit aucun fichier."""
        return self._octets("png", dpi, bbox_serre, metadonnees)

    def pdf(self, bbox_serre=True, metadonnees=None):
        """Rendu PDF — retourne des OCTETS, n'écrit aucun fichier."""
        return self._octets("pdf", None, bbox_serre, metadonnees)
