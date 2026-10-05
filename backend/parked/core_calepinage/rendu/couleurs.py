# -*- coding: utf-8 -*-
"""AOF65 — le statut d'une cote est porté par la DONNÉE ; la couleur en découle.

Sur les planches du 27/07/2026, le bleu, l'orange et le gris ne sont pas une
décoration : ils **engagent**. Bleu = mesuré contradictoirement sur site ;
orange = à confirmer à l'exécution ; gris = déduit d'une fermeture ou lu au
plan. Un maître d'ouvrage lit ce code, et un litige d'exécution se tranche
dessus.

C'est pourquoi la couleur n'est jamais choisie au moment de dessiner : elle est
DÉDUITE du ``StatutCote`` que porte la donnée. Trois conséquences directes,
toutes armées par ``core/tests/test_calepinage_couleurs.py`` :

* **la section « À CONFIRMER À L'EXÉCUTION » est GÉNÉRÉE** depuis les cotes —
  une cote orange oubliée dans le panneau devient impossible, alors que c'est
  exactement ce qui arrive quand la liste est retapée à la main ;
* **la légende ne re-déclare que les statuts PRÉSENTS** — une légende qui
  annonce un orange absent de la planche fait douter de tout le reste ;
* **changer une couleur ne se fait qu'ICI** — ce module est le seul endroit du
  sous-paquet où une valeur hexadécimale a le droit d'exister (test statique).
"""

from enum import Enum

# --------------------------------------------------------------- statuts de cote
#: Cote relevée contradictoirement sur site.
BLEU_MESURE = "#1d4ed8"
#: Cote ou position à confirmer au relevé d'exécution.
ORANGE_A_CONFIRMER = "#d97706"
#: Cote déduite d'une fermeture, ou lue au plan (donc non contradictoire).
GRIS_DEDUIT = "#64748b"

# ------------------------------------------------------------------- géométrie
#: Trait de la géométrie relevée (contours, murs, lignes de niveau).
NOIR_GEOMETRIE = "#111111"
#: Remplissage d'un caisson béton.
FOND_CAISSON = "#d8dee6"
#: Remplissage d'un volume relevé plein (cage, local).
FOND_BLOC = "#eef1f5"

# ------------------------------------------------------------------ tables PV
#: Remplissage d'une table photovoltaïque posée.
VERT_TABLE_FOND = "#bbf7d0"
#: Contour et trait de faîtage d'une table.
VERT_TABLE_CONTOUR = "#15803d"

# -------------------------------------------------------------------- verdicts
#: Capacité démontrée supérieure ou égale à l'engagement.
VERT_VERDICT = "#15803d"
#: Capacité démontrée inférieure à l'engagement — « tendu », jamais « échec ».
ORANGE_VERDICT_TENDU = "#c2410c"

# ---------------------------------------------------------------------- textes
#: Corps de texte des panneaux latéraux.
TEXTE_PANNEAU = "#1f2937"
#: Texte secondaire (nota de bas de plan, sous-titres).
TEXTE_SECONDAIRE = "#475569"
#: Texte d'accroche des lignes d'engagement neutres.
TEXTE_ENGAGEMENT = "#334155"


class StatutCote(Enum):
    """La provenance d'une cote. La couleur en est une CONSÉQUENCE, pas un choix."""

    MESURE = "mesure"
    A_CONFIRMER = "a_confirmer"
    DEDUIT_PLAN = "deduit_plan"

    @property
    def couleur(self):
        if self is StatutCote.MESURE:
            return BLEU_MESURE
        if self is StatutCote.A_CONFIRMER:
            return ORANGE_A_CONFIRMER
        return GRIS_DEDUIT

    @property
    def libelle(self):
        """Le libellé de légende — la phrase même des planches remises."""
        if self is StatutCote.MESURE:
            return "cote MESURÉE au relevé contradictoire (bleu)"
        if self is StatutCote.A_CONFIRMER:
            return "cote / position À CONFIRMER À L'EXÉCUTION (orange)"
        return "cote de plan / déduite des fermetures (gris)"

    @property
    def trait_tirete(self):
        """Une donnée INCERTAINE se dessine en tireté — jamais en trait plein."""
        return self is StatutCote.A_CONFIRMER

    @property
    def rang(self):
        """Ordre canonique de lecture : mesuré, à confirmer, déduit."""
        return ORDRE_DES_STATUTS.index(self)


