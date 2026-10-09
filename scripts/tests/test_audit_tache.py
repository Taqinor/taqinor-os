"""Tests de scripts/audit_tache.py — le generateur de clauses CALCULEES (AMET80-82).

Stdlib pur (unittest) : aucune base, aucun Django, aucun reseau, aucun docker.
Lancer :
    python -m unittest scripts.tests.test_audit_tache -v

Deux familles :
* les GOLDENS (`scripts/tests/golden/audit_tache/<CAS>.json`) — sorties
  GENEREES par l'outil sur l'arbre reel (ACRM26, ACHT22, AFAC47), cles par
  SYMBOLE, jamais par numero de ligne. Comparaison « rien ne disparait » :
  chaque entree du golden doit encore etre trouvee (un outil qui regresse,
  tronque ou oublie un chainon echoue). Regenerer apres un changement voulu
  du code :  AUDIT_TACHE_GOLDEN=ecrire python -m unittest scripts.tests.test_audit_tache
* des depots JETABLES (git init dans un dossier temporaire) pour le cache, le
  `--narrow` et les regles fines, independants de l'arbre reel.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import audit_tache as at  # noqa: E402

GOLDEN = ROOT / "scripts" / "tests" / "golden" / "audit_tache"
ECRIRE = os.environ.get("AUDIT_TACHE_GOLDEN") == "ecrire"

DJ = "backend/django_core/apps"
# Les commandes rejouees par cas. La sortie projetee (sans lignes) EST le golden.
CAS = {
    "ACRM26": [
        ("appelants", f"{DJ}/crm/views.py::EquipeCommercialeViewSet.get_permissions"),
        ("lecteurs-front", "tranches_facturees"),
        ("ecrivains", "Lead.whatsapp"),
        ("ecrivains", "Lead.telephone_whatsapp"),
    ],
    "ACHT22": [
        ("appelants", f"{DJ}/installations/views/livraison.py::LivraisonViewSet.bon_livraison"),
        ("appelants", f"{DJ}/installations/livraison_pdf.py::bon_livraison_pdf"),
    ],
    "AFAC47": [
        ("appelants", f"{DJ}/ventes/views/facture.py::FactureViewSet.perform_update"),
        ("appelants", f"{DJ}/ventes/utils/echeancier.py::tranches_normalisees"),
    ],
}


def executer(commande: str, argument: str) -> dict:
    return at.COMMANDES[commande](argument)


def projeter(commande: str, resultat: dict) -> dict:
    return at.projection(commande, resultat)


def comparer(test, attendu: dict, obtenu: dict, contexte: str):
    """Rien du golden ne disparait : listes incluses, compteurs >=."""
    for cle, valeur in attendu.items():
        recu = obtenu.get(cle)
        if isinstance(valeur, list):
            manquants = sorted(set(valeur) - set(recu or []))
            test.assertFalse(manquants, f"{contexte} [{cle}] : disparus {manquants}")
        elif isinstance(valeur, int) and not isinstance(valeur, bool):
            test.assertGreaterEqual(recu, valeur, f"{contexte} [{cle}]")
        else:
            test.assertEqual(recu, valeur, f"{contexte} [{cle}]")


class _Golden:
    _memo: dict = {}

    @classmethod
    def charger(cls, cas: str) -> dict:
        chemin = GOLDEN / f"{cas}.json"
        if ECRIRE:
            sortie = {}
            for commande, argument in CAS[cas]:
                sortie[f"{commande} {argument}"] = projeter(commande, cls.sortie(commande, argument))
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(json.dumps({"cas": cas, "commandes": sortie}, ensure_ascii=False,
                                         indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return json.loads(chemin.read_text(encoding="utf-8"))

    @classmethod
    def sortie(cls, commande: str, argument: str) -> dict:
        cle = (commande, argument)
        if cle not in cls._memo:
            cls._memo[cle] = executer(commande, argument)
        return cls._memo[cle]


class GoldenTests(unittest.TestCase):
    def test_chaque_golden_est_retrouve(self):
        for cas in CAS:
            golden = _Golden.charger(cas)
            for libelle, attendu in golden["commandes"].items():
                commande, argument = libelle.split(" ", 1)
                obtenu = projeter(commande, _Golden.sortie(commande, argument))
                with self.subTest(cas=cas, commande=libelle):
                    comparer(self, attendu, obtenu, f"{cas} {libelle}")

    def test_goldens_sans_numero_de_ligne(self):
        for cas in CAS:
            texte = (GOLDEN / f"{cas}.json").read_text(encoding="utf-8")
            self.assertNotRegex(texte, r"\.(?:py|jsx?|mjs):\d", cas)


class AppelantsTests(unittest.TestCase):
    def test_lecteurs_front_trouve_devisrow_et_devistab(self):
        # R3_V3 : DevisRow.jsx:538 ET DevisTab.jsx:1001. Arbre du 09/10 :
        # DevisTab lit desormais `porte_facturation` (ATOT31) — le golden dit
        # ce que l'arbre dit ; DevisRow, lui, doit etre trouve avec ses lignes.
        sortie = _Golden.sortie("lecteurs-front", "tranches_facturees")
        fichiers = {e["fichier"]: e["lignes"] for e in sortie["lecteurs"]}
        devisrow = "frontend/src/pages/ventes/devisList/DevisRow.jsx"
        self.assertIn(devisrow, fichiers)
        self.assertTrue(fichiers[devisrow])
        golden = _Golden.charger("ACRM26")["commandes"]["lecteurs-front tranches_facturees"]
        comparer(self, golden, projeter("lecteurs-front", sortie), "lecteurs-front")
        self.assertIn("DevisRow.jsx", sortie["texte"])

    def test_thunk_redux_amene_facture_form(self):
        # ATOT9 : le PUT de FactureForm passe par le thunk `updateFacture`.
        sortie = _Golden.sortie(
            "appelants", f"{DJ}/ventes/views/facture.py::FactureViewSet.perform_update")
        form = "frontend/src/pages/ventes/FactureForm.jsx"
        self.assertIn(form, sortie["ecrans"])
        # mutant « ignorer les thunks » : FactureForm n'a AUCUN chemin direct.
        self.assertIn("ventesSlice.js::updateFacture", sortie["chemins"][form])

    def test_route_bl_zero_ecran(self):
        sortie = _Golden.sortie(
            "appelants", f"{DJ}/installations/views/livraison.py::LivraisonViewSet.bon_livraison")
        self.assertTrue(sortie["routes"], "la route BL doit etre resolue")
        self.assertEqual(sortie["ecrans"], [])
        self.assertIn("0 écran", sortie["texte"])

    def test_route_plus_specifique_gagne_mes_equipes_card(self):
        # Defaut R3_V3 : `/crm/equipes/statistiques/` n'est PAS servi par le
        # ViewSet (route `path()` plus specifique) : MesEquipesCard n'est pas un appelant.
        sortie = _Golden.sortie(
            "appelants", f"{DJ}/crm/views.py::EquipeCommercialeViewSet.get_permissions")
        tout = " ".join(sortie["ecrans"] + [w["fichier"] for w in sortie["wrappers"]]
                        + sortie["intermediaires"])
        self.assertNotIn("MesEquipesCard", tout)
        self.assertIn("frontend/src/pages/parametres/EquipesCommercialesSection.jsx",
                      sortie["ecrans"])

    def test_appelants_python_au_format_fichier_symbole(self):
        sortie = _Golden.sortie("appelants", f"{DJ}/ventes/utils/echeancier.py::tranches_normalisees")
        self.assertTrue(sortie["python"])
        for appelant in sortie["python"]:
            self.assertRegex(appelant["symbole"], r"^backend/.+\.py::[\w.<>]+$")

    def test_ecrivains_suivent_setattr_dynamique(self):
        sortie = _Golden.sortie("ecrivains", "Lead.whatsapp")
        symboles = {e["symbole"].split("::")[1] for e in sortie["ecrivains"]}
        # Meta, fusion (`_MERGE_FILL_FIELDS` + setattr), re-semis Odoo (`_FILL_FIELDS`).
        self.assertIn("_apply_meta_form_extras", symboles)
        self.assertTrue(any(e["via"].startswith("setattr dynamique") for e in sortie["ecrivains"]))


def _git(racine, *args):
    subprocess.run(["git", *args], cwd=racine, check=True, capture_output=True)


class DepotJetable:
    """git init + quelques fichiers Python : cache et `--narrow` isoles."""

    def __init__(self, fichiers: dict):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        for rel, contenu in fichiers.items():
            chemin = self.racine / rel
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(contenu, encoding="utf-8")
        _git(self.racine, "init", "-q")
        _git(self.racine, "add", "-A")
        _git(self.racine, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
        self.cache = tempfile.TemporaryDirectory()

    def fermer(self):
        self.tmp.cleanup()
        self.cache.cleanup()


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.depot = DepotJetable({
            "backend/app/a.py": "def f():\n    return 1\n\n\nclass K:\n    def m(self):\n        return f()\n",
            "backend/app/b.py": "from app.a import f\n\n\ndef g():\n    return f()\n",
            "backend/app/migrations/0001_x.py": "def f():\n    return 1\n",
            "scripts/c.py": "def h():\n    return 2\n",
        })
        self.addCleanup(self.depot.fermer)

    def test_narrow_restreint_par_git_grep(self):
        idx = at.index(narrow=r"\bg\b", racine=self.depot.racine, cache_dir=self.depot.cache.name)
        self.assertEqual(sorted(idx), ["backend/app/b.py"])

    def test_index_complet_ignore_les_migrations_et_qualifie(self):
        idx = at.index(racine=self.depot.racine, cache_dir=self.depot.cache.name)
        self.assertEqual(sorted(idx), ["backend/app/a.py", "backend/app/b.py", "scripts/c.py"])
        noms = [d.qualname for d in idx["backend/app/a.py"]["defs"]]
        self.assertEqual(noms, ["f", "K", "K.m"])

    def test_cache_disque_par_sha_puis_invalide(self):
        cache = self.depot.cache.name
        at.index(racine=self.depot.racine, cache_dir=cache)
        self.assertEqual(len(list(Path(cache).glob("*.pickle"))), 1)
        at.index(racine=self.depot.racine, cache_dir=cache)
        self.assertEqual(len(list(Path(cache).glob("*.pickle"))), 1, "chaud = meme cle")
        (self.depot.racine / "scripts" / "c.py").write_text("def h2():\n    return 3\n", encoding="utf-8")
        at._ETATS.clear()  # l'etat git est memoise par process (une commande = un process)
        idx = at.index(racine=self.depot.racine, cache_dir=cache)
        self.assertEqual([d.qualname for d in idx["scripts/c.py"]["defs"]], ["h2"])

    def test_corps_identiques_meme_empreinte(self):
        idx = at.index(racine=self.depot.racine, cache_dir=self.depot.cache.name)
        empreintes = {d.qualname: d.empreinte for f in idx.values() for d in f["defs"]}
        self.assertNotEqual(empreintes["f"], empreintes["h"])


if __name__ == "__main__":
    unittest.main()
