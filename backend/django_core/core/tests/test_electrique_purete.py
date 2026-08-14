# -*- coding: utf-8 -*-
"""PV33 — le paquet ``core.electrique`` est un NOYAU PUR (test armé).

Miroir exact de ``test_calepinage_purete.py`` pour le moteur électrique. Ce test
est le second verrou de la pureté (le premier est le contrat import-linter
``electrique-est-un-noyau-pur``). Il analyse l'AST de CHAQUE fichier du paquet et
échoue si :

* un import sort de la liste blanche (stdlib + le paquet lui-même) — ajouter
  ``import django`` rend ce test ROUGE ; le moteur électrique n'a même pas
  besoin de ``numpy`` (le calepinage, lui, en a l'usage) : sa liste blanche est
  donc STRICTEMENT la bibliothèque standard ;
* un appel d'I/O apparaît (``open``, ``os.makedirs``, ``print``…) — le moteur
  retourne des OBJETS et du TEXTE, il n'écrit jamais ;
* une globale MUTABLE de module apparaît (liste/dict/ensemble au niveau module) —
  une table de calibres qu'un appelant peut MUTER rend le moteur non
  parallélisable et non reproductible : les barèmes sont des tuples.

Il ne dépend PAS de Django : ``unittest`` pur, aucune base de données.
"""

import ast
import os
import sys
import unittest

PAQUET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "electrique")

#: Aucune dépendance externe : le moteur électrique est STRICTEMENT stdlib.
DEPENDANCES_AUTORISEES = frozenset()

#: Le paquet peut s'importer lui-même (chemins absolus ``core.electrique.x``).
RACINE_INTERNE = "core.electrique"

#: Appels interdits : le moteur ne fait aucune I/O et n'écrit rien en console.
APPELS_INTERDITS = frozenset({
    "open", "print", "input", "exec", "eval", "compile", "__import__",
})

#: Attributs interdits (``os.makedirs``, ``pathlib.Path.write_text``…).
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
            "unittest", "decimal", "abc", "re", "html", "types"}


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
        self.assertTrue(fichiers, "core/electrique/ ne contient aucun module")

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
            "core/electrique/ doit rester PUR (stdlib seulement) — imports "
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

    def test_aucun_import_d_un_autre_module_de_core(self):
        """Même ``core.calepinage`` est hors périmètre : deux noyaux INDÉPENDANTS.

        Un noyau qui en importe un autre finit par hériter de ses dépendances
        (numpy, matplotlib) et de ses versions : les deux moteurs se versionnent
        séparément, ils ne doivent donc pas se tenir par la main.
        """
        fautifs = []
        for chemin in _fichiers_du_paquet():
            for nom in self._imports(chemin):
                if nom == "core" or (nom.startswith("core.")
                                     and not nom.startswith(RACINE_INTERNE)):
                    fautifs.append((os.path.relpath(chemin, PAQUET), nom))
        self.assertEqual(fautifs, [],
                         "le noyau électrique n'importe aucun autre module de "
                         "core : %r" % (fautifs,))

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
            "globale MUTABLE de module — utiliser un tuple/frozenset : %r"
            % (fautifs,))


class ConstantesNormativesSourcees(unittest.TestCase):
    """Toute constante NORMATIVE cite sa source dans le fichier qui la porte.

    Le moteur publie des calibres et des sections qu'un bureau de contrôle peut
    contester : un fichier de règles qui ne nomme aucune norme est un fichier
    dont personne ne sait défendre les nombres.
    """

    FICHIERS_NORMATIFS = ("protections.py", "cables.py")
    NORMES = ("NF C 15-100", "UTE C 15-712-1", "IEC 62548", "EN 50618",
              "IEC 62930", "IEC 60269")

    def test_les_modules_de_regles_citent_une_norme(self):
        for nom in self.FICHIERS_NORMATIFS:
            chemin = os.path.join(PAQUET, nom)
            if not os.path.exists(chemin):
                continue          # module pas encore construit — rien à exiger
            with open(chemin, "r", encoding="utf-8") as fh:
                contenu = fh.read()
            self.assertTrue(
                any(norme in contenu for norme in self.NORMES),
                "%s ne cite aucune norme — chaque règle doit porter sa source"
                % nom)


