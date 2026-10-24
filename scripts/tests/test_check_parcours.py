"""Tests de scripts/check_parcours.py et scripts/rejouer_parcours.py (AMET98, C-AMET-025).

Stdlib pur (unittest) : aucun Django, aucune base, aucun docker. Les tables jetables vivent dans
un dossier temporaire ; leurs références visent de VRAIS symboles du dépôt (résolus par
``core/parcours.py``). Le rejeu est testé sur ses parties hôte (jugement des oracles, format
AMET88, programme envoyé à ``sonde.py``) avec un conteneur factice. Lancer :
    python -m unittest scripts.tests.test_check_parcours -v
"""
import ast
import contextlib
import copy
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_acceptation  # noqa: E402 — après sys.path/setup() (D-ENF22)
import check_parcours  # noqa: E402 — après sys.path/setup() (D-ENF22)
import rejouer_parcours as rp  # noqa: E402 — après sys.path/setup() (D-ENF22)
import sonde  # noqa: E402 — après sys.path/setup() (D-ENF22)

CORE = "backend/django_core/core/parcours.py"
ETAPE_D1 = {"id": "PA9.01", "nom": "Convertir", "proprietaire": "deploy",
            "declencheur": {"type": "clic", "source": f"{CORE}::resoudre_symbole"},
            "fonction_entree": f"{CORE}::problemes_de_l_etape",
            "checkpoint": {"modifiable": False, "champs": [], "persistance": f"{CORE}::charger_table"},
            "regle_aval": [{"type": "refus_409", "detail": "deux fois : refus"}], "taches": ["ZZZ1"]}
ETAPE_PILOTE = {"id": "creation", "libelle": "Création", "declencheur": {"type": "http", "source": f"{CORE}::etapes"},
                "fonction_entree": f"{CORE}::charger_table", "checkpoint": {"persistance": f"{CORE}::charger_table"},
                "regles_aval": [{"regle": "résout", "source": f"{CORE}::est_une_reference"}]}
MANQUANTE = {"id": "PA9.03", "manquante": True, "declencheur": {"manquant": True},
             "fonction_entree": {"manquant": True},
             "checkpoint": {"persistance": f"{CORE}::charger_table"}, "regles_aval": [], "taches": ["ZZZ2"]}


def table(*etapes, portes=True):
    t = {"parcours": "PA9", "etapes": [copy.deepcopy(e) for e in etapes]}
    if portes:
        t["portes"] = [{"source": f"{CORE}::charger_table"}]
    return t


def racine_avec(t) -> Path:
    racine = Path(tempfile.mkdtemp(prefix="parcours_test_"))
    unittest.addModuleCleanup(shutil.rmtree, racine, True)
    dossier = racine / "backend" / "django_core" / "apps" / "zz" / "parcours"
    dossier.mkdir(parents=True)
    (dossier / "PA9.json").write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
    return racine


def lancer(fonction, *args, **kw):
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = fonction(*args, **kw)
    return code, sortie.getvalue()


