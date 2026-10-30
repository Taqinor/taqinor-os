"""Tests de scripts/check_parcours.py et scripts/rejouer_parcours.py (AMET98, C-AMET-025).

Stdlib pur (unittest), aucun Django, aucune base, aucun docker : dépôt jetable ; le rejeu
lui-même tourne dans le conteneur (sonde.py), ici tout ce qui l'entoure (conteneur simulé).
    python -m unittest scripts.tests.test_check_parcours -v
"""
import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_acceptation as cacc  # noqa: E402 — après sys.path/setup() (D-ENF22)
import check_parcours  # noqa: E402 — après sys.path/setup() (D-ENF22)
import parcours_tables as cp  # noqa: E402 — après sys.path/setup() (D-ENF22)
import rejouer_parcours as rp  # noqa: E402 — après sys.path/setup() (D-ENF22)
import sonde  # noqa: E402 — après sys.path/setup() (D-ENF22)
from scripts.tests.test_audit_tache import DepotActif, DepotJetable  # noqa: E402 — dépôt jetable AMET80


VUES = ("class FactureViewSet:\n    def payer(self):\n        return 1\n\n\n"
        "def emettre():\n    pass\n")
MODELES = "class Facture:\n    statut = 'x'\n"

ETAPE = {  # schéma §D.1 : contrôlé par core/parcours.problemes_de_la_table
    "id": "PA9.01", "nom": "Payer", "proprietaire": "fac",
    "declencheur": {"type": "clic", "source": "apps/fac/views.py::FactureViewSet.payer"},
    "fonction_entree": "apps/fac/views.py::FactureViewSet.payer",
    "checkpoint": {"modifiable": True, "champs": ["statut"], "persistance": "apps/fac/models.py::Facture.statut"},
    "regle_aval": [{"type": "refus_409", "detail": "déjà payée"}],
    "taches": ["AFAC1"],
}
ETAPE_B = {  # dialecte `libelle` / `regles_aval` (AMET13/15/18/24)
    "id": "payer", "libelle": "Payer",
    "declencheur": {"type": "http", "source": "apps/fac/views.py::FactureViewSet.payer"},
    "fonction_entree": "apps/fac/views.py::emettre",
    "checkpoint": {"persistance": "apps/fac/models.py::Facture"},
    "regles_aval": [{"regle": "refus si déjà payée", "source": "apps/fac/views.py::emettre"}],
    "taches": ["AFAC1"],
}
MANQUANTE = {
    "id": "PA9.02", "libelle": "Relance", "manquante": True,
    "declencheur": {"manquant": True}, "fonction_entree": {"manquant": True},
    "checkpoint": {"persistance": "apps/fac/models.py::Facture"},
    "regles_aval": [{"regle": "émetteur présent", "source": "apps/fac/views.py::emettre"}],
}


def _table(*etapes, portes=True):
    t = {"parcours": "PA9", "pilote": "fac", "chemins_relatifs_a": "backend/django_core",
         "etapes": [copy.deepcopy(e) for e in etapes]}
    if portes:
        t["portes"] = [{"id": "p1", "source": "apps/fac/views.py::emettre"}]
    return t


class _Depot:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        app = self.racine / "backend" / "django_core" / "apps" / "fac"
        (app / "parcours").mkdir(parents=True)
        (app / "views.py").write_text(VUES, encoding="utf-8")
        (app / "models.py").write_text(MODELES, encoding="utf-8")

    def ecrire(self, table):
        (self.racine / "backend/django_core/apps/fac/parcours/PA9.json").write_text(
            json.dumps(table, ensure_ascii=False), encoding="utf-8")


def _echecs(table):
    d = _Depot()
    try:
        return cp.verifier_table("PA9.json", table, d.racine)
    finally:
        d.tmp.cleanup()


