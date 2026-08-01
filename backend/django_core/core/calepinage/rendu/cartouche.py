# -*- coding: utf-8 -*-
"""AOF64 — ``MarqueRendu`` : la marque de rendu est DISTINCTE de la société propriétaire.

Cas réel du dossier FRDISI du 27/07/2026 : les planches sont remises au nom
d'**ACCORDIA TECH**, le partenaire soumissionnaire. TAQINOR, qui exploite le
moteur, ne doit apparaître **nulle part** sur le livrable — ni au cartouche, ni
dans les mentions, ni dans les métadonnées du PDF. Le mélange des deux n'est pas
une coquille de mise en page : c'est une divulgation de sous-traitance dans une
consultation publique.

D'où la règle portée par ce module : le cartouche ne connaît QUE la
``MarqueRendu``. Il n'a aucun accès à l'entreprise propriétaire, et il est
capable de REFUSER un rendu dont un terme interdit se serait glissé dans la
donnée (``noms_interdits``) — la garde est active, pas déclarative.

Le cartouche type reprend, ligne à ligne, celui des trois planches remises :

    ACCORDIA TECH — Consultation FRDISI : PV + stockage, Mohammedia
    BÂT. C — TERRASSE ÉCOLE SUPTECH — IMPLANTATION PHOTOVOLTAÏQUE
    Document 05H — Statut : Appel d'offres
    Date : Juillet 2026 — Indice : H — relevé contradictoire du 27/07/2026
    Échelle : barre graphique (impression A3) — cotes en mètres
"""

from dataclasses import dataclass, replace

#: Le statut porté par toute planche versée à une consultation.
STATUT_APPEL_D_OFFRES = "Appel d'offres"

#: L'échelle est TOUJOURS graphique (voir ``Feuille.barre_echelle``) : une
#: échelle numérique ment dès la première photocopie réduite.
MENTION_ECHELLE = "Échelle : barre graphique (impression A3) — cotes en mètres"

#: Langues dont le cartouche est réellement rédigé. Une langue non traduite est
#: REFUSÉE plutôt que rendue à moitié : un cartouche mi-français mi-anglais dans
#: un dossier administratif est un motif d'irrégularité, pas un détail.
LANGUES_SUPPORTEES = ("fr",)


class LangueNonSupportee(ValueError):
    """Langue de cartouche non rédigée — refusée plutôt que rendue à moitié."""


class MarqueContaminee(ValueError):
    """Un terme interdit (typiquement la société propriétaire) est dans la marque."""


def _normaliser(texte):
    return " ".join((texte or "").split()).casefold()


