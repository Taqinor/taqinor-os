# -*- coding: utf-8 -*-
"""AOF63 — ``core.calepinage.rendu.feuille`` : le tracé, les fils, les fuites.

``unittest`` pur : le sous-paquet ``rendu`` ne touche ni Django ni la base, donc
ces tests tournent HORS du gate migrations (le poste de coût CI dominant).

Trois preuves, exactement celles que la tâche exige :

1. **Identique au trait près à la planche d'origine** — la géométrie de cote
   produite par ``geometrie_cote`` est comparée à un ORACLE INDÉPENDANT :
   ``dessin.dim`` du 27/07/2026 recopié ici tel quel, dans le langage de son
   auteur. Si le port dérive d'un millimètre, le test est rouge.
2. **Deux rendus concurrents ne se marchent pas dessus** — deux fils rendent la
   même feuille témoin et doivent produire les MÊMES octets qu'un rendu série.
3. **Aucune figure fuitée** — le compteur de figures de ``pyplot`` ne bouge pas
   d'un cheveu, et la figure est réellement libérée après ``fermer()``.
"""

import ast
import gc
import math
import os
import threading
import unittest
import weakref

from django.test import tag

from core.calepinage.rendu import feuille as F

CHEMIN_MODULE = os.path.abspath(F.__file__)


# --------------------------------------------------------------------------
# ORACLE — ``dessin.dim`` du relevé du 27/07/2026, recopié SANS retouche.
# Il ne partage aucune ligne de code avec l'implémentation testée : c'est ce
# qui rend la comparaison probante plutôt que tautologique.
# --------------------------------------------------------------------------
def _unit(p1, p2):
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(dx, dy) or 1.0
    return dx / L, dy / L, L


def oracle_dim(p1, p2, off=0.8, gap=0.12, ext=0.18, text_off=0.22,
               flip_text=False):
    """Retourne (attaches, ligne_de_cote, ancre_texte, angle, longueur)."""
    ux, uy, L = _unit(p1, p2)
    nx, ny = -uy, ux
    q1 = (p1[0] + nx * off, p1[1] + ny * off)
    q2 = (p2[0] + nx * off, p2[1] + ny * off)
    s = 1 if off >= 0 else -1
    attaches = []
    for p, q in ((p1, q1), (p2, q2)):
        a = (p[0] + nx * gap * s, p[1] + ny * gap * s)
        b = (q[0] + nx * ext * s, q[1] + ny * ext * s)
        attaches.append((a, b))
    mx, my = (q1[0] + q2[0]) / 2, (q1[1] + q2[1]) / 2
    ang = math.degrees(math.atan2(uy, ux))
    if ang > 90 or ang <= -90:
        ang += 180
    toff = text_off if not flip_text else -text_off - 0.1
    ancre = (mx + nx * toff * s, my + ny * toff * s)
    return tuple(attaches), (q1, q2), ancre, ang, L


# --------------------------------------------------------------------------
# Feuille TÉMOIN — un extrait réel de la planche 05H (bâtiment C, école) :
# contour, ligne interne à décroché, cage, deux chaînes de cotes, une table,
# une légende et la barre d'échelle graphique.
# --------------------------------------------------------------------------
NOIR = "#111111"
BLEU = "#1d4ed8"
ORANGE = "#d97706"
GRIS = "#64748b"
VERT = "#15803d"
VERT_FOND = "#bbf7d0"


def construire_feuille_temoin():
    f = F.Feuille(
        "IMPLANTATION PHOTOVOLTAÏQUE — BÂTIMENT C : TERRASSE ÉCOLE SUPTECH",
        "Relevé contradictoire du 27/07/2026 — cotes en mètres",
        (-5.5, 45.5), (-3.7, 57.6))
    f.rectangle(0, 0, 26.2, 51.1, contour=NOIR, lw=2.2, zorder=10)
    f.ligne((0, 31.74), (13.18, 31.74), NOIR, lw=2.0)
    f.caisson(14.09, 22.92, 4.11, 8.82, contour=ORANGE, remplissage="#d8dee6",
              etiquette="cage", incertain=True)
    f.bloc(13.95, 10.50, 4.18, 4.50, contour=NOIR, remplissage="#eef1f5",
           etiquette="local")
    f.cote((0, 53.0), (13.18, 53.0), BLEU, off=0, contenu="13,18")
    f.cote((14.09, 53.0), (25.62, 53.0), GRIS, off=0, contenu="11,53 (déduit)")
    f.rectangle(0.35, 0.35, 4.70, 1.134, contour=VERT, remplissage=VERT_FOND,
                lw=0.35, zorder=5)
    f.legende(30.4, 48.0, ((None, "cote MESURÉE au relevé contradictoire"),
                           (None, "cote À CONFIRMER À L'EXÉCUTION")),
              couleur_texte="#1f2937")
    f.barre_echelle(30.4, 4.0, couleur_trait="black", couleur_texte=NOIR)
    return f