class ParcoursTests(unittest.TestCase):
    """AMET98 — `parcours_tables.py`, exécuté par `check_parcours.py` (stage-names)."""

    def test_etape_sans_regle_aval_echoue_et_symbole_resolu_passe(self):
        echecs, _ = _echecs(_table(ETAPE))
        self.assertEqual(echecs, [])
        sans = copy.deepcopy(ETAPE)
        sans["regle_aval"] = []
        echecs, _ = _echecs(_table(sans))
        self.assertTrue(any("règle aval" in e for e in echecs), echecs)

    def test_etape_sans_checkpoint_echoue(self):
        for cle in ("checkpoint", "declencheur", "fonction_entree"):
            with self.subTest(cle=cle):
                sans = copy.deepcopy(ETAPE)
                del sans[cle]
                echecs, _ = _echecs(_table(sans))
                self.assertTrue(any(cle in e for e in echecs), echecs)

    def test_symbole_introuvable_echoue(self):
        faux = copy.deepcopy(ETAPE)
        faux["fonction_entree"] = "apps/fac/views.py::FactureViewSet.rembourser"
        echecs, _ = _echecs(_table(faux))
        self.assertTrue(any("rembourser" in e for e in echecs), echecs)
        faux = copy.deepcopy(ETAPE)
        faux["regle_aval"] = [{"type": "inventee"}]
        echecs, _ = _echecs(_table(faux))
        self.assertTrue(any("inventee" in e for e in echecs), echecs)

    def test_entree_qui_n_est_pas_une_reference_echoue(self):
        for etape in (ETAPE, ETAPE_B):
            deux = copy.deepcopy(etape)
            deux["fonction_entree"] = etape["fonction_entree"] + " puis apps/fac/views.py::emettre"
            echecs, _ = _echecs(_table(deux))
            self.assertTrue(any("fonction_entree" in e and "fichier::symbole" in e for e in echecs), echecs)

    def test_etape_manquante_rapportee_jamais_resolue(self):
        echecs, manquantes = _echecs(_table(ETAPE_B, MANQUANTE))
        self.assertEqual((echecs, manquantes), ([], ["PA9.02"]))
        mal = copy.deepcopy(MANQUANTE)
        mal["fonction_entree"] = "apps/fac/views.py::emettre"
        echecs, _ = _echecs(_table(ETAPE_B, mal))
        self.assertTrue(any("manquante" in e for e in echecs), echecs)

    def test_dialecte_regles_aval_meme_exigences(self):
        for cle in ("checkpoint", "declencheur", "fonction_entree", "regles_aval"):
            with self.subTest(cle=cle):
                sans = copy.deepcopy(ETAPE_B)
                del sans[cle]
                echecs, _ = _echecs(_table(sans))
                self.assertTrue(echecs, cle)
        faux = copy.deepcopy(ETAPE_B)
        faux["regles_aval"][0]["source"] = "apps/fac/views.py::absente"
        echecs, _ = _echecs(_table(faux))
        self.assertTrue(any("absente" in e for e in echecs), echecs)

    def test_symbole_imbrique_resolu_par_l_index_amet80(self):
        imbrique = copy.deepcopy(ETAPE)
        imbrique["fonction_entree"] = "apps/fac/views.py::creer._create"
        d = _Depot()
        self.addCleanup(d.tmp.cleanup)
        (d.racine / "backend/django_core/apps/fac/views.py").write_text(
            VUES + "\n\ndef creer():\n    try:\n        def _create():\n            pass\n    finally:\n        pass\n",
            encoding="utf-8")
        self.assertEqual(cp.verifier_table("PA9.json", _table(imbrique), d.racine)[0], [])

    def test_portes_vides_echouent_sauf_dette_gelee_qui_ne_fait_que_retrecir(self):
        for etape in (ETAPE, ETAPE_B):
            echecs, _ = _echecs(_table(etape, portes=False))
            self.assertTrue(any("portes" in e for e in echecs), echecs)
        cp.SANS_PORTES_GELEES.add("PA9")
        try:
            self.assertEqual(_echecs(_table(ETAPE_B, portes=False))[0], [])
            echecs, _ = _echecs(_table(ETAPE_B))
            self.assertTrue(any("gelée" in e for e in echecs), echecs)
        finally:
            cp.SANS_PORTES_GELEES.discard("PA9")

    def test_main_sur_depot_jetable(self):
        d = _Depot()
        self.addCleanup(d.tmp.cleanup)
        d.ecrire(_table(ETAPE))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cp.verifier_tout(racine=d.racine), 0)
        self.assertIn("1 table(s)", out.getvalue())
        sans = copy.deepcopy(ETAPE)
        del sans["checkpoint"]
        d.ecrire(_table(sans))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cp.verifier_tout(racine=d.racine), 1)
        self.assertIn("ÉCHEC", out.getvalue())

    def test_tables_reelles_vertes_par_check_parcours(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = check_parcours.main([])
        self.assertEqual(code, 0, out.getvalue())

    def test_check_parcours_echoue_sur_une_table_invalide(self):
        """Mutant : accepter une étape sans checkpoint ⇒ ce test échoue."""
        d = _Depot()
        self.addCleanup(d.tmp.cleanup)
        sans = copy.deepcopy(ETAPE)
        del sans["checkpoint"]
        d.ecrire(_table(sans))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(check_parcours.main(["--racine", str(d.racine)]), 1)
        self.assertIn("ÉCHEC PA9", out.getvalue())
        self.assertIn("checkpoint", out.getvalue())
        self.assertGreaterEqual(len(cp.charger_tables(ROOT)), 7)


class RejeuTests(unittest.TestCase):
    """Le rejeu lui-même tourne dans le conteneur (sonde.py) : ici, tout ce qui l'entoure."""

    def _resultats(self, verdict_9_01="PASS"):
        oracles = {o: "NA" for o in cacc.ORACLES}
        oracles.update({"1": "PASS", "2": "PASS"})
        return [{"id": "payer", "joue": True, "appel": "POST /api/django/fac/1/payer/ -> 200",
                 "oracles": oracles, "parcours": {"auto": "NA", "checkpoint": "PASS", "aval": "PASS"},
                 "notes": "", "verdict": verdict_9_01}]

    def test_etapes_d_enregistrement_conformes_au_contrat_amet88(self):
        table = _table(ETAPE_B, MANQUANTE, dict(ETAPE_B, id="PA9.03", taches=[]))
        res = self._resultats() + [dict(self._resultats()[0], id="PA9.03")]
        etapes, ignorees = rp.etapes_enregistrement(table, res)
        self.assertEqual([e["id"] for e in etapes], ["payer"])
        self.assertTrue(all(cacc._etape_complete(e) for e in etapes))
        self.assertEqual(etapes[0]["taches"], ["AFAC1"])
        self.assertIn("PA9.02", " ".join(ignorees))   # manquante : rapportée, jamais jouée
        self.assertIn("PA9.03", " ".join(ignorees))   # sans tâche : jouée, rien à couvrir

    def test_oracle_de_parcours_en_echec_fait_tomber_l_etape(self):
        res = self._resultats()
        res[0]["parcours"]["aval"] = "FAIL"
        etapes, _ = rp.etapes_enregistrement(_table(ETAPE_B), res)
        self.assertEqual(etapes[0]["verdict"], "FAIL")

    def test_programme_dans_une_transaction_annulee(self):
        prog = rp.programme(_table(ETAPE_B), {"modele": "fac.Facture", "enregistrement": "1"}, 60)
        self.assertIn("set_rollback(True)", prog)
        self.assertIn(rp.MARQUE, prog)

    def test_source_envoyee_au_conteneur_autonome(self):
        """Les fonctions envoyées en ligne ne lisent aucun nom du module hors du programme lui-même."""
        import builtins
        ns = {}
        source = rp.EN_TETE_CONTENEUR + "\n\n".join(rp.inspect.getsource(f) for f in rp._CONTENEUR)
        exec(compile(source, "conteneur", "exec"), ns)
        self.assertIn("_jouer", ns)

        def noms(code):
            yield from code.co_names
            for c in code.co_consts:
                if hasattr(c, "co_names"):
                    yield from noms(c)
        for f in rp._CONTENEUR:
            with self.subTest(fonction=f.__name__):
                inconnus = {n for n in noms(ns[f.__name__].__code__) if n in vars(rp)} - set(ns) - set(vars(builtins))
                self.assertEqual(inconnus, set())

    def test_dry_run_n_execute_rien_et_table_invalide_refusee(self):
        appels = []

        def executer(*a):
            appels.append(a)
            return 0, "", ""
        d = _Depot()
        self.addCleanup(d.tmp.cleanup)
        d.ecrire(_table(ETAPE_B))
        argv = ["PA9", "--enregistrement", "1", "--modele", "fac.Facture", "--racine", str(d.racine)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rp.main(argv + ["--dry-run"], executer=executer, appelants=lambda *a: []), 0)
        self.assertEqual(appels, [])
        sans = copy.deepcopy(ETAPE_B)
        del sans["checkpoint"]
        d.ecrire(_table(sans))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(rp.main(argv, executer=executer, appelants=lambda *a: []), 1)
        self.assertEqual(appels, [])
        self.assertIn("ÉCHEC", out.getvalue())

    def test_rejeu_complet_ecrit_l_enregistrement_via_l_ecrivain_partage(self):
        d = _Depot()
        self.addCleanup(d.tmp.cleanup)
        d.ecrire(_table(ETAPE_B))
        sortie = (rp.MARQUE + json.dumps(self._resultats()) + "\n"
                  + sonde.MARQUE + json.dumps({"verdict": "REPRO", "base_inchangee": True, "observe": ""}) + "\n")
        ecrits = []
        argv = ["PA9", "--enregistrement", "1", "--modele", "fac.Facture", "--racine", str(d.racine)]
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = rp.main(argv, executer=lambda *a: (0, sortie, ""), appelants=lambda *a: [],
                           ecrire=lambda g, charge: ecrits.append((g, charge)) or 0)
        self.assertEqual(code, 0, out.getvalue())
        self.assertEqual(ecrits[0][0], "PA9")
        self.assertEqual(ecrits[0][1]["couvre"], ["AFAC1"])
        # base modifiée = jamais d'enregistrement
        sale = sortie.replace('"base_inchangee": true', '"base_inchangee": false')
        ecrits.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rp.main(argv, executer=lambda *a: (1, sale, ""), appelants=lambda *a: [],
                                     ecrire=lambda g, c: ecrits.append(g) or 0), 1)
        self.assertEqual(ecrits, [])


