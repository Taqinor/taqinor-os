# -*- coding: utf-8 -*-
"""AOF67 — le bandeau d'engagement : formulation imposée, GÉNÉRÉE.

Le bandeau est la seule ligne de la planche que le maître d'ouvrage lit à coup
sûr. Sa formulation est donc imposée mot pour mot, et surtout : **elle n'est
jamais rédigée à la main**. Un verdict tapé au clavier survit à la donnée qui
l'a produit — c'est ainsi qu'une planche finit par annoncer une marge qui
n'existe plus.

Les trois lignes, dans l'ordre :

1. « Capacité démontrée sur le relevé : N modules — ENGAGÉ AU MARCHÉ : E
   modules (marge +X) » en VERT, ou « (écart −X) » en ORANGE-TENDU ;
2. « Implantation définitive arrêtée après relevé d'exécution — marché à prix
   unitaires » ;
3. la ligne de paramètres et de variante conservatrice.

Et une QUATRIÈME ligne qui APPARAÎT seule, exactement quand N < E :
« Répartition des modules entre bâtiments ajustable à l'exécution dans le cadre
du marché à prix unitaires ». C'est elle, et elle seule, qui rend un bâtiment
« TENDU » non bloquant : sans elle, un écart sur un bâtiment se lit comme un
défaut d'offre ; avec elle, il se lit comme ce qu'il est — une répartition à
arrêter à l'exécution, dans un marché à prix unitaires.

Note d'implémentation : ``Engagement.ecart`` est la SEULE arithmétique métier
tolérée dans ``rendu/`` (allowlist nommée dans
``core/tests/test_calepinage_planche.py``). Ce n'est pas une re-dérivation
d'une grandeur du moteur : c'est la comparaison des deux entrées du bandeau,
et la calculer ici est précisément ce qui interdit de la rédiger à la main.
"""

from dataclasses import dataclass

from core.calepinage.rendu import couleurs as C

#: Ligne 2 — invariable, c'est la clause qui rattache la planche au marché.
LIGNE_MARCHE = ("Implantation définitive arrêtée après relevé d'exécution — "
                "marché à prix unitaires")

#: Ligne 4 — n'apparaît QUE lorsque la capacité démontrée est inférieure à
#: l'engagement. C'est elle qui rend un bâtiment « TENDU » non bloquant.
LIGNE_REPARTITION = ("Répartition des modules entre bâtiments ajustable à "
                     "l'exécution dans le cadre du marché à prix unitaires")

#: Signe moins TYPOGRAPHIQUE (U+2212) : sur une planche, le trait d'union d'un
#: clavier se confond avec un tiret de ponctuation.
MOINS = "−"


@dataclass(frozen=True)
class LigneBandeau:
    """Une ligne du bandeau, avec l'apparence que son sens commande."""

    texte: str
    couleur: str
    taille: float
    gras: bool = False


@dataclass(frozen=True)
class Engagement:
    """Ce que le relevé démontre, face à ce que l'offre engage.

    ``capacite_demontree`` et ``engagement_marche`` sont des comptes de modules
    produits par le moteur. ``parametres`` décrit le jeu de calepinage retenu
    (allées, rives, dégagements) : un bandeau qui annonce un compte sans dire
    de quels paramètres il dépend n'est pas vérifiable, donc pas remissible.
    """

    capacite_demontree: int
    engagement_marche: int
    parametres: str
    variante_conservatrice: str = ""

    def __post_init__(self):
        for nom in ("capacite_demontree", "engagement_marche"):
            valeur = getattr(self, nom)
            if not isinstance(valeur, int) or isinstance(valeur, bool):
                raise TypeError("%s doit être un compte entier de modules" % nom)
            if valeur < 0:
                raise ValueError("%s ne peut pas être négatif" % nom)
        if not (self.parametres or "").strip():
            raise ValueError(
                "un bandeau sans ses paramètres de calepinage n'est pas "
                "vérifiable : le compte annoncé dépend d'eux")

    # ------------------------------------------------------------------ verdict
    @property
    def ecart(self):
        """Capacité démontrée moins engagement — l'unique soustraction du rendu."""
        return self.capacite_demontree - self.engagement_marche

    @property
    def tenu(self):
        """L'engagement est-il couvert par le relevé ?"""
        return self.capacite_demontree >= self.engagement_marche

    @property
    def mention_ecart(self):
        """« marge +26 » ou « écart −26 ». JAMAIS saisi, toujours dérivé."""
        valeur = abs(self.ecart)
        if self.tenu:
            return "marge +{}".format(valeur)
        return "écart {}{}".format(MOINS, valeur)

    @property
    def couleur_verdict(self):
        return C.couleur_du_verdict(self.tenu)

    # ------------------------------------------------------------------- lignes
    def ligne_capacite(self):
        return LigneBandeau(
            texte=("Capacité démontrée sur le relevé : {} modules — "
                   "ENGAGÉ AU MARCHÉ : {} modules ({})").format(
                       self.capacite_demontree, self.engagement_marche,
                       self.mention_ecart),
            couleur=self.couleur_verdict, taille=9.5, gras=True)

    def ligne_marche(self):
        return LigneBandeau(texte=LIGNE_MARCHE, couleur=C.TEXTE_ENGAGEMENT,
                            taille=7.2, gras=True)

    def ligne_parametres(self):
        texte = self.parametres.strip()
        if self.variante_conservatrice.strip():
            texte = "{} — {}".format(texte, self.variante_conservatrice.strip())
        return LigneBandeau(texte=texte, couleur=C.TEXTE_PANNEAU, taille=6.0)

    def ligne_repartition(self):
        """La 4e ligne — ``None`` tant que la capacité couvre l'engagement."""
        if self.tenu:
            return None
        return LigneBandeau(texte=LIGNE_REPARTITION,
                            couleur=C.ORANGE_VERDICT_TENDU, taille=6.0)

    def lignes(self):
        """Les trois lignes, plus la quatrième exactement quand elle est due."""
        construites = [self.ligne_capacite(), self.ligne_marche(),
                       self.ligne_parametres()]
        repartition = self.ligne_repartition()
        if repartition is not None:
            construites.append(repartition)
        return tuple(construites)

    def textes(self):
        return tuple(ligne.texte for ligne in self.lignes())


def dessiner_bandeau(feuille, engagement, x, y, pas=0.85):
    """Empile le bandeau au-dessus du plan et retourne les lignes posées."""
    lignes = engagement.lignes()
    for indice, ligne in enumerate(lignes):
        feuille.texte(x, y - indice * pas, ligne.texte, ligne.couleur,
                      taille=ligne.taille, ha="center", va="center",
                      gras=ligne.gras, zorder=30)
    return lignes