@tag('slow')
class GeometrieDeCote(unittest.TestCase):
    """Preuve 1 — le port est identique au trait près à ``dessin.dim``."""

    CAS = (
        ((0.0, 0.0), (10.0, 0.0), 0.8, False),
        ((0.0, 0.0), (10.0, 0.0), -0.8, False),
        ((0.0, 0.0), (0.0, 12.0), 0.0, False),
        ((3.0, 4.0), (-7.0, -1.5), 1.25, True),
        ((13.95, 11.6), (18.13, 11.6), 0.0, False),
        ((5.0, 5.0), (5.0, 5.0), 0.4, False),      # longueur nulle
    )

    def test_tous_les_traits_coincident_avec_l_oracle(self):
        for p1, p2, off, flip in self.CAS:
            with self.subTest(p1=p1, p2=p2, off=off, flip=flip):
                geo = F.geometrie_cote(p1, p2, off=off, flip_text=flip)
                att, ligne, ancre, angle, longueur = oracle_dim(
                    p1, p2, off=off, flip_text=flip)
                for obtenu, attendu in zip(geo.attaches, att):
                    for a, b in zip(obtenu, attendu):
                        self.assertAlmostEqual(a[0], b[0], places=12)
                        self.assertAlmostEqual(a[1], b[1], places=12)
                for a, b in zip(geo.ligne, ligne):
                    self.assertAlmostEqual(a[0], b[0], places=12)
                    self.assertAlmostEqual(a[1], b[1], places=12)
                self.assertAlmostEqual(geo.ancre_texte[0], ancre[0], places=12)
                self.assertAlmostEqual(geo.ancre_texte[1], ancre[1], places=12)
                self.assertAlmostEqual(geo.angle_texte, angle, places=12)
                self.assertAlmostEqual(geo.longueur, longueur, places=12)

    def test_le_texte_n_est_jamais_tete_en_bas(self):
        for p1, p2, off, flip in self.CAS:
            geo = F.geometrie_cote(p1, p2, off=off, flip_text=flip)
            self.assertGreater(geo.angle_texte, -90.0 - 1e-9)
            self.assertLessEqual(geo.angle_texte, 90.0 + 1e-9)

    def test_longueur_par_defaut_en_francais(self):
        self.assertEqual(F.texte_de_longueur(10.87), "10,87")
        self.assertEqual(F.texte_de_longueur(8.5, decimales=1), "8,5")

    def test_la_cote_dessinee_retourne_sa_geometrie(self):
        with F.Feuille("T", "s", (0, 20), (0, 20)) as f:
            geo = f.cote((1.0, 1.0), (11.0, 1.0), BLEU, off=0.8)
            attendu = F.geometrie_cote((1.0, 1.0), (11.0, 1.0), off=0.8)
            self.assertEqual(geo, attendu)
            # 2 lignes d'attache tracées + la double flèche + le texte
            self.assertEqual(len(f.axe.lines), 2)
            self.assertEqual(len(f.axe.patches), 1)
            self.assertEqual([t.get_text() for t in f.axe.texts], ["10,00"])


@tag('slow')
class FormatsDeFeuille(unittest.TestCase):
    def test_a3_paysage_par_defaut(self):
        with F.Feuille("T", "s", (0, 1), (0, 1)) as f:
            self.assertEqual(f.format.nom, "A3")
            self.assertEqual(f.format.figsize, (16.54, 11.69))
            self.assertGreater(f.format.largeur_pouces, f.format.hauteur_pouces)

    def test_a2_et_a1_disponibles(self):
        for nom in ("A2", "A1"):
            with F.Feuille("T", "s", (0, 1), (0, 1), format_nom=nom) as f:
                self.assertEqual(f.format.nom, nom)

    def test_format_inconnu_refuse_en_citant_les_formats_connus(self):
        with self.assertRaises(F.FormatInconnu) as capture:
            F.format_feuille("A4")
        self.assertIn("A3", str(capture.exception))

    def test_dpi_et_marges_configurables(self):
        with F.Feuille("T", "s", (0, 1), (0, 1), dpi=300) as f:
            self.assertEqual(f.dpi, 300.0)


@tag('slow')
class SortiesEnOctets(unittest.TestCase):
    """Le rendu retourne des OCTETS — il n'écrit AUCUN fichier."""

    def test_png_et_pdf_sont_des_octets_bien_formes(self):
        with construire_feuille_temoin() as f:
            png = f.png()
            pdf = f.pdf()
        self.assertIsInstance(png, bytes)
        self.assertIsInstance(pdf, bytes)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(png), 5000)
        self.assertGreater(len(pdf), 3000)

    def test_aucun_chemin_local_dans_la_sortie(self):
        with construire_feuille_temoin() as f:
            pdf = f.pdf()
        for interdit in (b"OneDrive", b"C:/Users", b"C:\\Users", b"/home/",
                         b"Atlencia"):
            self.assertNotIn(interdit, pdf)

    def test_feuille_fermee_refuse_de_rendre(self):
        f = construire_feuille_temoin()
        f.fermer()
        f.fermer()                       # idempotent
        with self.assertRaises(RuntimeError):
            f.png()


