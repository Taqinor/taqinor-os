# -*- coding: utf-8 -*-
"""AOF66 — la planche montre le résultat. Elle ne le recalcule pas.

Le défaut de référence est réel et daté : le 27/07/2026, la note de synthèse
annonçait 264 modules quand la donnée en disait 314. Trois copies du même
nombre, une seule vérité. Ce fichier arme les trois garanties de la tâche :

1. un test STATIQUE interdit toute arithmétique métier dans TOUT ``rendu/`` ;
2. tous les nombres affichés proviennent du résultat projeté — sinon
   ``NombreNonSource`` ;
3. aucune chaîne affirmative (« optimal », « conforme ») n'est écrite en dur,
   et l'échelle n'est jamais chiffrée.
"""

import ast
import os
import re
import unittest

from core.calepinage.rendu import couleurs as C
from core.calepinage.rendu import planche as P
from core.calepinage.rendu.feuille import Feuille

DOSSIER_RENDU = os.path.dirname(os.path.abspath(P.__file__))

#: Vocabulaire MÉTIER : ce qui se compte, se convertit, se facture. Une
#: identité qui contient l'un de ces fragments ne doit JAMAIS être l'opérande
#: d'une opération arithmétique dans le rendu — ce serait une deuxième source
#: de vérité, c'est-à-dire un « 264 » en puissance.
#: (« marge » est DÉLIBÉRÉMENT absent : dans ce paquet il désigne une marge de
#: PAGE, pas une marge d'engagement — celle-ci s'appelle ``ecart``, et c'est la
#: seule tolérance déclarée ci-dessous.)
LEXIQUE_METIER = ("module", "kwc", "kwh", "watt", "puissance", "production",
                  "capacite", "engage", "prix", "montant", "cout",
                  "ecart", "rendement", "tarif", "surface")

#: La SEULE arithmétique métier tolérée dans ``rendu/``, nommée une fois pour
#: toutes : l'écart d'engagement du bandeau (AOF67), qui est une COMPARAISON de
#: deux entrées du bandeau, pas une re-dérivation d'une grandeur du moteur.
#: Son contenu exact est vérifié par ``test_calepinage_bandeau.py``.
ARITHMETIQUE_TOLEREE = (("bandeau.py", "ecart"),)

#: Mots qui ENGAGENT le soumissionnaire : ils appartiennent au métier, jamais
#: au dessin.
MOTS_AFFIRMATIFS = re.compile(
    r"\b(optimal|optimale|optimaux|conforme|conformes|garanti|garantie|"
    r"idéal|idéale|parfait|parfaite|meilleur|meilleure)\b", re.IGNORECASE)

#: Une échelle chiffrée (« 1/200 », « 1:200 ») ment dès la première photocopie.
ECHELLE_CHIFFREE = re.compile(r"\b1\s*[/:]\s*\d{2,}")

OPERATEURS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
              ast.Pow)


def _modules_de_rendu():
    for nom in sorted(os.listdir(DOSSIER_RENDU)):
        if nom.endswith(".py"):
            yield nom, os.path.join(DOSSIER_RENDU, nom)


def _arbre(chemin):
    with open(chemin, "r", encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=chemin)


def _identifiants(noeud):
    """Les identités lisibles d'une expression (Name / Attribute)."""
    trouves = []
    for sous in ast.walk(noeud):
        if isinstance(sous, ast.Name):
            trouves.append(sous.id)
        elif isinstance(sous, ast.Attribute):
            trouves.append(sous.attr)
    return trouves


def _est_metier(nom):
    minuscule = nom.casefold()
    return any(fragment in minuscule for fragment in LEXIQUE_METIER)


def _docstrings(arbre):
    """Les nœuds de docstring — ils DÉCRIVENT le défaut, ils ne le commettent pas."""
    reperes = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                  ast.AsyncFunctionDef)):
            continue
        corps = getattr(noeud, "body", ())
        if (corps and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)):
            reperes.add(id(corps[0].value))
    return reperes


def _chaines_rendues(arbre):
    """Les chaînes littérales qui peuvent finir sur le papier."""
    reperes = _docstrings(arbre)
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
                and id(noeud) not in reperes):
            yield noeud.value, noeud.lineno


def _arithmetique_metier(arbre):
    """``(fonction_englobante, ligne, identifiant)`` pour chaque opération métier."""
    trouves = []

    def visiter(noeud, fonction):
        for enfant in ast.iter_child_nodes(noeud):
            courante = fonction
            if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef)):
                courante = enfant.name
            if isinstance(enfant, ast.BinOp) and isinstance(enfant.op, OPERATEURS):
                for identifiant in (_identifiants(enfant.left)
                                    + _identifiants(enfant.right)):
                    if _est_metier(identifiant):
                        trouves.append((courante, enfant.lineno, identifiant))
            visiter(enfant, courante)

    visiter(arbre, None)
    return trouves