DJ = "backend/django_core/apps"
APPEL = "from rest_framework import viewsets\nfrom apps.fac.domain.ops import emettre_facture\n\n\n"


class EntreeDomaineTests(unittest.TestCase):
    """Fonction d'entrée DOMAINE (PA4.05-09) : jouée par l'action de vue qui l'APPELLE (index AST AMET80)."""

    @classmethod
    def setUpClass(cls):
        cls.depot = DepotJetable({
            f"{DJ}/fac/domain/ops.py": "def emettre_facture(f):\n    return f\n",
            f"{DJ}/fac/views.py": APPEL + "class FactureViewSet(viewsets.ModelViewSet):\n"
            "    def bulk(self, request):\n        return emettre_facture(2)\n\n"
            "    def emettre(self, request, pk=None):\n        return emettre_facture(1)\n",
            f"{DJ}/fac/services.py": APPEL + "def lot():\n    return emettre_facture(3)\n",       # pas une vue
            f"{DJ}/fac/tests/test_ops.py": APPEL + "def test_e():\n    emettre_facture(0)\n",  # un test
            f"{DJ}/autre/views.py": APPEL + "class AutreViewSet(viewsets.ModelViewSet):\n"
            "    def emettre(self, request):\n        return emettre_facture(4)\n",            # autre app : repli
        })
        cls.actif = DepotActif(cls.depot)

    @classmethod
    def tearDownClass(cls):
        cls.actif.restaurer()
        cls.depot.fermer()

    def test_entree_domaine_resolue_vers_l_action_de_vue_appelante(self):
        ancres = cp.actions_appelantes(f"{DJ}/fac/domain/ops.py::emettre_facture", self.depot.racine)
        self.assertEqual(ancres, [f"{DJ}/fac/views.py::FactureViewSet.emettre",   # nom proche d'abord
                                  f"{DJ}/fac/views.py::FactureViewSet.bulk"])
        self.assertEqual(cp.actions_appelantes(f"{DJ}/fac/views.py::FactureViewSet.emettre", self.depot.racine), [])
        table = _table(dict(ETAPE_B, fonction_entree=f"{DJ}/fac/domain/ops.py::emettre_facture"), MANQUANTE)
        self.assertEqual(rp.appelants_des_etapes(table, self.depot.racine), {"payer": ancres})

    def test_conteneur_prefere_le_modele_du_checkpoint_et_dit_lequel(self):
        def modele(label):
            return type(label.split(".")[1], (), {"_meta": SimpleNamespace(label=label)})
        Facture, Lot = modele("fac.Facture"), modele("fac.Lot")
        vues = {n: type(n, (), {"queryset": SimpleNamespace(model=M)}) for n, M in
                (("LotViewSet", Lot), ("FactureViewSet", Facture))}
        ancres = [f"{DJ}/fac/views.py::LotViewSet.emettre", f"{DJ}/fac/views.py::FactureViewSet.emettre"]
        C = {"objets": {}, "P": {"appelants": {"e": ancres}},
             "routes": [(f"api/{n}/(?P<pk>[^/.]+)/emettre/$", SimpleNamespace(cls=v, actions={"post": "emettre"}))
                        for n, v in vues.items()]}
        notes = []
        self.assertIs(rp._c_par_appelant(C, {"id": "e"}, Facture, notes)[2], vues["FactureViewSet"])
        self.assertIn("via backend/django_core/apps/fac/views.py::FactureViewSet.emettre", notes[0])
        self.assertIs(rp._c_par_appelant(C, {"id": "e"}, None, [])[2], vues["LotViewSet"])  # ordre de l'hôte
        notes = []
        self.assertIsNone(rp._c_par_appelant(C, {"id": "autre"}, Facture, notes))
        self.assertIn("aucune action de vue n'appelle", notes[0])


if __name__ == "__main__":
    unittest.main()
