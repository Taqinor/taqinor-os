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
FACTURE = f"{DJ}/ventes/views/facture.py::FactureViewSet.perform_update"
# Les commandes rejouees par cas. La sortie projetee (sans lignes) EST le golden.
CAS = {
    "ACRM26": [
        ("appelants", f"{DJ}/crm/views.py::EquipeCommercialeViewSet.get_permissions"),
        ("lecteurs-front", "tranches_facturees"),
        ("ecrivains", "Lead.whatsapp"),
        ("ecrivains", "Lead.telephone_whatsapp"),
        ("assertions-existantes", f"{DJ}/crm/views.py::EquipeCommercialeViewSet.get_permissions"),
        ("listes-figees", f"{DJ}/crm/services.py"),
        ("jumeaux", f"{DJ}/crm/views.py::EquipeCommercialeViewSet.get_permissions"),
        ("jumeaux", f"{DJ}/crm/views.py::SiteProfileViewSet.get_permissions"),
        ("emplacement", f"{DJ}/crm/services.py::merge_leads"),
    ],
    "ACHT22": [
        ("appelants", f"{DJ}/installations/views/livraison.py::LivraisonViewSet.bon_livraison"),
        ("appelants", f"{DJ}/installations/livraison_pdf.py::bon_livraison_pdf"),
        ("assertions-existantes", f"{DJ}/installations/views/livraison.py::LivraisonViewSet.bon_livraison"),
        ("lecteurs-sample", "roof_layout_v2.schema.json"),
        ("test-canonique", f"{DJ}/installations/services.py::recreer_nomenclature_ordre_assemblage"),
    ],
    "AFAC47": [
        ("appelants", f"{DJ}/ventes/views/facture.py::FactureViewSet.perform_update"),
        ("appelants", f"{DJ}/ventes/utils/echeancier.py::tranches_normalisees"),
        ("assertions-existantes", f"{DJ}/ventes/recouvrement.py::ParametrageRelanceClientViewSet.perform_update"),
        ("assertions-existantes", f"{FACTURE} --anciens Montant figé"),
        ("listes-figees", f"{DJ}/ventes/recouvrement.py"),
    ],
}


def executer(commande: str, argument: str) -> dict:
    """`argument` peut porter `--anciens <litteral>` (comme la CLI)."""
    cible, _, ancien = argument.partition(" --anciens ")
    options = {"anciens": [ancien]} if ancien else {}
    return at.COMMANDES[commande](cible, **options)


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


class AssertionsTests(unittest.TestCase):
    def test_ancien_litteral_trouve_le_test_qui_le_fige(self):
        # Given de la tache : `--anciens "Montant fige"` sur FactureViewSet.perform_update.
        sortie = _Golden.sortie(
            "assertions-existantes",
            f"{DJ}/ventes/views/facture.py::FactureViewSet.perform_update --anciens Montant figé")
        par_litteral = [a for a in sortie["assertions"] if "littéral « Montant figé »" in a["via"]]
        self.assertTrue(any(a["test"].startswith(
            f"{DJ}/facturation/tests/test_atot_montants_figes.py::") for a in par_litteral), sortie["texte"])
        for a in sortie["assertions"]:
            self.assertEqual(a["verdict"], "")
            self.assertRegex(a["test"], r"^\S+\.(?:py|jsx?|mjs|tsx?|json)(?:::.+)?$")
        # Golden ACRM26 (R3_V3) : les tests de tests_zsal3_equipe_crud.py et leurs codes 201/200/404.
        acrm = _Golden.sortie("assertions-existantes",
                              f"{DJ}/crm/views.py::EquipeCommercialeViewSet.get_permissions")
        codes = {c for a in acrm["assertions"] if "tests_zsal3_equipe_crud.py::" in a["test"] for c in a["codes"]}
        self.assertTrue({201, 200, 404} <= codes, acrm["texte"])

    def test_asec28_patch_seulement(self):
        sortie = _Golden.sortie(
            "assertions-existantes", f"{DJ}/ventes/recouvrement.py::ParametrageRelanceClientViewSet.perform_update")
        asec28 = [a for a in sortie["assertions"] if "test_xfac_asec28" in a["test"]]
        self.assertTrue(asec28, sortie["texte"])
        self.assertEqual({v for a in asec28 for v in a["verbes"]}, {"PATCH"})

    def test_lecteurs_sample_trouve_tests_et_front(self):
        sortie = _Golden.sortie("lecteurs-sample", "roof_layout_v2.schema.json")
        categories = {x["categorie"] for x in sortie["lecteurs"]}
        self.assertIn("test-py", categories)
        self.assertGreaterEqual(len(sortie["lecteurs"]), 10, sortie["texte"])

    def test_listes_figees_nomment_garde_type_et_regeneration(self):
        sortie = _Golden.sortie("listes-figees", f"{DJ}/crm/services.py")
        gardes = {g["garde"]: g for g in sortie["gardes"]}
        self.assertIn("scripts/check_get_or_create.py", gardes)
        g = gardes["scripts/check_get_or_create.py"]
        self.assertEqual(g["type_de_cle"], "par_symbole")
        self.assertTrue(g["declare"])
        self.assertIn("--write", g["regeneration"])

    def test_type_de_cle_declare_par_les_quatre_gardes(self):
        for garde in ("check_get_or_create", "check_naive_datetime", "check_duplicats_litteraux",
                      "check_taches_cablage"):
            texte = (ROOT / "scripts" / f"{garde}.py").read_text(encoding="utf-8")
            self.assertRegex(texte, r'(?m)^TYPE_DE_CLE = "par_(?:ligne|symbole)"(?:  #.*)?$', garde)

    def test_type_de_cle_absent_est_deduit(self):
        depot = DepotJetable({
            "scripts/check_x.py": '"""garde."""\nBASE = "x_allow.txt"\n# --write-baseline\n',
            "scripts/x_allow.txt": "backend/app/a.py:12\n",
            "backend/app/a.py": "def f():\n    return 1\n",
        })
        self.addCleanup(depot.fermer)
        sortie = at.listes_figees("backend/app/a.py", racine=depot.racine)
        g = sortie["gardes"][0]
        self.assertEqual((g["garde"], g["type_de_cle"], g["declare"]), ("scripts/check_x.py", "par_ligne", False))
        self.assertIn("TYPE_DE_CLE absent (déduit : par_ligne)", sortie["texte"])