# ---------------------------------------------------------------------------
# Planche TÉMOIN — extrait de la planche 05H (bâtiment C, école SUPTECH).
# Tous les nombres viennent de la DONNÉE, aucun n'est retapé ici.
# ---------------------------------------------------------------------------
def donnees_temoin():
    return P.DonneesPlanche(
        enveloppe=P.Enveloppe(points=((0, 0), (26.2, 0), (26.2, 51.1),
                                      (0, 51.1))),
        zones=(P.ZoneRendue(points=((0, 0), (25.62, 0), (25.62, 31.74),
                                    (0, 31.74)),
                            nature="terrasse basse"),),
        styles_de_zone=(P.StyleDeZone(nature="terrasse basse",
                                      remplissage=C.FOND_BLOC),),
        obstacles=(
            P.ObstacleRendu(14.09, 22.92, 4.11, 8.82, libelle="cage",
                            statut=C.StatutCote.A_CONFIRMER),
            P.ObstacleRendu(13.95, 10.50, 4.18, 4.50, libelle="local",
                            plein=True),
        ),
        tables=(P.TableRendue(points=((0.35, 0.35), (5.05, 0.35),
                                      (5.05, 1.484), (0.35, 1.484)),
                              faitage=((2.70, 0.35), (2.70, 1.484))),),
        cotes=(
            P.CoteRendue((0, 53.0), (13.18, 53.0), "13,18"),
            P.CoteRendue((14.09, 53.0), (25.62, 53.0), "11,53 (déduit)",
                         statut=C.StatutCote.DEDUIT_PLAN),
            P.CoteRendue((25.62, 22.92), (25.62, 31.74), "≈8,82",
                         statut=C.StatutCote.A_CONFIRMER,
                         mention="profondeur de la cage ≈8,82, déduite de la "
                                 "fermeture 51,1"),
        ),
        sensibilites=(
            P.Sensibilite("variante conservatrice 1,50/0,50/0,50", "268 modules"),
            P.Sensibilite("uniforme 0,60", "314 modules"),
        ),
        nombres=(
            ("capacité démontrée sur le relevé", "314 modules"),
            ("engagé au marché", "288 modules"),
        ),
        provenance=("moteur 1.0.0", "entrée a1b2c3"),
    )


class ArithmetiqueMetierInterdite(unittest.TestCase):
    """« un test STATIQUE interdit toute arithmétique métier dans rendu/ »."""

    def test_aucune_operation_sur_une_grandeur_metier(self):
        fautifs = []
        for nom, chemin in _modules_de_rendu():
            for fonction, ligne, identifiant in _arithmetique_metier(
                    _arbre(chemin)):
                if (nom, fonction) in ARITHMETIQUE_TOLEREE:
                    continue
                fautifs.append((nom, fonction, ligne, identifiant))
        self.assertEqual(
            fautifs, [],
            "arithmétique métier dans rendu/ — le rendu MONTRE le résultat, il "
            "ne le recalcule pas (c'est le défaut « 264 vs 314 ») : %r"
            % (fautifs,))

    def test_le_detecteur_voit_reellement_une_faute(self):
        """Sans ce témoin, le test précédent pourrait être vert par construction."""
        arbre = ast.parse("def rendre(res):\n"
                          "    return res.modules * 0.625\n")
        trouves = _arithmetique_metier(arbre)
        self.assertEqual([(f, i) for f, _l, i in trouves],
                         [("rendre", "modules")])

    def test_la_tolerance_est_nommee_et_minimale(self):
        self.assertEqual(len(ARITHMETIQUE_TOLEREE), 1)
        self.assertEqual(ARITHMETIQUE_TOLEREE[0], ("bandeau.py", "ecart"))