class AucunPrixDansLeNoyau(unittest.TestCase):
    """Un prix qui entrerait ici ressortirait dans un dossier technique.

    Les mots traqués sont des NOMS DE CHAMP monétaires, pas des mots français :
    « marge » toute seule désignerait aussi la marge d'une planche (le schéma
    unifilaire en a), donc seule ``marge_commerciale``/``taux_marge`` compte —
    un champ de prix, lui, ne s'écrit pas autrement que ``prix_achat`` /
    ``prix_vente`` / ``montant_*``.
    """

    MOTS_INTERDITS = ("prix_achat", "prix_vente", "taux_marge",
                      "marge_commerciale", "montant_ht", "montant_ttc")

    def test_aucun_champ_de_prix(self):
        fautifs = []
        for chemin in _fichiers_du_paquet():
            with open(chemin, "r", encoding="utf-8") as fh:
                contenu = fh.read()
            for mot in self.MOTS_INTERDITS:
                if mot in contenu:
                    fautifs.append((os.path.relpath(chemin, PAQUET), mot))
        self.assertEqual(fautifs, [],
                         "le moteur électrique ne manipule AUCUN prix : %r"
                         % (fautifs,))


class VersionDuMoteur(unittest.TestCase):
    def test_version_semantique_et_importable_sans_django(self):
        from core.electrique import SCHEMA_VERSION, VERSION_MOTEUR
        from core.electrique.version import compatible, version_tuple

        self.assertEqual(len(version_tuple(VERSION_MOTEUR)), 3)
        self.assertIsInstance(SCHEMA_VERSION, int)
        self.assertTrue(compatible(VERSION_MOTEUR))
        majeur = version_tuple(VERSION_MOTEUR)[0]
        self.assertFalse(compatible("%d.0.0" % (majeur + 1)))

    def test_version_invalide_leve(self):
        from core.electrique.version import version_tuple
        with self.assertRaises(ValueError):
            version_tuple("1.0")


class ContratDeDonnees(unittest.TestCase):
    """Les dataclasses du contrat sont bien IMMUABLES (frozen)."""

    def test_les_specs_sont_frozen(self):
        import dataclasses

        from core.electrique.types import (
            Cable, Chaine, Conformite, EntreeElectrique, GroupePan,
            LigneNomenclature, Protection, Ratio, ResultatElectrique,
            SpecModule, SpecOnduleur,
        )
        for classe in (SpecModule, SpecOnduleur, GroupePan, EntreeElectrique,
                       Chaine, Protection, Cable, LigneNomenclature, Ratio,
                       Conformite, ResultatElectrique):
            self.assertTrue(dataclasses.is_dataclass(classe), classe.__name__)
            self.assertTrue(classe.__dataclass_params__.frozen,
                            "%s doit être frozen" % classe.__name__)

    def test_une_spec_ne_se_mute_pas(self):
        import dataclasses

        from core.electrique.types import SpecModule

        module = SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                            pmax_wc=550.0)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            module.vmp_v = 40.0

    def test_la_physique_de_temperature_est_portee_par_la_spec(self):
        """Voc à froid > Voc STC > Voc à chaud (coefficient négatif)."""
        from core.electrique.types import SpecModule, TEMPERATURE_STC_C

        module = SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                            pmax_wc=550.0)
        self.assertGreater(module.tension_voc_a(-5.0), module.voc_v)
        self.assertAlmostEqual(module.tension_voc_a(TEMPERATURE_STC_C),
                               module.voc_v, places=9)
        self.assertLess(module.tension_vmp_a(70.0), module.vmp_v)

    def test_entree_calcule_ses_totaux(self):
        from core.electrique.types import (
            EntreeElectrique, GroupePan, SpecModule, SpecOnduleur,
        )

        entree = EntreeElectrique(
            module=SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                              pmax_wc=550.0),
            onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=850.0,
                                  v_max_abs=1000.0, i_max_mppt_a=26.0,
                                  ac_kw=10.0),
            groupes=(GroupePan("Sud", 12, 180.0, 15.0),
                     GroupePan("Est", 8, 90.0, 15.0)),
        )
        self.assertEqual(entree.nb_modules, 20)
        self.assertAlmostEqual(entree.puissance_kwc, 11.0, places=6)
        self.assertEqual(entree.tension_reseau_v, 230.0)

    def test_un_ratio_publie_ses_bornes(self):
        from core.electrique.types import Ratio

        ratio = Ratio(nom="AC/DC", valeur=0.8, borne_min=0.75, borne_max=1.0)
        self.assertEqual(ratio.texte, "0,80")
        self.assertIn("0,75-1,00", ratio.fourchette_texte)
