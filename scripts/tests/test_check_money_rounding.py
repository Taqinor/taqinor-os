"""Tests QJR4 -- scripts/check_money_rounding.py (cle d'identite de contenu).

Pur stdlib (unittest), sans Django ni base -- comme la garde elle-meme. Lancer :
    python -m unittest scripts.tests.test_check_money_rounding -v

Ce que ces tests verrouillent, dans l'ordre du Done= de QJR4 :
  * inserer 50 lignes EN AMONT ne change aucune cle (le point de la tache) ;
  * deplacer une fonction dans un autre module conserve son identite de
    contenu (seul le prefixe chemin change) ;
  * renommer la fonction englobante change la cle -- une suppression et une
    apparition, donc une relecture humaine, ce qui est voulu ;
  * supprimer un site laisse une entree ORPHELINE, signalee ;
  * ajouter un site NOUVEAU est rouge.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_money_rounding as cmr  # noqa: E402


MODULE_A = "a/module_a.py"
MODULE_B = "b/module_b.py"

BASE_SRC = '''\
def facturer(lignes):
    total_ht = sum(lignes)
    return round(total_ht, 2)
'''

SHIFTED_SRC = ("# commentaire de recalage\n" * 50) + BASE_SRC

RENAMED_SRC = BASE_SRC.replace("def facturer(", "def facturer_le_devis(")

TWO_IDENTICAL_SRC = '''\
def facturer(a, b):
    total_ht = a
    premier = round(total_ht, 2)
    total_ht = b
    second = round(total_ht, 2)
    return premier, second
'''

MODULE_LEVEL_SRC = '''\
BASE_HT = 1000.0
TOTAL_TTC = round(BASE_HT * 1.2, 2)
'''

METHOD_SRC = '''\
class Facture:
    def total(self, lignes):
        montant = sum(lignes)
        return round(montant, 2)
'''

NOT_MONEY_SRC = '''\
def surface(cotes):
    largeur = sum(cotes)
    return round(largeur, 2)
'''

ADDED_SITE_SRC = BASE_SRC + '''

def acompte(devis):
    montant_acompte = devis * 0.3
    return round(montant_acompte, 2)
'''


def _keys(source, rel=MODULE_A):
    return [site.key for site in cmr.collect_sites(source, rel)]


class TestCleDIdentiteDeContenu(unittest.TestCase):
    def test_forme_de_la_cle(self):
        (key,) = _keys(BASE_SRC)
        chemin, qualname, sha = key.split("::")
        self.assertEqual(chemin, MODULE_A)
        self.assertEqual(qualname, "facturer")
        self.assertEqual(sha, cmr.content_sha("total_ht"))
        self.assertEqual(len(sha), 12)

    def test_insertion_de_50_lignes_en_amont_ne_change_rien(self):
        """Le coeur de QJR4 : dix recalages manuels en aout, plus aucun."""
        avant = _keys(BASE_SRC)
        apres = _keys(SHIFTED_SRC)
        self.assertEqual(avant, apres)
        # ... alors que la ligne, elle, a bel et bien bouge de 50.
        self.assertEqual(cmr.collect_sites(BASE_SRC, MODULE_A)[0].lineno + 50,
                         cmr.collect_sites(SHIFTED_SRC, MODULE_A)[0].lineno)

    def test_deplacement_de_fonction_entre_modules(self):
        """Le chemin change, l'identite de contenu (qualname::sha) survit."""
        (dans_a,) = _keys(BASE_SRC, MODULE_A)
        (dans_b,) = _keys(BASE_SRC, MODULE_B)
        self.assertNotEqual(dans_a, dans_b)
        self.assertEqual(dans_a.split("::", 1)[1], dans_b.split("::", 1)[1])

    def test_renommage_de_la_fonction_change_la_cle(self):
        """Voulu : un renommage est une relecture, pas un recalage muet."""
        (avant,) = _keys(BASE_SRC)
        (apres,) = _keys(RENAMED_SRC)
        self.assertNotEqual(avant, apres)
        offenders, orphans = cmr.evaluate(
            cmr.collect_sites(RENAMED_SRC, MODULE_A), {avant: "relu"})
        self.assertEqual([s.key for s in offenders], [apres])
        self.assertEqual(orphans, [avant])

    def test_deux_round_identiques_dans_la_meme_fonction(self):
        premier, second = _keys(TWO_IDENTICAL_SRC)
        self.assertTrue(premier.endswith("#1"), premier)
        self.assertTrue(second.endswith("#2"), second)
        self.assertEqual(premier[:-2], second[:-2])

    def test_qualname_module_et_methode(self):
        (au_module,) = _keys(MODULE_LEVEL_SRC)
        self.assertEqual(au_module.split("::")[1], cmr.MODULE_QUALNAME)
        (methode,) = _keys(METHOD_SRC)
        self.assertEqual(methode.split("::")[1], "Facture.total")

    def test_expression_sans_semantique_monetaire_ignoree(self):
        self.assertEqual(_keys(NOT_MONEY_SRC), [])

    def test_espaces_normalises(self):
        eclate = "def facturer(lignes):\n    total_ht = 1\n    return round(\n        total_ht,\n        2,\n    )\n"
        (compact,) = _keys(BASE_SRC)
        (multi,) = _keys(eclate)
        self.assertEqual(compact, multi)


