# -*- coding: utf-8 -*-
"""AOF66 — assemblage d'une planche depuis un plan VALIDÉ. AUCUN recalcul.

Le constat qui commande tout ce module est mesuré, pas théorique : à la fin de
la session du 27/07/2026, la note de synthèse annonçait encore **264 modules**
quand la donnée du calepinage en disait **314**. Le calcul n'avait pas menti —
il ne ment jamais. Ce qui avait menti, c'est la TROISIÈME copie du nombre :
une dans le script, une dans la planche, une dans la note. La duplication de la
donnée entre le moteur, le dessin et la vue est la SEULE source d'incohérence
observée de toute la session.

D'où le contrat de ce module, armé par des tests :

* ``DonneesPlanche`` est une PROJECTION en lecture seule du résultat validé.
  Le rendu ne recalcule rien : il ne sait ni compter des modules, ni convertir
  des kWc, ni sommer une surface. Un test STATIQUE interdit toute arithmétique
  métier dans tout ``rendu/``.
* **Tout nombre affiché doit provenir de la donnée.** ``Planche`` refuse de
  tracer un texte dont un nombre n'existe nulle part dans le résultat projeté
  (``NombreNonSource``) : le « 264 » d'une note retapée à la main devient une
  erreur détectée, pas une relecture chanceuse.
* **Aucune affirmation rédigée en dur.** Le rendu n'a le droit d'écrire ni
  « optimal » ni « conforme » : ces mots-là engagent le soumissionnaire, ils
  appartiennent au métier, jamais au dessin.

L'échelle est TOUJOURS graphique : l'impression d'un dossier d'appel d'offres
n'est pas garantie à l'échelle (photocopie, réduction A3->A4), une mention
« 1/200 » y devient donc fausse dès le premier tirage.
"""

import re
from dataclasses import dataclass, field

from core.calepinage.rendu import couleurs as C

#: Titre du bloc de sensibilités (variantes et hypothèses qui déplacent le compte).
TITRE_SENSIBILITES = "SENSIBILITÉS"

#: Titre du bloc de légende.
TITRE_LEGENDE = "LÉGENDE"

#: Un nombre tel qu'il paraît sur une planche française : 314, 51,1, 8.82.
NOMBRE = re.compile(r"\d+(?:[.,]\d+)?")


class RenduIncoherent(ValueError):
    """Le rendu et la donnée ne disent pas la même chose."""


class NombreNonSource(RenduIncoherent):
    """Un nombre affiché n'existe pas dans le résultat projeté.

    C'est le « 264 vs 314 » de la session du 27/07/2026, rendu impossible.
    """


def nombres_du_texte(texte):
    """Les nombres qu'un texte fait paraître, tels qu'ils sont écrits."""
    return tuple(NOMBRE.findall(texte or ""))


# ---------------------------------------------------------------------------
# La PROJECTION du résultat validé. Ces structures ne portent que des chaînes
# DÉJÀ FORMATÉES : le rendu ne formate pas plus qu'il ne calcule, sinon le même
# nombre finirait écrit de deux façons dans le même dossier.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Enveloppe:
    """Le contour relevé du support (toiture, terrasse, développé d'arc)."""

    points: tuple
    libelle: str = ""
    epaisseur: float = 2.2


@dataclass(frozen=True)
class ObstacleRendu:
    """Un volume relevé : cage, local, ouvrage bas, marche, ligne de niveau.

    ``statut`` À CONFIRMER -> contour ORANGE TIRETÉ : un obstacle NON COTÉ ne
    se présente pas avec l'aplomb d'un obstacle relevé.
    """

    x: float
    y: float
    largeur: float
    hauteur: float
    libelle: str = ""
    statut: C.StatutCote = C.StatutCote.MESURE
    plein: bool = False


