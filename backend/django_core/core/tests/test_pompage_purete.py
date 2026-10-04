# -*- coding: utf-8 -*-
"""AGR109 — le paquet ``core.pompage`` est un NOYAU PUR (test armé).

Miroir de ``test_electrique_purete.py`` pour le moteur de pompage. Second verrou
de la pureté (le premier est le contrat import-linter
``pompage-est-un-noyau-pur``). Il analyse l'AST de CHAQUE fichier du paquet et
échoue si :

* un import sort de la liste blanche (stdlib + le paquet lui-même +
  ``core.electrique``) — ajouter ``import django`` rend ce test ROUGE ;
* un appel d'I/O apparaît (``open``, ``print``…) ;
* une globale MUTABLE de module apparaît (liste/dict/ensemble au niveau module).

Il ne dépend PAS de Django : ``unittest`` pur, aucune base de données.
"""

import ast
import os
import sys
import tempfile
import unittest

PAQUET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "pompage")

#: Racines internes permises : le paquet lui-même et le noyau électrique.
RACINES_INTERNES = ("core.pompage", "core.electrique")

APPELS_INTERDITS = frozenset({
    "open", "print", "input", "exec", "eval", "compile", "__import__",
})
ATTRIBUTS_INTERDITS = frozenset({
    "makedirs", "mkdir", "remove", "unlink", "rmtree", "system", "popen",
    "savefig", "write_text", "write_bytes",
})
RACINES_DJANGO = frozenset({"django", "rest_framework", "celery", "apps",
                            "authentication"})


def _stdlib():
    noms = getattr(sys, "stdlib_module_names", None)
    if noms:
        return set(noms)
    return {"math", "json", "dataclasses", "typing", "enum", "itertools",
            "functools", "bisect", "collections", "re", "types", "decimal"}


STDLIB = _stdlib()


def _fichiers(paquet=PAQUET):
    for racine, _dirs, fichiers in os.walk(paquet):
        for nom in sorted(fichiers):
            if nom.endswith(".py"):
                yield os.path.join(racine, nom)


def _imports_source(source, nom="<src>"):
    arbre = ast.parse(source, filename=nom)
    trouves = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            trouves.extend(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and not noeud.level:
            trouves.append(noeud.module or "")
    return trouves


def _imports_interdits(paquet=PAQUET):
    fautifs = []
    for chemin in _fichiers(paquet):
        with open(chemin, "r", encoding="utf-8") as fh:
            source = fh.read()
        for nom in _imports_source(source, chemin):
            if any(nom == r or nom.startswith(r + ".") for r in RACINES_INTERNES):
                continue
            racine = nom.split(".")[0]
            if racine in STDLIB and racine not in RACINES_DJANGO:
                continue
            fautifs.append((os.path.relpath(chemin, paquet), nom))
    return fautifs


class ImportsDuPaquet(unittest.TestCase):

    def test_le_paquet_existe_et_a_ses_modules(self):
        noms = {os.path.basename(c) for c in _fichiers()}
        for attendu in ("__init__.py", "hydraulique.py", "selection.py",
                        "volumes.py"):
            self.assertIn(attendu, noms)

    def test_aucun_import_hors_liste_blanche(self):
        self.assertEqual(_imports_interdits(), [],
                         "core/pompage/ doit rester PUR (stdlib + "
                         "core.electrique)")

    def test_ajouter_import_django_rend_le_verrou_rouge(self):
        """Le cas que la tâche exige de voir rouge, rejoué sur une copie."""
        with tempfile.TemporaryDirectory() as tmp:
            for chemin in _fichiers():
                with open(chemin, "r", encoding="utf-8") as fh:
                    contenu = fh.read()
                cible = os.path.join(tmp, os.path.basename(chemin))
                with open(cible, "w", encoding="utf-8") as fh:
                    fh.write(contenu)
            with open(os.path.join(tmp, "volumes.py"), "a",
                      encoding="utf-8") as fh:
                fh.write("\nimport django  # noqa\n")
            self.assertIn(("volumes.py", "django"), _imports_interdits(tmp))

    def test_aucun_autre_noyau_que_electrique(self):
        fautifs = []
        for chemin in _fichiers():
            with open(chemin, "r", encoding="utf-8") as fh:
                for nom in _imports_source(fh.read(), chemin):
                    if (nom == "core" or nom.startswith("core.")) and not any(
                            nom == r or nom.startswith(r + ".")
                            for r in RACINES_INTERNES):
                        fautifs.append((os.path.basename(chemin), nom))
        self.assertEqual(fautifs, [])

    def test_aucune_io(self):
        fautifs = []
        for chemin in _fichiers():
            with open(chemin, "r", encoding="utf-8") as fh:
                arbre = ast.parse(fh.read(), filename=chemin)
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.Call):
                    continue
                cible = noeud.func
                if isinstance(cible, ast.Name) and cible.id in APPELS_INTERDITS:
                    fautifs.append((os.path.basename(chemin), cible.id))
                elif (isinstance(cible, ast.Attribute)
                      and cible.attr in ATTRIBUTS_INTERDITS):
                    fautifs.append((os.path.basename(chemin), cible.attr))
        self.assertEqual(fautifs, [])

    def test_aucune_globale_mutable(self):
        fautifs = []
        for chemin in _fichiers():
            with open(chemin, "r", encoding="utf-8") as fh:
                arbre = ast.parse(fh.read(), filename=chemin)
            for noeud in arbre.body:
                if not isinstance(noeud, (ast.Assign, ast.AnnAssign)):
                    continue
                if isinstance(noeud.value, (ast.List, ast.Dict, ast.Set)):
                    cibles = ([noeud.target] if isinstance(noeud, ast.AnnAssign)
                              else noeud.targets)
                    noms = [t.id for t in cibles if isinstance(t, ast.Name)
                            and not (t.id.startswith("__")
                                     and t.id.endswith("__"))]
                    if noms:
                        fautifs.append((os.path.basename(chemin), noms))
        self.assertEqual(fautifs, [])


class ReExportsIdentiques(unittest.TestCase):
    """Les anciens chemins pointent sur les MÊMES objets (aucune copie)."""

    def test_le_noyau_s_importe_sans_django(self):
        from core.pompage import hydraulique, selection, volumes
        self.assertTrue(callable(hydraulique.hmt_puits_iteree))
        self.assertTrue(callable(selection.selection_pompe))
        self.assertTrue(callable(volumes.pumping_cycle_yield))
        self.assertEqual(sum(volumes.JOURS_PAR_MOIS), 365)