class TestBaseDeReference(unittest.TestCase):
    def _fichier_temporaire(self, texte):
        """Ecrit `texte` dans un fichier temporaire, nettoye a la fin du test."""
        fd, nom = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        chemin = Path(nom)
        chemin.write_text(texte, encoding="utf-8")
        self.addCleanup(lambda: chemin.exists() and chemin.unlink())
        return chemin

    def test_suppression_de_site_signale_une_entree_orpheline(self):
        (key,) = _keys(BASE_SRC)
        offenders, orphans = cmr.evaluate(
            cmr.collect_sites("def facturer(lignes):\n    return 0\n",
                              MODULE_A),
            {key: "relu"})
        self.assertEqual(offenders, [])
        self.assertEqual(orphans, [key])

    def test_nouveau_site_est_rouge(self):
        allow = {k: "relu" for k in _keys(BASE_SRC)}
        sites = cmr.collect_sites(ADDED_SITE_SRC, MODULE_A)
        offenders, orphans = cmr.evaluate(sites, allow)
        self.assertEqual(orphans, [])
        self.assertEqual(len(offenders), 1)
        self.assertEqual(offenders[0].qualname, "acompte")

    def test_lecture_du_format_cle_barre_raison(self):
        texte = (
            "# commentaire\n"
            "\n"
            "a/x.py::f::0123456789ab | une raison humaine\n"
            "a/x.py::g::ba9876543210\n"
        )
        entrees = cmr.load_allowlist(self._fichier_temporaire(texte))
        self.assertEqual(entrees, {
            "a/x.py::f::0123456789ab": "une raison humaine",
            "a/x.py::g::ba9876543210": "",
        })

    def test_regeneration_conserve_les_raisons_existantes(self):
        sites = cmr.collect_sites(ADDED_SITE_SRC, MODULE_A)
        connu = sites[0].key
        rendu = cmr.render_allowlist(sites, {connu: "deja relu en aout"})
        self.assertIn(f"{connu} | deja relu en aout", rendu)
        self.assertIn(cmr.NEW_SITE_REASON, rendu)
        # Le rendu doit se relire tel quel.
        self.assertEqual(
            set(cmr.load_allowlist(self._fichier_temporaire(rendu))),
            {site.key for site in sites})

    def test_la_base_livree_porte_une_raison_pour_chaque_cle(self):
        entrees = cmr.load_allowlist()
        self.assertTrue(entrees, "scripts/money_rounding_allow.txt est vide")
        sans_raison = [k for k, raison in entrees.items() if not raison]
        self.assertEqual(sans_raison, [])
        a_relire = [k for k, raison in entrees.items()
                    if raison == cmr.NEW_SITE_REASON]
        self.assertEqual(a_relire, [], "raison placeholder non completee")


if __name__ == "__main__":
    unittest.main()