class JumeauxTests(unittest.TestCase):
    def test_get_permissions_rend_105_corps_identiques_sans_troncature(self):
        # R3_V3 : 105 corps identiques = le corps `IsAnyRole` / `IsResponsableOrAdmin` qu'avait
        # EquipeCommercialeViewSet AVANT ACRM26 ; ACRM26 l'a passe a `IsAdminRole` (groupe de 17).
        # On rejoue donc le fait sur un porteur ACTUEL de ce corps (meme fichier crm/views.py).
        sortie = _Golden.sortie("jumeaux", f"{DJ}/crm/views.py::SiteProfileViewSet.get_permissions")
        identiques = sortie["corps_identiques"]
        self.assertGreaterEqual(len(identiques), 105)          # 112 au 09/10 (docstrings ignorees)
        self.assertEqual(sortie["nb_corps_identiques"], len(identiques))
        self.assertEqual(sum(j["cible"] for j in identiques), 1)
        for j in identiques:                                    # aucune troncature dans le texte
            self.assertIn(j["symbole"].split("::", 1)[1], sortie["texte"])
        self.assertRegex(sortie["texte"], r"\(gen [0-9a-f]{9} .+::SiteProfileViewSet\.get_permissions#[0-9a-f]{8}\)")
        acrm26 = _Golden.sortie("jumeaux", f"{DJ}/crm/views.py::EquipeCommercialeViewSet.get_permissions")
        self.assertEqual(acrm26["nb_corps_identiques"], len(acrm26["corps_identiques"]))

    def test_emplacement_mur_et_spl_qui_deplace(self):
        sortie = _Golden.sortie("emplacement", f"{DJ}/crm/services.py::merge_leads")
        self.assertTrue(sortie["mur"])
        self.assertGreaterEqual(sortie["lignes"], 2000)
        self.assertIn("SPL22", sortie["spl"])                   # « Déplacer la fusion de leads … »
        self.assertIn("@after: SPL22", sortie["texte"])

    def test_test_canonique_classe_le_module_kitting_en_premier(self):
        sortie = _Golden.sortie(
            "test-canonique", f"{DJ}/installations/services.py::recreer_nomenclature_ordre_assemblage")
        self.assertEqual(sortie["modules"][0]["module"], f"{DJ}/installations/tests_fg328_kitting.py")
        self.assertTrue(sortie["modules"][0]["id_de_tache"])

    def test_inspecter_est_l_api_exportee(self):
        self.assertTrue(callable(at.inspecter) and callable(at.index))

    def test_verifier_tampon_perime_exit_1(self):
        depot = DepotJetable({"backend/app/a.py": "def f():\n    return 1\n"})
        self.addCleanup(depot.fermer)
        _, _, d = at.resoudre("backend/app/a.py::f", depot.racine)
        frais = f"(gen abcdef123 backend/app/a.py::f#{d.empreinte[:8]})"
        (depot.racine / "docs").mkdir()
        (depot.racine / "docs" / "PLAN.md").write_text(
            f"- [ ] ZZT1 — **x** : {frais} Files: `backend/app/a.py`\n"
            "- [ ] ZZT2 — **y** : (gen abcdef123 backend/app/a.py::f#00000000) Files: `backend/app/a.py`\n",
            encoding="utf-8")
        sauvegarde = at.ctc.ROOT
        at.ctc.ROOT = depot.racine
        self.addCleanup(setattr, at.ctc, "ROOT", sauvegarde)
        self.assertFalse(at.verifier("ZZT1", racine=depot.racine)["perimee"])
        self.assertTrue(at.verifier("ZZT2", racine=depot.racine)["perimee"])
        (depot.racine / "backend" / "app" / "a.py").write_text("def f():\n    return 2\n", encoding="utf-8")
        self.assertTrue(at.verifier("ZZT1", racine=depot.racine)["perimee"])
        self.assertEqual(at.main(["--verifier", "ZZT2", "--racine", str(depot.racine)]), 1)

    def test_clause_texte_pret_a_coller(self):
        depot = DepotJetable({"backend/app/a.py": "def f():\n    return 1\n"})
        self.addCleanup(depot.fermer)
        sortie = at.emplacement("backend/app/a.py::f", racine=depot.racine)
        self.assertTrue(sortie["texte"].startswith("Emplacement : `backend/app/a.py::f` (3 l."))
        self.assertEqual(at.CLAUSES["emplacement"], "emplacement")


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