@dataclass(frozen=True)
class ZoneRendue:
    """Une zone de toiture qualifiée par sa NATURE (dalle, bac acier, hors-PV…)."""

    points: tuple
    nature: str
    libelle: str = ""


@dataclass(frozen=True)
class StyleDeZone:
    """L'apparence d'une nature de zone. Les couleurs viennent de la palette."""

    nature: str
    remplissage: str = None
    contour: str = C.NOIR_GEOMETRIE
    hachure: str = None


@dataclass(frozen=True)
class TableRendue:
    """Une table posée, en POLYGONE : le même type sert au plan droit et à l'arc.

    ``faitage`` est le couple de points du trait de faîtage, ou ``()``.
    """

    points: tuple
    faitage: tuple = ()


@dataclass(frozen=True)
class CoteRendue:
    """Une cote du relevé, avec sa provenance (donc sa couleur)."""

    p1: tuple
    p2: tuple
    texte: str
    statut: C.StatutCote = C.StatutCote.MESURE
    decalage: float = 0.0
    mention: str = ""
    taille: float = 6.2
    cadre: bool = False


@dataclass(frozen=True)
class Sensibilite:
    """Une hypothèse qui déplace le compte, avec sa valeur DÉJÀ formatée."""

    libelle: str
    valeur: str


@dataclass(frozen=True)
class DonneesPlanche:
    """Ce qu'une planche a le droit de montrer — et rien d'autre.

    ``nombres`` porte les grandeurs publiables du résultat, DÉJÀ formatées par
    le moteur : ``(("capacité démontrée", "314 modules"), …)``. C'est la seule
    porte par laquelle un nombre entre sur la feuille.

    ``provenance`` porte le couple identifiant de l'artefact (hash d'entrée,
    version du moteur) tel que le moteur l'a produit : une planche sans
    provenance n'est pas rejouable.
    """

    enveloppe: Enveloppe
    obstacles: tuple = ()
    zones: tuple = ()
    tables: tuple = ()
    cotes: tuple = ()
    sensibilites: tuple = ()
    nombres: tuple = ()
    provenance: tuple = ()
    styles_de_zone: tuple = field(default=())

    # ------------------------------------------------------------ provenance
    def textes_de_la_donnee(self):
        """Toutes les chaînes issues du résultat — la SOURCE des nombres."""
        sources = [self.enveloppe.libelle]
        sources.extend(o.libelle for o in self.obstacles)
        sources.extend(z.libelle for z in self.zones)
        sources.extend(z.nature for z in self.zones)
        for cote in self.cotes:
            sources.append(cote.texte)
            sources.append(cote.mention)
        for sensibilite in self.sensibilites:
            sources.append(sensibilite.libelle)
            sources.append(sensibilite.valeur)
        for libelle, valeur in self.nombres:
            sources.append(libelle)
            sources.append(valeur)
        sources.extend(self.provenance)
        return tuple(s for s in sources if s)

    def nombres_de_la_donnee(self):
        """L'ensemble des nombres que le résultat autorise à faire paraître."""
        autorises = set()
        for texte in self.textes_de_la_donnee():
            autorises.update(nombres_du_texte(texte))
        return frozenset(autorises)

    def style_de_zone(self, nature):
        for style in self.styles_de_zone:
            if style.nature == nature:
                return style
        return StyleDeZone(nature=nature)


