# -*- coding: utf-8 -*-
"""AOF38 — le protocole ``Surface`` : la forme du toit disparaît du moteur.

REPÈRE UNIFIÉ DU MOTEUR (une seule convention pour tout le paquet, et c'est
celle du moteur historique ``calepinage.py``) :

* ``x`` — abscisse LE LONG de la rangée : c'est là que les tables se suivent.
  Sur l'arc, ``x`` est l'abscisse CURVILIGNE du bord extérieur (le ``s`` des
  scripts d'origine).
* ``y`` — coordonnée TRANSVERSALE : c'est là que les rangées se rangent, et
  c'est l'axe sur lequel le DP progresse. Sur l'arc, ``y`` est l'ordonnée
  depuis le bord INTÉRIEUR.

Les planches d'origine employaient les deux lettres dans les deux sens (la
planche de l'aile L nommait ``x`` la position de rangée, celle de l'arc la
nommait ``y``) : c'est précisément le genre de divergence que ce protocole
supprime. Les noms de méthodes sont ceux du contrat gelé par la tâche.

Une surface est IMMUABLE et ne fait aucune I/O. Elle ne compte rien et ne pose
rien : elle répond à des questions de géométrie.
"""

from dataclasses import dataclass, field
from typing import Tuple

from core.calepinage.types import Axe, Rives
from core.calepinage.units import TOL_LONGUEUR_M

__all__ = ["Coupure", "Surface", "CONFORMITE_METHODES"]

#: Les 6 méthodes que TOUTE surface doit exposer (suite de conformité).
CONFORMITE_METHODES = (
    "axe_progression", "bande", "longueur_utile", "pas_de_pose",
    "vers_feuille", "coupures",
)


@dataclass(frozen=True)
class Coupure:
    """Rupture que AUCUNE table ne peut enjamber (niveau, muret, joint).

    ``axe`` dit sur quelle coordonnée la coupure se lit : ``"x"`` (elle coupe
    la progression le long des rangées — c'est le cas du changement de niveau
    de l'école) ou ``"y"`` (elle sépare deux bandes transversales).
    """

    repere: str
    axe: str
    position: float
    epaisseur_m: float = 0.0

    def __post_init__(self):
        if self.axe not in ("x", "y"):
            raise ValueError("axe de coupure inconnu : %r" % (self.axe,))

    @property
    def debut(self):
        return self.position - self.epaisseur_m / 2.0

    @property
    def fin(self):
        return self.position + self.epaisseur_m / 2.0


@dataclass(frozen=True)
class Surface:
    """Base commune : géométrie déclarée + rives + niveau + orientation.

    Les sous-classes redéfinissent ``bande`` (et, pour l'arc, ``pas_de_pose``
    et ``vers_feuille``). Tout le reste est mutualisé ici — un contributeur qui
    ajoute une forme n'a qu'un seul point d'entrée à écrire.
    """

    repere: str
    rives: Rives = field(default_factory=Rives)
    axe_rangee: Axe = Axe.NORD_SUD
    niveau: int = 0
    pente_deg: float = 0.0
    azimut_deg: float = 180.0
    coupures_declarees: Tuple[Coupure, ...] = ()
    origine: Tuple[float, float] = (0.0, 0.0)

    # ------------------------------------------------------------- protocole
    def axe_progression(self):
        """Axe cardinal DE LA RANGÉE (les tables progressent dessus)."""
        return self.axe_rangee

    def bornes_transversales(self):
        """``(ymin, ymax)`` bruts de la surface — à redéfinir."""
        raise NotImplementedError

    def bande(self, y0, emprise=0.0):
        """Étendue ``(xmin, xmax)`` utilisable par une rangée ``[y0, y0+emprise]``.

        Rend ``None`` si la rangée ne tient pas dans la surface. C'est LA
        méthode qui porte la forme du toit : sur un polygone en L, une rangée
        qui reste à l'ouest de l'aile descend d'un seul tenant ; sur l'arc,
        l'étendue est une abscisse curviligne.
        """
        raise NotImplementedError

    def longueur_utile(self, y0, emprise=0.0):
        """Longueur d'une rangée APRÈS application des rives d'extrémité."""
        bornes = self.bande(y0, emprise)
        if bornes is None:
            return 0.0
        xmin, xmax = self.bornes_utiles(bornes)
        return max(0.0, xmax - xmin)

    def bornes_utiles(self, bornes):
        """Applique les rives d'EXTRÉMITÉ (+ joint) aux bornes d'une rangée."""
        retrait = self.rives.extremite_totale_m
        return (bornes[0] + retrait, bornes[1] - retrait)

    def bornes_transversales_utiles(self):
        """``(ymin, ymax)`` après rives LATÉRALES (+ acrotère)."""
        ymin, ymax = self.bornes_transversales()
        retrait = self.rives.laterale_totale_m
        return (ymin + retrait, ymax - retrait)

    def pas_de_pose(self, kit, y0):
        """Pas de pose LE LONG de la rangée pour une rangée à ``y0``.

        En géométrie plane c'est exactement l'emprise de la table. L'arc le
        redéfinit : deux tables jointives en abscisse développée se
        RECOUVRIRAIENT au rayon intérieur.
        """
        return kit.cote_le_long_rangee_m

    def vers_feuille(self, coord_locale):
        """``(x, y)`` local -> coordonnée de FEUILLE (dessin), sans I/O."""
        x, y = coord_locale
        return (self.origine[0] + x, self.origine[1] + y)

    def coupures(self):
        """Ruptures infranchissables — aucune table ne les enjambe."""
        return tuple(self.coupures_declarees)

    # ------------------------------------------------------------- communs
    def coupures_sur_x(self):
        return tuple(c for c in self.coupures() if c.axe == "x")

    def coupures_sur_y(self):
        return tuple(c for c in self.coupures() if c.axe == "y")

    def troncons_entre_coupures(self, bornes):
        """Découpe ``(xmin, xmax)`` aux coupures en ``x`` (murets, niveaux)."""
        xmin, xmax = bornes
        morceaux = []
        courant = xmin
        for c in sorted(self.coupures_sur_x(), key=lambda k: k.position):
            if c.fin <= courant or c.debut >= xmax:
                continue
            if c.debut > courant + TOL_LONGUEUR_M:
                morceaux.append((courant, min(c.debut, xmax)))
            courant = max(courant, c.fin)
        if courant < xmax - TOL_LONGUEUR_M:
            morceaux.append((courant, xmax))
        return tuple((a, b) for a, b in morceaux if b > a)

    def enjambe_une_coupure(self, x0, x1, y0=None, y1=None):
        """``True`` si une table ``[x0, x1]`` chevauche une coupure."""
        for c in self.coupures_sur_x():
            if x0 < c.fin - TOL_LONGUEUR_M and x1 > c.debut + TOL_LONGUEUR_M:
                return True
        if y0 is not None and y1 is not None:
            for c in self.coupures_sur_y():
                if y0 < c.fin - TOL_LONGUEUR_M and y1 > c.debut + TOL_LONGUEUR_M:
                    return True
        return False

    @property
    def aire_m2(self):
        """Aire brute de la surface (chiffrée, jamais utilisée pour compter)."""
        raise NotImplementedError