class ParcoursTests(unittest.TestCase):
    """Garde statique : 1 déclencheur, 1 fonction d'entrée, 1 checkpoint, ≥ 1 règle aval, symboles résolus."""

    def test_etape_sans_regle_aval_echoue_et_symbole_resolu_passe(self):
        self.assertEqual(check_parcours.problemes(table(ETAPE_D1)), [])
        self.assertEqual(lancer(check_parcours.main, ["--racine", str(racine_avec(table(ETAPE_D1)))])[0], 0)
        sans_regle = dict(ETAPE_D1)
        del sans_regle["regle_aval"]
        erreurs = check_parcours.problemes(table(sans_regle))
        self.assertTrue(any("règle aval" in e for e in erreurs), erreurs)
        code, sortie = lancer(check_parcours.main, ["--racine", str(racine_avec(table(sans_regle)))])
        self.assertEqual(code, 1)
        self.assertIn("ÉCHEC", sortie)

    def test_etape_sans_checkpoint_echoue_dans_les_deux_dialectes(self):
        for etape in (ETAPE_D1, ETAPE_PILOTE):
            sans = {k: v for k, v in etape.items() if k != "checkpoint"}
            with self.subTest(etape=etape["id"]):
                self.assertTrue(any("checkpoint" in e for e in check_parcours.problemes(table(sans))))

    def test_symbole_introuvable_echoue(self):
        faux = dict(ETAPE_D1, fonction_entree=f"{CORE}::symbole_qui_n_existe_pas")
        self.assertTrue(any("introuvable" in e for e in check_parcours.problemes(table(faux))))
        regle = dict(ETAPE_PILOTE, regles_aval=[{"regle": "x", "source": f"{CORE}::absent_du_module"}])
        self.assertTrue(any("règle aval 1.source" in e for e in check_parcours.problemes(table(regle))))

    def test_dialecte_par_pilote_passe_la_regle_de_sa_garde(self):
        self.assertEqual(check_parcours.problemes(table(ETAPE_PILOTE, portes=False)), [])
        sans_declencheur = {k: v for k, v in ETAPE_PILOTE.items() if k != "declencheur"}
        self.assertTrue(any("déclencheur" in e for e in check_parcours.problemes(table(sans_declencheur))))

    def test_portes_vides_ou_absentes_au_schema_d1_echouent(self):
        self.assertTrue(check_parcours.problemes(table(ETAPE_D1, portes=False)))
        self.assertTrue(check_parcours.problemes(dict(table(ETAPE_PILOTE), portes=[])))
        code, sortie = lancer(check_parcours.main, ["--racine", str(racine_avec(table(ETAPE_PILOTE, portes=False)))])
        self.assertEqual(code, 0)
        self.assertIn("sans `portes[]`", sortie)

    def test_etape_manquante_rapportee_jamais_exigee(self):
        t = table(ETAPE_D1, MANQUANTE)
        self.assertEqual(check_parcours.problemes(t), [])
        sortie = lancer(check_parcours.main, ["--racine", str(racine_avec(t))])[1]
        self.assertIn("manquante(s) rapportée(s) (PA9.03)", sortie)
        casse = dict(MANQUANTE, checkpoint={"persistance": f"{CORE}::introuvable_ici"})
        self.assertTrue(check_parcours.problemes(table(ETAPE_D1, casse)))

    def test_identifiant_en_double_echoue(self):
        self.assertTrue(any("double" in e for e in check_parcours.problemes(table(ETAPE_D1, ETAPE_D1))))


OBSERVEES = [
    {"id": "PA9.01", "taches": ["ZZZ1"], "statut": "joue", "verbe": "post", "modifiable": None, "liste": True,
     "appels": [{"verbe": "POST", "url": "/ventes/devis/1/convertir-en-bc/", "statut": 201, "etrangers": 0},
                {"verbe": "POST", "url": "/ventes/devis/1/convertir-en-bc/", "statut": 400, "etrangers": 0,
                 "attendu_refus": True}],
     "ecrit": {"crees": 1, "modifies": []}, "regles": {"refus_409": True}, "coherence": []},
    {"id": "PA9.02", "taches": [], "statut": "auto", "appels": [], "ecrit": {"crees": 1, "modifies": []}, "regles": {}},
    {"id": "PA9.03", "taches": ["ZZZ2"], "statut": "manquante", "appels": [], "regles": {}},
]
SHA = "abcdef1234567890abcdef1234567890abcdef12"


def SANS_APPELANT(cible):
    """Remplace l'index AST d'audit_tache (~40 s à froid) : aucun appelant."""
    return {"python": []}