@dataclass(frozen=True)
class MarqueRendu:
    """L'identité SOUS LAQUELLE la planche est remise.

    ``soumissionnaire`` peut être un PARTENAIRE : c'est le seul nom qui paraît.
    ``logo`` est un paquet d'OCTETS PNG (jamais un chemin) pour qu'une marque
    blanche puisse fournir le sien sans qu'aucun chemin local n'entre dans le
    rendu.
    """

    soumissionnaire: str
    code_document: str
    objet: str = ""
    designation_ouvrage: str = ""
    date: str = ""
    indice_revision: str = "A"
    statut: str = STATUT_APPEL_D_OFFRES
    base_releve: str = ""
    logo: bytes = None
    mentions: tuple = ()
    langue: str = "fr"

    def __post_init__(self):
        if self.langue not in LANGUES_SUPPORTEES:
            raise LangueNonSupportee(
                "cartouche non rédigé en %r — langues rédigées : %s"
                % (self.langue, ", ".join(LANGUES_SUPPORTEES)))
        if not (self.soumissionnaire or "").strip():
            raise ValueError("un cartouche sans soumissionnaire n'est pas remissible")
        if not (self.code_document or "").strip():
            raise ValueError("un cartouche sans code document n'est pas traçable")
        if not (self.indice_revision or "").strip():
            raise ValueError("un cartouche sans indice de révision n'est pas traçable")

    # ---------------------------------------------------------------- révision
    def indice_suivant(self):
        """``"A"`` -> ``"B"`` … ``"Z"`` -> ``"AA"``. Indices alphabétiques du BTP."""
        indice = self.indice_revision.strip().upper()
        if not indice.isalpha():
            raise ValueError(
                "indice de révision non alphabétique : %r" % (self.indice_revision,))
        lettres = list(indice)
        position = len(lettres) - 1
        while position >= 0:
            if lettres[position] != "Z":
                lettres[position] = chr(ord(lettres[position]) + 1)
                return "".join(lettres)
            lettres[position] = "A"
            position -= 1
        return "A" + "".join(lettres)

    def avec_indice(self, indice):
        """Nouvelle marque, indice CHANGÉ, tout le reste à l'identique.

        C'est le « l'indice s'incrémente sans réécrire le reste » de la tâche :
        une révision ne doit jamais être l'occasion de retoucher un autre champ
        du cartouche par inadvertance.
        """
        return replace(self, indice_revision=indice)

    def revisee(self):
        """La même marque, un cran de révision plus loin."""
        return self.avec_indice(self.indice_suivant())

    # ------------------------------------------------------------------ lignes
    def lignes(self):
        """Les lignes du cartouche : ``(texte, gras)``, dans l'ordre de lecture."""
        entete = self.soumissionnaire
        if self.objet:
            entete = "%s — %s" % (self.soumissionnaire, self.objet)
        construites = [(entete, True)]
        if self.designation_ouvrage:
            construites.append((self.designation_ouvrage, True))
        construites.append(
            ("Document %s — Statut : %s" % (self.code_document, self.statut), False))
        datation = "Date : %s — Indice : %s" % (self.date or "—",
                                                self.indice_revision)
        if self.base_releve:
            datation = "%s — %s" % (datation, self.base_releve)
        construites.append((datation, False))
        construites.append((MENTION_ECHELLE, False))
        for mention in self.mentions:
            construites.append((mention, False))
        return tuple(construites)

    def textes(self):
        """Toutes les chaînes que la marque fera paraître, à plat."""
        return tuple(texte for texte, _gras in self.lignes())


def verifier_marque(marque, noms_interdits):
    """Refuse une marque où un terme interdit paraîtrait, en CITANT le terme.

    ``noms_interdits`` contient typiquement le nom de la société propriétaire :
    une planche remise au nom d'un partenaire ne doit en porter aucune trace.
    """
    for interdit in noms_interdits:
        cible = _normaliser(interdit)
        if not cible:
            continue
        for texte in marque.textes():
            if cible in _normaliser(texte):
                raise MarqueContaminee(
                    "terme interdit dans le cartouche : « %s » (ligne : « %s »)"
                    % (interdit, texte))
    return marque


def dessiner_cartouche(feuille, marque, couleur_trait, couleur_texte,
                       noms_interdits=(), x=0.665, y=0.02, largeur=0.32,
                       hauteur=0.115, taille=7.5, taille_gras=8.5,
                       marge_gauche=0.008, zorder=50, largeur_logo=0.0):
    """Pose le cartouche en bas à droite (coordonnées FIGURE).

    Port de ``dessin.cartouche`` : même cadre, même répartition verticale des
    lignes, même graisse. La garde ``noms_interdits`` s'exécute AVANT le
    premier trait — un cartouche contaminé n'est jamais dessiné à moitié.
    """
    verifier_marque(marque, noms_interdits)
    lignes = marque.lignes()
    feuille.cadre_figure(x, y, largeur, hauteur, contour=couleur_trait,
                         zorder=zorder)
    if marque.logo and largeur_logo > 0:
        feuille.image_figure(marque.logo, x + largeur - largeur_logo - marge_gauche,
                             y + hauteur * 0.55, largeur_logo, hauteur * 0.4,
                             zorder=zorder + 2)
    nombre = len(lignes)
    for indice, (texte, gras) in enumerate(lignes):
        hauteur_ligne = hauteur - (indice + 0.85) * hauteur / (nombre + 0.3)
        feuille.texte_figure(x + marge_gauche, y + hauteur_ligne, texte,
                             couleur_texte,
                             taille=taille_gras if gras else taille,
                             ha="left", va="baseline", gras=gras,
                             zorder=zorder + 1)
    return lignes