class AucuneAffirmationEcriteEnDur(unittest.TestCase):
    def test_aucun_mot_qui_engage_le_soumissionnaire(self):
        fautifs = []
        for nom, chemin in _modules_de_rendu():
            for chaine, ligne in _chaines_rendues(_arbre(chemin)):
                trouve = MOTS_AFFIRMATIFS.search(chaine)
                if trouve:
                    fautifs.append((nom, ligne, trouve.group(0)))
        self.assertEqual(
            fautifs, [],
            "affirmation rédigée en dur dans rendu/ — ces mots engagent le "
            "soumissionnaire : %r" % (fautifs,))

    def test_aucune_echelle_chiffree(self):
        fautifs = []
        for nom, chemin in _modules_de_rendu():
            for chaine, ligne in _chaines_rendues(_arbre(chemin)):
                if ECHELLE_CHIFFREE.search(chaine):
                    fautifs.append((nom, ligne, chaine))
        self.assertEqual(fautifs, [],
                         "échelle chiffrée : l'impression n'est pas garantie "
                         "à l'échelle — la barre graphique est la seule vraie")

    def test_le_detecteur_de_mots_voit_reellement_une_faute(self):
        self.assertTrue(MOTS_AFFIRMATIFS.search("calepinage optimal"))
        self.assertTrue(MOTS_AFFIRMATIFS.search("Installation CONFORME"))
        self.assertTrue(ECHELLE_CHIFFREE.search("Échelle 1/200"))
        self.assertIsNone(MOTS_AFFIRMATIFS.search("à confirmer à l'exécution"))


class TousLesNombresViennentDuResultat(unittest.TestCase):
    def test_les_nombres_de_la_donnee_sont_reconnus(self):
        autorises = donnees_temoin().nombres_de_la_donnee()
        for nombre in ("13,18", "11,53", "8,82", "51,1", "314", "288", "268",
                       "1,50", "0,60", "1.0.0"[0]):
            self.assertIn(nombre, autorises, nombre)

    def test_un_nombre_sans_source_est_REFUSE_en_le_citant(self):
        """LE défaut du 27/07/2026 : la note disait 264, la donnée disait 314."""
        planche = P.Planche(donnees_temoin())
        with self.assertRaises(P.NombreNonSource) as capture:
            planche.verifier_texte("capacité démontrée : 264 modules")
        self.assertIn("264", str(capture.exception))

    def test_le_nombre_reellement_calcule_passe(self):
        planche = P.Planche(donnees_temoin())
        self.assertEqual(
            planche.verifier_texte("capacité démontrée : 314 modules"),
            "capacité démontrée : 314 modules")

    def test_un_libelle_sans_chiffre_passe_librement(self):
        planche = P.Planche(donnees_temoin())
        self.assertEqual(planche.verifier_texte("cage d'escalier"),
                         "cage d'escalier")

    def test_les_blocs_de_texte_sont_generes_depuis_la_donnee(self):
        planche = P.Planche(donnees_temoin())
        self.assertEqual(
            planche.lignes_de_nombres(),
            ("capacité démontrée sur le relevé : 314 modules",
             "engagé au marché : 288 modules"))
        self.assertEqual(
            planche.lignes_de_sensibilites(),
            ("variante conservatrice 1,50/0,50/0,50 : 268 modules",
             "uniforme 0,60 : 314 modules"))

    def test_un_nota_retape_fait_echouer_le_dessin(self):
        """Tout ce qui n'est pas dans la donnée traverse la garde."""
        planche = P.Planche(donnees_temoin())
        with Feuille("T", "s", (0, 30), (0, 60)) as feuille:
            with self.assertRaises(P.NombreNonSource):
                planche.texte_annexe(feuille, 13.1, -1.35,
                                     "capacité retenue : 264 modules")
            self.assertEqual(len(feuille.axe.texts), 0)
            planche.texte_annexe(feuille, 13.1, -2.05,
                                 "capacité retenue : 314 modules")
            self.assertEqual(len(feuille.axe.texts), 1)

    def test_la_note_de_synthese_est_confrontee_a_la_planche(self):
        """Le défaut daté du 27/07/2026, pris à sa source réelle."""
        planche = P.Planche(donnees_temoin())
        note_fausse = ("Le calepinage retenu porte 264 modules.",
                       "Engagement au marché : 288 modules.")
        with self.assertRaises(P.NombreNonSource) as capture:
            planche.verifier_document(note_fausse)
        self.assertIn("264", str(capture.exception))
        note_juste = ("Le calepinage retenu porte 314 modules.",
                      "Engagement au marché : 288 modules.")
        self.assertEqual(planche.verifier_document(note_juste), note_juste)

    def test_la_section_orange_est_generee_depuis_les_cotes(self):
        planche = P.Planche(donnees_temoin())
        lignes = planche.lignes_a_confirmer()
        self.assertEqual(len(lignes), 1)
        self.assertIn("profondeur de la cage", lignes[0])
        C.verifier_section_complete(donnees_temoin().cotes, lignes)

    def test_la_legende_ne_declare_que_les_statuts_presents(self):
        entrees = P.Planche(donnees_temoin()).entrees_de_legende()
        self.assertEqual(len(entrees), 3)