class Planche:
    """Assemble une planche depuis une ``DonneesPlanche``. Ne recalcule RIEN."""

    def __init__(self, donnees):
        self._donnees = donnees
        self._nombres_autorises = donnees.nombres_de_la_donnee()

    @property
    def donnees(self):
        return self._donnees

    @property
    def nombres_autorises(self):
        return self._nombres_autorises

    # ------------------------------------------------------------- provenance
    def verifier_texte(self, texte):
        """Refuse un texte dont un nombre n'existe pas dans le résultat.

        Un libellé sans chiffre passe librement : c'est du vocabulaire, pas de
        la donnée.
        """
        for nombre in nombres_du_texte(texte):
            if nombre not in self._nombres_autorises:
                raise NombreNonSource(
                    "nombre « %s » affiché sans source dans le résultat "
                    "(texte : « %s ») — la planche ne recalcule ni ne retape "
                    "aucune grandeur" % (nombre, texte))
        return texte

    def verifier_document(self, textes):
        """Confronte un texte EXTÉRIEUR (note, vue, courriel) à la donnée.

        C'est la garde qui manquait le 27/07/2026 : la note de synthèse
        annonçait 264 modules pendant que la planche en montrait 314. Le rendu
        n'a pas les moyens d'empêcher un tiers d'écrire un nombre — mais il
        peut le lui FAIRE VÉRIFIER, et c'est cette fonction que le producteur
        du dossier appelle avant de remettre quoi que ce soit.
        """
        for texte in textes:
            self.verifier_texte(texte)
        return tuple(textes)

    # ----------------------------------------------------------------- dessin
    def dessiner(self, feuille):
        """Pose la planche entière sur la feuille et retourne ce qui a été écrit."""
        self._dessiner_zones(feuille)
        self._dessiner_enveloppe(feuille)
        self._dessiner_tables(feuille)
        self._dessiner_obstacles(feuille)
        self._dessiner_cotes(feuille)
        return self.donnees

    def _dessiner_zones(self, feuille):
        for zone in self._donnees.zones:
            style = self._donnees.style_de_zone(zone.nature)
            feuille.polygone(zone.points, contour=style.contour,
                             remplissage=style.remplissage, lw=1.0, zorder=4,
                             hachure=style.hachure)
            if zone.libelle:
                self.verifier_texte(zone.libelle)

    def _dessiner_enveloppe(self, feuille):
        points = tuple(self._donnees.enveloppe.points)
        if len(points) < 3:
            raise RenduIncoherent(
                "une enveloppe relevée exige au moins trois points")
        feuille.polygone(points, contour=C.NOIR_GEOMETRIE,
                         lw=self._donnees.enveloppe.epaisseur, zorder=10)

    def _dessiner_tables(self, feuille):
        for table in self._donnees.tables:
            feuille.polygone(table.points, contour=C.VERT_TABLE_CONTOUR,
                             remplissage=C.VERT_TABLE_FOND, lw=0.35, zorder=5)
            if table.faitage:
                feuille.ligne(table.faitage[0], table.faitage[1],
                              C.VERT_TABLE_CONTOUR, lw=0.5, zorder=6)

    def _dessiner_obstacles(self, feuille):
        for obstacle in self._donnees.obstacles:
            contour, tirete = C.style_caisson(obstacle.statut)
            if obstacle.libelle:
                self.verifier_texte(obstacle.libelle)
            if obstacle.plein:
                feuille.bloc(obstacle.x, obstacle.y, obstacle.largeur,
                             obstacle.hauteur, contour=contour,
                             remplissage=C.FOND_BLOC,
                             etiquette=obstacle.libelle,
                             couleur_etiquette=C.TEXTE_PANNEAU)
            else:
                feuille.caisson(obstacle.x, obstacle.y, obstacle.largeur,
                                obstacle.hauteur, contour=contour,
                                remplissage=C.FOND_CAISSON,
                                etiquette=obstacle.libelle,
                                couleur_etiquette=contour, incertain=tirete)

    def _dessiner_cotes(self, feuille):
        for cote in self._donnees.cotes:
            self.verifier_texte(cote.texte)
            feuille.cote(cote.p1, cote.p2, C.couleur_du_statut(cote.statut),
                         off=cote.decalage, contenu=cote.texte,
                         taille=cote.taille, cadre=cote.cadre)

    # ----------------------------------------------------------- blocs de texte
    def lignes_de_sensibilites(self):
        """« libellé : valeur », GÉNÉRÉES depuis la donnée, jamais rédigées."""
        lignes = []
        for sensibilite in self._donnees.sensibilites:
            ligne = "%s : %s" % (sensibilite.libelle, sensibilite.valeur)
            lignes.append(self.verifier_texte(ligne))
        return tuple(lignes)

    def lignes_de_nombres(self):
        """Les grandeurs publiables, telles que le moteur les a formatées."""
        lignes = []
        for libelle, valeur in self._donnees.nombres:
            lignes.append(self.verifier_texte("%s : %s" % (libelle, valeur)))
        return tuple(lignes)

    def lignes_a_confirmer(self):
        """Le panneau orange, GÉNÉRÉ depuis les cotes (voir ``couleurs.py``)."""
        return C.section_a_confirmer(self._donnees.cotes)

    def entrees_de_legende(self):
        """Les statuts PRÉSENTS sur la planche, et seulement eux."""
        return C.entrees_de_legende(self._donnees.cotes)

    def dessiner_panneau(self, feuille, x, y, taille_titre=7.6, taille=5.9,
                         pas=0.82, pas_titre=1.15, pas_legende=0.95):
        """Le panneau latéral : légende, sensibilités, grandeurs, orange.

        Retourne l'ordonnée atteinte — l'appelant y pose la barre d'échelle.
        """
        courante = y
        entrees = self.entrees_de_legende()
        if entrees:
            courante = self._titre(feuille, x, courante, TITRE_LEGENDE,
                                   C.NOIR_GEOMETRIE, taille_titre, pas_titre)
            feuille.legende(x, courante, entrees, couleur_texte=C.TEXTE_PANNEAU,
                            taille=taille, pas=pas_legende)
            courante -= len(entrees) * pas_legende + pas
        for titre, lignes, couleur in (
                (TITRE_SENSIBILITES, self.lignes_de_sensibilites(),
                 C.NOIR_GEOMETRIE),
                (C.TITRE_SECTION_A_CONFIRMER, self.lignes_a_confirmer(),
                 C.ORANGE_A_CONFIRMER)):
            if not lignes:
                continue
            courante = self._titre(feuille, x, courante, titre, couleur,
                                   taille_titre, pas_titre)
            courante = self._lignes(feuille, x, courante, lignes, taille, pas)
        return courante

    def texte_annexe(self, feuille, x, y, texte, couleur=C.TEXTE_SECONDAIRE,
                     taille=6.0, ha="center", va="center", zorder=30):
        """Un nota de bas de plan, fourni par l'appelant — passé à la garde.

        Tout ce qui entre sur la feuille sans venir de ``DonneesPlanche``
        traverse ``verifier_texte`` : c'est le seul endroit par lequel un
        nombre retapé pourrait arriver, il est donc gardé.
        """
        self.verifier_texte(texte)
        return feuille.texte(x, y, texte, couleur, taille=taille, ha=ha,
                             va=va, zorder=zorder)

    def _titre(self, feuille, x, y, texte, couleur, taille, pas):
        feuille.texte(x, y, texte, couleur, taille=taille, ha="left", va="top",
                      gras=True, zorder=30)
        return y - pas

    def _lignes(self, feuille, x, y, lignes, taille, pas):
        for indice, ligne in enumerate(lignes):
            feuille.texte(x, y - indice * pas, ligne, C.TEXTE_PANNEAU,
                          taille=taille, ha="left", va="top", zorder=30)
        return y - len(lignes) * pas - pas

    # --------------------------------------------------------- barre d'échelle
    def dessiner_barre_echelle(self, feuille, x, y, total=10.0, pas=2.0):
        """L'échelle est GRAPHIQUE. Il n'existe aucun chemin vers une échelle chiffrée."""
        feuille.barre_echelle(x, y, couleur_trait=C.NOIR_GEOMETRIE,
                              couleur_texte=C.NOIR_GEOMETRIE, total=total,
                              pas=pas)