class RejeuParcoursTests(unittest.TestCase):
    """Rejeu : oracles qa-explorer 1-10 + 3 oracles de parcours, enregistrement AMET88, programme sonde."""

    def test_etape_jouee_refus_409_observe_passe(self):
        juge = rp.evaluer(OBSERVEES[0])
        self.assertEqual(juge["verdict"], "PASS")
        self.assertEqual(juge["oracles_parcours"], {"declenchee": "PASS", "checkpoint": "PASS", "aval": "PASS"})
        self.assertEqual([juge["oracles"][k] for k in ("1", "2", "3", "5", "9")],
                         ["PASS", "PASS", "NA", "PASS", "PASS"])

    def test_etape_auto_non_declenchee_ou_checkpoint_non_relu_echoue(self):
        muette = dict(OBSERVEES[1], ecrit={"crees": 0, "modifies": []})
        self.assertEqual(rp.evaluer(muette)["oracles_parcours"]["declenchee"], "FAIL")
        self.assertEqual(rp.evaluer(muette)["verdict"], "FAIL")
        beat = rp.evaluer(dict(muette, planifiee=True))  # beat jamais déclenché dans la transaction : NA
        self.assertEqual((beat["oracles_parcours"]["declenchee"], beat["verdict"]), ("NA", "PASS"))
        non_relu = dict(OBSERVEES[0], modifiable=False)
        self.assertEqual(rp.evaluer(non_relu)["oracles_parcours"]["checkpoint"], "FAIL")
        accepte_deux_fois = dict(OBSERVEES[0], regles={"refus_409": False})
        self.assertEqual(rp.evaluer(accepte_deux_fois)["oracles_parcours"]["aval"], "FAIL")

    def test_erreur_serveur_et_donnee_etrangere_rougissent_les_oracles_1_et_9(self):
        appel = {"verbe": "GET", "url": "/x/", "statut": 500, "etrangers": 2}
        juge = rp.evaluer(dict(OBSERVEES[0], appels=[appel]))
        self.assertEqual((juge["oracles"]["1"], juge["oracles"]["9"], juge["verdict"]), ("FAIL", "FAIL", "FAIL"))
        self.assertEqual(rp._etrangers({"company": 3, "lignes": [{"company_id": 4}]}, 3), 1)

    def test_etape_manquante_jamais_jouee(self):
        observee = rp._jouer_etape(MANQUANTE, None, None, {}, [], None, {}, 1)
        self.assertEqual((observee["statut"], observee["appels"]), ("manquante", []))
        res = rp.enregistrement("PA9", SHA, "2026-10-24", OBSERVEES)
        self.assertEqual(res["etapes_manquantes"], ["PA9.03"])
        self.assertNotIn("ZZZ2", res["couvre"])

    def test_enregistrement_ecrit_au_format_amet88(self):
        res = rp.enregistrement("PA9", SHA, "2026-10-24", OBSERVEES)
        self.assertEqual((res["verdict"], res["couvre"]), ("PASS", ["ZZZ1"]))
        self.assertEqual([e["id"] for e in res["etapes_sans_tache"]], ["PA9.02"])
        md = rp.ecrire(res, racine_avec(table(ETAPE_D1)))
        erreurs = []
        self.assertEqual(check_acceptation.lire_enregistrement(md, erreurs), {"ZZZ1"})
        self.assertEqual(erreurs, [])
        self.assertEqual(md.parent.name, "PA9")

    def test_candidats_fonction_entree_declencheur_puis_appelants_index(self):
        etape = dict(ETAPE_D1, fonction_entree="backend/django_core/apps/ventes/domain/x.py::emettre",
                     declencheur={"type": "clic", "source": "frontend/src/pages/X.jsx::cliquer"})
        trouves = rp.candidats(etape, appelants=lambda cible: {"python": [
            {"symbole": "backend/django_core/apps/ventes/views/f.py::FactureViewSet.emettre", "test": False},
            {"symbole": "backend/django_core/apps/ventes/tests/t.py::T.test", "test": True}]})
        self.assertEqual(trouves, ["backend/django_core/apps/ventes/domain/x.py::emettre",
                                   "backend/django_core/apps/ventes/views/f.py::FactureViewSet.emettre"])

    def test_bout_en_bout_conteneur_factice_transaction_annulee(self):
        racine, vus = racine_avec(table(ETAPE_D1, MANQUANTE)), {}

        def executer(commande, programme, timeout):
            vus["programme"] = programme
            self.assertIn("transaction.set_rollback(True)", programme)
            source = ast.literal_eval(re.search(r"^_SRC = (.*)$", programme, re.M).group(1))
            espace = {"__name__": "__sonde__"}
            exec(compile(source, "sonde", "exec"), espace)  # définit sonde() sans rien jouer
            self.assertTrue(callable(espace["sonde"]))
            self.assertEqual(espace["PARAMS"]["enregistrement"], "42")
            self.assertEqual(list(espace["PARAMS"]["candidats"]), ["PA9.01"])
            bilan = {"verdict": "REPRO", "base_inchangee": True}
            return 0, rp.MARQUE + json.dumps(OBSERVEES) + "\n" + sonde.MARQUE + json.dumps(bilan) + "\n", ""
        code, sortie = lancer(rp.main, ["PA9", "--enregistrement", "42", "--racine", str(racine)],
                              executer=executer, appelants=SANS_APPELANT, sha=SHA, date="2026-10-24")
        self.assertEqual(code, 0, sortie)
        self.assertIn("PA9.03 : manquante", sortie)
        self.assertTrue((racine / "docs/audits/acceptation/PA9/2026-10-24-abcdef123.results.json").is_file())

    def test_table_refusee_ou_base_modifiee_ne_passe_pas(self):
        sans_regle = {k: v for k, v in ETAPE_D1.items() if k != "regle_aval"}
        appele = []
        code, _ = lancer(rp.main, ["PA9", "--enregistrement", "1", "--racine", str(racine_avec(table(sans_regle)))],
                         executer=lambda *a: appele.append(a), appelants=SANS_APPELANT, sha=SHA)
        self.assertEqual((code, appele), (1, []))
        sortie = rp.MARQUE + json.dumps(OBSERVEES) + "\n" + sonde.MARQUE + '{"base_inchangee": false}\n'
        code, _ = lancer(rp.main, ["PA9", "--enregistrement", "1", "--racine", str(racine_avec(table(ETAPE_D1)))],
                         executer=lambda *a: (0, sortie, ""), appelants=SANS_APPELANT, sha=SHA, date="2026-10-24")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