class AssemblageDeLaPlanche(unittest.TestCase):
    def test_tous_les_elements_sont_poses(self):
        donnees = donnees_temoin()
        with Feuille("T", "s", (-5, 45), (-4, 58)) as feuille:
            P.Planche(donnees).dessiner(feuille)
            polygones = len([p for p in feuille.axe.patches
                             if type(p).__name__ == "Polygon"])
            rectangles = len([p for p in feuille.axe.patches
                              if type(p).__name__ == "Rectangle"])
            fleches = len([p for p in feuille.axe.patches
                           if type(p).__name__ == "FancyArrowPatch"])
        # 1 zone + 1 enveloppe + 1 table
        self.assertEqual(polygones, 3)
        # 1 caisson + 1 bloc
        self.assertEqual(rectangles, 2)
        # une double flèche par cote
        self.assertEqual(fleches, len(donnees.cotes))

    def test_un_obstacle_non_cote_est_orange_et_tirete(self):
        with Feuille("T", "s", (-5, 45), (-4, 58)) as feuille:
            P.Planche(donnees_temoin()).dessiner(feuille)
            caisson = [p for p in feuille.axe.patches
                       if type(p).__name__ == "Rectangle"][0]
            style, couleur = caisson.get_linestyle(), caisson.get_edgecolor()
        self.assertEqual(style, "--")
        self.assertEqual(couleur[:3], (0xd9 / 255, 0x77 / 255, 0x06 / 255))

    def test_une_enveloppe_degeneree_est_refusee(self):
        donnees = P.DonneesPlanche(
            enveloppe=P.Enveloppe(points=((0, 0), (1, 1))))
        with Feuille("T", "s", (0, 10), (0, 10)) as feuille:
            with self.assertRaises(P.RenduIncoherent):
                P.Planche(donnees).dessiner(feuille)

    def test_la_table_porte_son_trait_de_faitage(self):
        with Feuille("T", "s", (-5, 45), (-4, 58)) as feuille:
            P.Planche(donnees_temoin()).dessiner(feuille)
            traits = len(feuille.axe.lines)
        # 2 lignes d'attache par cote + 1 faîtage
        self.assertEqual(traits, 2 * len(donnees_temoin().cotes) + 1)

    def test_la_barre_d_echelle_est_graphique(self):
        with Feuille("T", "s", (0, 45), (0, 20)) as feuille:
            planche = P.Planche(donnees_temoin())
            planche.dessiner_barre_echelle(feuille, 30.4, 4.0, total=10, pas=2)
            segments = [p for p in feuille.axe.patches
                        if type(p).__name__ == "Rectangle"]
            graduations = [t.get_text() for t in feuille.axe.texts]
        self.assertEqual(len(segments), 5)
        self.assertEqual(graduations, ["0", "2", "4", "6", "8", "10", "mètres"])

    def test_le_panneau_lateral_ecrit_les_trois_blocs(self):
        with Feuille("T", "s", (0, 45), (0, 55)) as feuille:
            planche = P.Planche(donnees_temoin())
            fin = planche.dessiner_panneau(feuille, 30.4, 50.6)
            ecrits = [t.get_text() for t in feuille.axe.texts]
        self.assertLess(fin, 50.6)
        self.assertIn(P.TITRE_LEGENDE, ecrits)
        self.assertIn(P.TITRE_SENSIBILITES, ecrits)
        self.assertIn(C.TITRE_SECTION_A_CONFIRMER, ecrits)
        self.assertIn("uniforme 0,60 : 314 modules", ecrits)

    def test_une_planche_sans_cote_n_ecrit_ni_legende_ni_section_orange(self):
        donnees = P.DonneesPlanche(
            enveloppe=P.Enveloppe(points=((0, 0), (10, 0), (10, 10), (0, 10))))
        with Feuille("T", "s", (0, 45), (0, 55)) as feuille:
            P.Planche(donnees).dessiner_panneau(feuille, 30.4, 50.6)
            ecrits = [t.get_text() for t in feuille.axe.texts]
        self.assertEqual(ecrits, [])

    def test_la_planche_entiere_sort_en_octets(self):
        with Feuille("IMPLANTATION PHOTOVOLTAÏQUE", "relevé du 27/07/2026",
                     (-5, 45), (-4, 58)) as feuille:
            planche = P.Planche(donnees_temoin())
            planche.dessiner(feuille)
            planche.dessiner_panneau(feuille, 30.4, 50.6)
            planche.dessiner_barre_echelle(feuille, 30.4, 3.6)
            octets = feuille.pdf()
        self.assertTrue(octets.startswith(b"%PDF"))


if __name__ == "__main__":            # pragma: no cover
    unittest.main()
