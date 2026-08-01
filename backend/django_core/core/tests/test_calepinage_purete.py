# -*- coding: utf-8 -*-
"""AOF33 — le paquet ``core.calepinage`` est un NOYAU PUR (test armé).

Ce test est le second verrou de la pureté (le premier est le contrat
import-linter ``calepinage-est-un-noyau-pur``). Il analyse l'AST de CHAQUE
fichier du paquet et échoue si :

* un import sort de la liste blanche (stdlib + ``numpy`` + le paquet lui-même) —
  ajouter ``import django`` rend ce test ROUGE ;
* un appel d'I/O apparaît (``open``, ``os.makedirs``, ``print``…) — le moteur
  retourne des OCTETS, il n'écrit jamais ;
* une globale MUTABLE de module apparaît (liste/dict/ensemble au niveau module) —
  la reconfiguration par mutation de globale est précisément ce qui rendait les
  scripts d'origine non parallélisables.

Il ne dépend PAS de Django : ``unittest`` pur, aucune base de données.
"""

import ast
import os
import sys
import unittest

PAQUET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "calepinage")

#: Seules dépendances externes autorisées. ``numpy`` est déjà en production.
DEPENDANCES_AUTORISEES = frozenset({"numpy"})

#: Le paquet peut s'importer lui-même (chemins absolus ``core.calepinage.x``).
RACINE_INTERNE = "core.calepinage"

#: Appels interdits : le moteur ne fait aucune I/O et n'écrit rien en console.
APPELS_INTERDITS = frozenset({
    "open", "print", "input", "exec", "eval", "compile", "__import__",
})

#: Attributs interdits (``os.makedirs``, ``sys.stdout.write``…).
ATTRIBUTS_INTERDITS = frozenset({
    "makedirs", "mkdir", "remove", "unlink", "rmtree", "system", "popen",
    "savefig", "write_text", "write_bytes",
})


def _fichiers_du_paquet():
    for racine, _dirs, fichiers in os.walk(PAQUET):
        for nom in sorted(fichiers):
            if nom.endswith(".py"):
                yield os.path.join(racine, nom)


def _modules_stdlib():
    noms = getattr(sys, "stdlib_module_names", None)
    if noms:
        return set(noms)
    # Repli très conservateur (Python < 3.10) : le paquet n'utilise que ceci.
    return {"math", "json", "hashlib", "dataclasses", "typing", "enum",
            "itertools", "functools", "bisect", "collections", "os", "sys",
            "unittest", "random", "decimal", "abc", "re"}


STDLIB = _modules_stdlib()


def _racine(nom_module):
    return (nom_module or "").split(".")[0]


class ImportsDuPaquet(unittest.TestCase):
    """Analyse AST — aucune importation du paquet n'est faite ici."""

    def _imports(self, chemin):
        with open(chemin, "r", encoding="utf-8") as fh:
            arbre = ast.parse(fh.read(), filename=chemin)
        trouves = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                for alias in noeud.names:
                    trouves.append(alias.name)
            elif isinstance(noeud, ast.ImportFrom):
                if noeud.level:            # import relatif : reste interne
                    continue
                trouves.append(noeud.module or "")
        return trouves

    def test_le_paquet_existe_et_a_des_fichiers(self):
        fichiers = list(_fichiers_du_paquet())
        self.assertTrue(fichiers, "core/calepinage/ ne contient aucun module")

    def test_aucun_import_hors_liste_blanche(self):
        interdits = []
        for chemin in _fichiers_du_paquet():
            for nom in self._imports(chemin):
                if nom == RACINE_INTERNE or nom.startswith(RACINE_INTERNE + "."):
                    continue
                racine = _racine(nom)
                if racine in STDLIB or racine in DEPENDANCES_AUTORISEES:
                    continue
                interdits.append((os.path.relpath(chemin, PAQUET), nom))
        self.assertEqual(
            interdits, [],
            "core/calepinage/ doit rester PUR (stdlib + numpy) — imports "
            "interdits : %r" % (interdits,))

    def test_aucun_import_django_ni_rest_framework(self):
        """Verrou explicite et NOMMÉ (le cas que la tâche exige de voir rouge)."""
        fautifs = []
        for chemin in _fichiers_du_paquet():
            for nom in self._imports(chemin):
                if _racine(nom) in {"django", "rest_framework", "celery",
                                    "apps", "authentication"}:
                    fautifs.append((os.path.relpath(chemin, PAQUET), nom))
        self.assertEqual(fautifs, [], "import Django/DRF/apps dans le noyau pur")

    def test_aucune_io(self):
        fautifs = []
        for chemin in _fichiers_du_paquet():
            with open(chemin, "r", encoding="utf-8") as fh:
                arbre = ast.parse(fh.read(), filename=chemin)
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.Call):
                    continue
                cible = noeud.func
                if isinstance(cible, ast.Name) and cible.id in APPELS_INTERDITS:
                    fautifs.append((os.path.relpath(chemin, PAQUET), cible.id))
                elif (isinstance(cible, ast.Attribute)
                      and cible.attr in ATTRIBUTS_INTERDITS):
                    fautifs.append((os.path.relpath(chemin, PAQUET), cible.attr))
        self.assertEqual(fautifs, [], "le moteur ne fait AUCUNE I/O : %r" % (fautifs,))

    def test_aucune_globale_mutable(self):
        """Une liste/dict/ensemble au niveau module = reconfiguration par mutation."""
        fautifs = []
        for chemin in _fichiers_du_paquet():
            with open(chemin, "r", encoding="utf-8") as fh:
                arbre = ast.parse(fh.read(), filename=chemin)
            for noeud in arbre.body:
                if not isinstance(noeud, (ast.Assign, ast.AnnAssign)):
                    continue
                valeur = noeud.value
                if isinstance(valeur, (ast.List, ast.Dict, ast.Set)):
                    cibles = ([noeud.target] if isinstance(noeud, ast.AnnAssign)
                              else noeud.targets)
                    noms = [t.id for t in cibles if isinstance(t, ast.Name)
                            and not (t.id.startswith("__") and t.id.endswith("__"))]
                    if noms:
                        fautifs.append((os.path.relpath(chemin, PAQUET), noms))
        self.assertEqual(
            fautifs, [],
            "globale MUTABLE de module — utiliser un tuple/frozenset ou un "
            "Parametres immuable : %r" % (fautifs,))


class VersionDuMoteur(unittest.TestCase):
    def test_version_semantique_et_importable_sans_django(self):
        from core.calepinage import SCHEMA_VERSION, VERSION_MOTEUR
        from core.calepinage.version import compatible, version_tuple

        self.assertEqual(len(version_tuple(VERSION_MOTEUR)), 3)
        self.assertIsInstance(SCHEMA_VERSION, int)
        self.assertTrue(compatible(VERSION_MOTEUR))
        majeur = version_tuple(VERSION_MOTEUR)[0]
        self.assertFalse(compatible("%d.0.0" % (majeur + 1)))

    def test_version_invalide_leve(self):
        from core.calepinage.version import version_tuple
        with self.assertRaises(ValueError):
            version_tuple("1.0")