#: Ordre de lecture, figé (un tuple : aucune globale MUTABLE dans ce paquet).
ORDRE_DES_STATUTS = (StatutCote.MESURE, StatutCote.A_CONFIRMER,
                     StatutCote.DEDUIT_PLAN)

#: Titre exact du panneau généré depuis les cotes oranges.
TITRE_SECTION_A_CONFIRMER = "À CONFIRMER À L'EXÉCUTION (orange)"


class SectionIncomplete(ValueError):
    """Une cote À CONFIRMER manque à la section générée — cas ROUGE de la tâche."""


def couleur_du_statut(statut):
    """``StatutCote`` -> couleur. Le SEUL chemin d'une donnée vers une couleur."""
    if not isinstance(statut, StatutCote):
        raise TypeError("statut de cote attendu, reçu %r" % (statut,))
    return statut.couleur


def couleur_du_verdict(capacite_atteinte):
    """Vert si la capacité démontrée tient l'engagement, orange-tendu sinon."""
    return VERT_VERDICT if capacite_atteinte else ORANGE_VERDICT_TENDU


def style_caisson(statut):
    """``(contour, tireté)`` d'un caisson — orange TIRETÉ dès qu'il est incertain.

    Un caisson dont la géométrie n'est pas contradictoire ne doit pas se
    présenter avec l'aplomb d'un caisson relevé : le trait tireté orange est ce
    qui empêche un lecteur pressé de le prendre pour acquis.
    """
    return couleur_du_statut(statut), statut.trait_tirete


def _mention(cote):
    """La phrase que la cote fait paraître dans la section générée."""
    mention = getattr(cote, "mention", "") or ""
    if mention.strip():
        return mention.strip()
    texte = (getattr(cote, "texte", "") or "").strip()
    if not texte:
        raise SectionIncomplete(
            "une cote À CONFIRMER sans mention ni texte ne peut pas être "
            "annoncée au maître d'ouvrage")
    return texte


def statuts_presents(cotes):
    """Les statuts réellement portés par les cotes, dans l'ordre canonique."""
    trouves = {cote.statut for cote in cotes}
    return tuple(statut for statut in ORDRE_DES_STATUTS if statut in trouves)


def legende_des_statuts(cotes):
    """``((statut, libellé), …)`` — les statuts PRÉSENTS et seulement ceux-là."""
    return tuple((statut, statut.libelle) for statut in statuts_presents(cotes))


def cotes_a_confirmer(cotes):
    """Les cotes oranges, dans l'ordre où elles ont été fournies."""
    return tuple(cote for cote in cotes
                 if cote.statut is StatutCote.A_CONFIRMER)


def section_a_confirmer(cotes):
    """Les lignes du panneau « À CONFIRMER À L'EXÉCUTION », GÉNÉRÉES.

    Une ligne par cote orange, sans doublon, dans l'ordre de la donnée.
    """
    lignes = []
    for cote in cotes_a_confirmer(cotes):
        mention = _mention(cote)
        if mention not in lignes:
            lignes.append(mention)
    return tuple(lignes)


def verifier_section_complete(cotes, lignes):
    """Refuse une section où une cote À CONFIRMER manque, en la CITANT.

    C'est le cas ROUGE exigé par la tâche : la section n'est pas un texte libre
    posé à côté du dessin, c'est une projection de la donnée, et l'écart entre
    les deux est une erreur détectée, pas une nuance de rédaction.
    """
    presentes = tuple(lignes)
    for cote in cotes_a_confirmer(cotes):
        mention = _mention(cote)
        if mention not in presentes:
            raise SectionIncomplete(
                "cote À CONFIRMER absente de la section générée : « %s »"
                % (mention,))
    return presentes


def echantillon_de_statut(statut, longueur=1.3, taille_fleche=6):
    """Appelable ``(feuille, x, y) -> None`` : l'échantillon de légende du statut.

    ``Feuille`` ne connaît aucun vocabulaire métier ; c'est ce module qui sait
    à quoi ressemble un statut de cote sur le papier.
    """
    couleur = couleur_du_statut(statut)

    def dessiner(feuille, x, y):
        feuille.fleche_double((x, y), (x + longueur, y), couleur,
                              echelle=taille_fleche, zorder=30)

    return dessiner


def entrees_de_legende(cotes):
    """``((echantillon, libellé), …)`` prêt pour ``Feuille.legende``."""
    return tuple((echantillon_de_statut(statut), libelle)
                 for statut, libelle in legende_des_statuts(cotes))
