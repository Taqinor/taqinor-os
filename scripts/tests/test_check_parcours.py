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

    def test_une_creation_de_lead_non_declaree_echoue(self):
        # ACVI92 — une porte de plus dans le code rougit la table qui ne la déclare pas.
        d = _Depot()
        self.addCleanup(d.tmp.cleanup)
        table = _table(ETAPE)
        table["parcours"] = "PA1"
        app = d.racine / "backend/django_core/apps/fac"
        (app / "tests_porte.py").write_text("def t():\n    Lead.objects.create()\n", encoding="utf-8")
        d.ecrire(table)
        self.assertEqual(cp._portes_non_declarees(table, d.racine), [])

        (app / "porte_factice.py").write_text(
            "def ouvrir():\n    return Lead.objects.create(nom='x')\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cp.verifier_tout(racine=d.racine), 1)
        self.assertIn(
            "ÉCHEC PA1 : création de lead non déclarée : apps/fac/porte_factice.py::ouvrir", out.getvalue())

        table["portes"].append({"id": "p2", "source": "apps/fac/porte_factice.py::ouvrir"})
        (app / "porte_factice.py").write_text(
            "def ouvrir():\n    return Lead(nom='x')\n", encoding="utf-8")
        self.assertEqual(cp._portes_non_declarees(table, d.racine), [])

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

    def test_statuts_declares_lus_dans_la_table_jamais_un_5xx(self):
        """Le 4xx DÉCLARÉ par une règle aval (« HTTP nnn », `refus_409`) est la réponse attendue ; rien d'autre."""
        e = dict(ETAPE, regle_aval=[{"type": "refus_409", "detail": "jeton absent : HTTP 400 ; consommé : HTTP 409"},
                                    {"type": "preserve_manuel", "detail": "dormante : HTTP 404 ; panne : HTTP 500"}])
        self.assertEqual(rp.statuts_declares(e), [400, 404, 409])
        self.assertEqual(rp.statuts_declares(ETAPE), [409])                     # refus_409 seul
        self.assertEqual(rp.statuts_declares(ETAPE_B), [])                      # dialecte sans code
        prog = rp.programme(_table(ETAPE), {"modele": "fac.Facture", "enregistrement": "1"}, 60)
        self.assertIn('"declares": {"PA9.01": [409]}', prog.replace("\\", ""))

    def test_oracle_2_accepte_seulement_le_4xx_declare(self):
        C = {"P": {"declares": {"e": [409]}}, "co": None, "routes": []}
        for st, o1, o2 in ((409, "PASS", "PASS"), (404, "PASS", "FAIL"), (500, "FAIL", "PASS")):
            with self.subTest(st=st):
                res = {"id": "e", "oracles": {}, "parcours": {}, "notes": []}
                rp._c_oracles_api(C, res, ("post", "/api/x/1/facturer/", {}, (st, "application/json", "{}", {})),
                                  object, set())
                self.assertEqual((res["oracles"]["1"], res["oracles"]["2"]), (o1, o2))
                self.assertEqual(any("déclaré par la table" in n for n in res["notes"]), st == 409)

    def test_url_a_parametre_nomme_modele_id(self):
        """PA4.11 — `paiements/factures/<facture_id>/…` reçoit le pk de la FACTURE, pas celui du modèle de la vue."""
        route = "api/django/ventes/paiements/^factures/(?P<facture_id>[^/.]+)/paiement-avec-retenue/$"
        self.assertEqual(rp._c_url(route, {"facture_id": 1087}),
                         "/api/django/ventes/paiements/factures/1087/paiement-avec-retenue/")
        self.assertEqual(rp._c_url("api/x/<int:pk>/y/<str:token>/", {"pk": 3, "token": "ab"}), "/api/x/3/y/ab/")
        self.assertEqual(rp._c_url("api/x/(?P<pk>[^/.]+)/y/", 5), "/api/x/5/y/")  # valeur unique : inchangé

    def test_apercu_declare_enchaine_son_jeton_dans_l_action(self):
        """PA4.08 — déclencheur = vue dry-run : jouée d'abord, son `token` passé au commit ; aperçu raté = FAIL."""
        from unittest import mock
        Apercu = type("releve_dry_run", (), {"post": None, "__module__": "apps.ventes.views.releve_import"})
        Commit = type("releve_commit", (), {"post": None, "__module__": "apps.ventes.views.releve_import"})
        C = {"routes": [("api/releve/dry-run/", SimpleNamespace(cls=Apercu, actions=None)),
                        ("api/releve/commit/", SimpleNamespace(cls=Commit, actions=None))],
             "P": {"corps": {"PA4.08.apercu": {"file": "x"}}, "declares": {"PA4.08": [400, 409]}},
             "objets": {}, "co": None}
        e = {"id": "PA4.08", "declencheur": {"source": "backend/django_core/apps/ventes/views/releve_import.py"
                                                       "::releve_dry_run"}}
        appels = []

        def appeler(C_, verbe, chemin, corps=None):
            appels.append((chemin, corps))
            return (200, "application/json", "", {"token": "J1"}) if "dry-run" in chemin else (
                (201, "application/json", "", {}) if (corps or {}).get("token") else (400, "", "", {}))
        trouve = ("api/releve/commit/", "post", Commit)
        with mock.patch.object(rp, "_c_appeler", appeler), mock.patch.object(rp, "_c_gabarit", lambda C_, v: v), \
                mock.patch.object(rp, "_c_parametres", lambda *a: ({}, None)):
            res = {"id": "PA4.08", "oracles": {}, "parcours": {}, "notes": []}
            self.assertTrue(rp._c_jouer_api(C, e, res, trouve, set()))
            self.assertEqual(appels, [("/api/releve/dry-run/", {"file": "x"}),
                                      ("/api/releve/commit/", {"token": "J1"})])
            self.assertEqual((res["appel"], res["oracles"]["2"]), ("POST /api/releve/commit/ -> 201", "PASS"))
            # aperçu sans jeton : le 400 « jeton requis » est DÉCLARÉ, mais jamais accepté quand l'aperçu a raté
            appels.clear()
            appeler_ko = (lambda C_, v, ch, c=None: (400, "", "aucun fichier", {}))
            with mock.patch.object(rp, "_c_appeler", appeler_ko):
                res = {"id": "PA4.08", "oracles": {}, "parcours": {}, "notes": []}
                rp._c_jouer_api(C, e, res, trouve, set())
            self.assertEqual(res["oracles"]["2"], "FAIL")
            self.assertIn("aperçu déclaré en échec", " ".join(res["notes"]))
        self.assertIsNone(rp._c_apercu(C, dict(e, declencheur={"source": "frontend/x.jsx::f"}), trouve, res))

    def test_etape_planifiee_executee_sans_artefact_hors_rejeu_jamais_fail(self):
        """PA4.15 — la tâche nommée par le déclencheur tourne ; sans artefact lié : « hors rejeu », pas FAIL ;
        une tâche qui LÈVE reste FAIL."""
        from unittest import mock
        e = {"id": "PA4.15", "declencheur": {"type": "beat", "source": "backend/django_core/apps/v/scheduled.py::r"},
             "checkpoint": {"persistance": "x.py::RelanceLog"}, "regle_aval": []}
        C = {"P": {"oracles": rp.ORACLES, "auto": sorted(cp.TYPES_AUTO), "declares": {}}, "routes": [], "objets": {}}

        def checkpoint(C_, res, point, Mp, auto):
            res["parcours"].update(auto="FAIL", checkpoint="FAIL")
        for tache, hors in ((True, True), (None, True), (False, False)):
            with self.subTest(tache=tache), mock.patch.object(rp, "_c_tache", lambda *a, t=tache: t), \
                    mock.patch.object(rp, "_c_modele_de", lambda a: object), \
                    mock.patch.object(rp, "_c_checkpoint", checkpoint):
                res = rp._c_etape(C, e)
            self.assertEqual(bool(res.get("hors_rejeu")), hors)
            self.assertEqual(res["parcours"]["auto"], "NA" if hors else "FAIL")
            etapes, ignorees = rp.etapes_enregistrement({"etapes": [dict(e, taches=["T1"])]}, [res])
            self.assertEqual(len(etapes), 0 if hors else 1)
            if hors:
                self.assertIn("PA4.15 : hors rejeu", ignorees[0])

    def test_couvre_attribue_chaque_etape_jouee_aux_taches_demandees(self):
        table = _table(ETAPE_B, dict(ETAPE_B, id="PA9.03", taches=[]))
        res = self._resultats() + [dict(self._resultats()[0], id="PA9.03")]
        etapes, ignorees = rp.etapes_enregistrement(table, res, ["AARG44"])
        self.assertEqual([(x["id"], x["taches"]) for x in etapes],
                         [("payer.rejeu_aarg44", ["AARG44"]), ("PA9.03.rejeu_aarg44", ["AARG44"])])
        self.assertTrue(all(cacc._etape_complete(x) for x in etapes))

    def test_programme_dans_une_transaction_annulee(self):
        prog = rp.programme(_table(ETAPE_B), {"modele": "fac.Facture", "enregistrement": "1"}, 60)
        self.assertIn("set_rollback(True)", prog)
        self.assertIn(rp.MARQUE, prog)

    def test_programme_ne_compte_que_les_tables_du_parcours(self):
        """AARG45 — l'en-tête de sonde porte `modeles` (clés de `portes` + `--modele`), jamais « tous »."""
        table = dict(_table(ETAPE_B, portes=False), portes={"Facture": [], "Paiement": []})
        prog = rp.programme(table, {"modele": "ventes.Devis", "enregistrement": "1"}, 60)
        self.assertIn("'modeles': ['Facture', 'Paiement', 'ventes.Devis']", prog)
        prog = rp.programme(_table(ETAPE_B), {"modele": "fac.Facture", "enregistrement": "1"}, 60)
        self.assertIn("'modeles': ['fac.Facture']", prog)

    def test_echec_imprime_l_exception_pas_la_queue_des_avertissements(self):
        """AARG45 — un rejeu qui lève nomme l'exception (ligne `ERREUR`/`Traceback`)."""
        d = _Depot()
        self.addCleanup(d.tmp.cleanup)
        d.ecrire(_table(ETAPE_B))
        argv = ["PA9", "--enregistrement", "1", "--modele", "fac.Facture", "--racine", str(d.racine)]
        bruit = "\n".join(f"UserWarning: DRF avertissement {i}" for i in range(40))
        observe = "ERREUR : Traceback (most recent call last):\n  File \"sonde\", line 3\nLookupError: App 'kb' ko"
        sortie = sonde.MARQUE + json.dumps({"verdict": "ECART", "base_inchangee": True, "observe": observe})
        brut = "Traceback (most recent call last):\n  File \"x\", line 1\nValueError: étape cassée\n" + bruit
        for executer, attendu in (((lambda *a: (1, sortie, bruit)), "LookupError: App 'kb' ko"),
                                  ((lambda *a: (1, "", brut)), "ValueError: étape cassée")):
            with self.subTest(attendu=attendu), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(rp.main(argv, executer=executer, appelants=lambda *a: []), 1)
            self.assertIn(attendu, out.getvalue())
            self.assertNotIn("DRF avertissement 39", out.getvalue())

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

    def test_vue_fonction_publique_a_jeton_resolue_par_son_ancre(self):
        """ADVS41 — `fichier::fonction` (@api_view publique, PA3-04) : sa route, jouée au jeton du lien."""
        Vue = type("proposal_data", (), {"get": lambda self: None, "__module__": "apps.ventes.public_views"})
        route = "api/django/ventes/proposal/<str:token>/"
        C = {"routes": [(route, SimpleNamespace(cls=Vue, actions=None))]}
        self.assertEqual(rp._c_route_de(C, "apps/ventes/public_views.py::proposal_data"), (route, "get", Vue))
        self.assertIsNone(rp._c_route_de(C, "apps/ventes/autre.py::proposal_data"))  # autre module
        # un DÉCLENCHEUR public (signature à empreinte lue) n'est jamais joué à la place de l'entrée
        self.assertIsNone(rp._c_route_de(C, "apps/ventes/public_views.py::proposal_data", False))
        self.assertIsNone(rp._c_route_de(C, "apps/ventes/domain/envoi.py::mark_devis_sent"))  # fonction domaine
        self.assertEqual(rp._c_url(route, "abc"), "/api/django/ventes/proposal/abc/")


if __name__ == "__main__":
    unittest.main()
