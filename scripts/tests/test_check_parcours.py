"""Tests de scripts/check_parcours.py (AMET98, C-AMET-025).

Stdlib pur (unittest) : aucun Django, aucune base, aucun docker. Les tables jetables vivent dans
un dossier temporaire ; leurs références visent de VRAIS symboles du dépôt (résolus par
``core/parcours.py``). Le rejeu est testé sur ses parties hôte (jugement des oracles, format
AMET88, programme envoyé à ``sonde.py``) avec un conteneur factice. Lancer :
    python -m unittest scripts.tests.test_check_parcours -v
"""
import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_parcours  # noqa: E402 — après sys.path/setup() (D-ENF22)

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


if __name__ == "__main__":
    unittest.main()