@tag('slow')
class AucunEtatGlobal(unittest.TestCase):
    """Preuves 2 et 3 — concurrence et fuite de figures."""

    def test_deux_rendus_concurrents_ne_se_marchent_pas_dessus(self):
        with construire_feuille_temoin() as f:
            reference = f.png(dpi=60)

        resultats = {}
        erreurs = []
        barriere = threading.Barrier(2)

        def rendre(cle):
            try:
                barriere.wait(timeout=30)
                with construire_feuille_temoin() as feuille:
                    resultats[cle] = feuille.png(dpi=60)
            except Exception as exc:                     # pragma: no cover
                erreurs.append(exc)

        fils = [threading.Thread(target=rendre, args=(i,)) for i in range(2)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join(timeout=60)

        self.assertEqual(erreurs, [])
        self.assertEqual(sorted(resultats), [0, 1])
        self.assertEqual(resultats[0], reference)
        self.assertEqual(resultats[1], reference)

    def test_aucune_figure_fuitee_dans_le_registre_pyplot(self):
        import matplotlib.pyplot as plt
        avant = set(plt.get_fignums())
        for _ in range(12):
            with construire_feuille_temoin() as f:
                f.png(dpi=50)
        self.assertEqual(set(plt.get_fignums()), avant)

    def test_la_figure_est_reellement_liberee(self):
        f = construire_feuille_temoin()
        temoin = weakref.ref(f.figure)
        f.fermer()
        gc.collect()
        self.assertIsNone(temoin(),
                          "la figure survit à fermer() : un worker de longue "
                          "durée fuirait une figure par planche")


@tag('slow')
class AucunCheminNiEtatDansLeCode(unittest.TestCase):
    """Les trois défauts NOMMÉS des scripts d'origine, interdits par test."""

    def _source(self):
        with open(CHEMIN_MODULE, "r", encoding="utf-8") as fh:
            return fh.read()

    def _arbre(self):
        return ast.parse(self._source(), filename=CHEMIN_MODULE)

    def _appels(self):
        """(nom_appele, ligne) pour chaque appel du module — docstrings exclues."""
        trouves = []
        for noeud in ast.walk(self._arbre()):
            if not isinstance(noeud, ast.Call):
                continue
            cible = noeud.func
            if isinstance(cible, ast.Attribute):
                trouves.append((cible.attr, noeud.lineno))
            elif isinstance(cible, ast.Name):
                trouves.append((cible.id, noeud.lineno))
        return trouves

    def _imports(self):
        noms = []
        for noeud in ast.walk(self._arbre()):
            if isinstance(noeud, ast.Import):
                noms.extend(a.name for a in noeud.names)
            elif isinstance(noeud, ast.ImportFrom) and not noeud.level:
                noms.append(noeud.module or "")
        return noms

    def test_aucun_chdir_aucun_sys_path_insert_aucun_makedirs(self):
        appeles = {nom for nom, _ in self._appels()}
        for interdit in ("chdir", "makedirs", "insert", "open", "print"):
            self.assertNotIn(
                interdit, appeles,
                "appel %s() interdit dans un moteur de rendu" % interdit)

    def test_aucun_chemin_local_dans_le_code(self):
        for interdit in ("DEST_PNG", "OneDrive", "Atlencia"):
            self.assertNotIn(interdit, self._source(),
                             "%s n'a rien à faire dans un moteur de rendu" % interdit)

    def test_aucun_appel_a_savefig_ni_a_pyplot(self):
        """``pyplot`` = registre global de figures = fuite + non-thread-safe."""
        appeles = {nom for nom, _ in self._appels()}
        self.assertNotIn("savefig", appeles)
        self.assertNotIn("use", appeles, "matplotlib.use() = backend GLOBAL")
        for nom in self._imports():
            self.assertNotIn("pyplot", nom)

    def test_aucune_globale_mutable_de_module(self):
        fautifs = []
        for noeud in self._arbre().body:
            if isinstance(noeud, (ast.Assign, ast.AnnAssign)):
                if isinstance(noeud.value, (ast.List, ast.Dict, ast.Set)):
                    fautifs.append(noeud.lineno)
        self.assertEqual(fautifs, [], "globale MUTABLE de module (lignes)")


if __name__ == "__main__":            # pragma: no cover
    unittest.main()
