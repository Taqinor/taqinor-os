"""Tests de scripts/check_decisions.py et scripts/decisions.py (AMET94).

Stdlib pur (unittest), depot jetable en fichiers temporaires : ni base, ni reseau.
    python -m unittest scripts.tests.test_check_decisions -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_decisions as cd  # noqa: E402
import decisions as dec  # noqa: E402
import plan_lanes  # noqa: E402

REGISTRE = """version: 1
decisions:

  - id: D-T-1
    question: "Question repondue ?"
    options:
      - cle: a
        texte: "premiere branche"
      - cle: b
        texte: "seconde branche"
    reponse: a
    date: "2026-10-09"
    source: "test"
    taches: [TST1]

  - id: D-T-2
    question: "Question ouverte ?"
    options:
      - cle: a
        texte: "oui"
    reponse: ouverte
    date: "2026-10-09"
    source: "test"
    taches: []
"""

SI_A = ("- [ ] TST1 — **Si (a) : faire la premiere chose ; si (b) : faire la seconde** : "
        "Constat : x. Files: `a.py` (ROUTINE)\n")


class Depot:
    def __init__(self, tache_lignes, registre=REGISTRE):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        (self.racine / "docs" / "plans").mkdir(parents=True)
        (self.racine / "docs" / "audits").mkdir(parents=True)
        (self.racine / "docs" / "audits" / "decisions.yml").write_text(registre, encoding="utf-8")
        self.plan = self.racine / "docs" / "plans" / "PLAN_AUDIT_TEST.md"
        self.plan.write_text("".join(tache_lignes), encoding="utf-8")

    def verifier(self):
        return cd.verifier(self.racine)

    def fermer(self):
        self.tmp.cleanup()


class DecisionsTests(unittest.TestCase):
    def depot(self, *lignes, registre=REGISTRE):
        d = Depot(lignes, registre)
        self.addCleanup(d.fermer)
        return d

    def test_tache_si_a_sur_decision_repondue_echoue(self):
        echecs, _ = self.depot(SI_A).verifier()
        self.assertEqual(len(echecs), 1)
        self.assertIn("TST1", echecs[0])
        self.assertIn("D-T-1", echecs[0])

    def test_tache_sans_conditionnel_passe(self):
        ligne = "- [ ] TST1 — **faire la premiere chose (@decision: D-T-1=a)** : Constat : x. Files: `a.py` (ROUTINE)\n"
        echecs, _ = self.depot(ligne).verifier()
        self.assertEqual(echecs, [])

    def test_tache_cochee_ignoree(self):
        echecs, _ = self.depot(SI_A.replace("[ ]", "[x]")).verifier()
        self.assertEqual(echecs, [])

    def test_si_dans_du_code_cite_ne_compte_pas(self):
        ligne = "- [ ] TST1 — **citer `Si (a) : x` sans l'employer** : Constat : x.\n"
        echecs, _ = self.depot(ligne).verifier()
        self.assertEqual(echecs, [])

    def test_conditionnel_sur_decision_ouverte_gated_est_signale_pas_echoue(self):
        ligne = ("- [ ] TST9 — **[GATED: decision fondateur D-T-2] Si (a) : oui ; si (b) : non** : "
                 "Constat : x.\n")
        d = self.depot(ligne)
        reg = REGISTRE.replace("taches: []", "taches: [TST9]")
        (d.racine / "docs" / "audits" / "decisions.yml").write_text(reg, encoding="utf-8")
        echecs, avert = d.verifier()
        self.assertEqual(echecs, [])
        self.assertEqual(len(avert), 1)

    def test_conditionnel_sans_decision_connue_echoue(self):
        ligne = "- [ ] TST7 — **Si (a) : oui ; si (b) : non** : Constat : x.\n"
        echecs, _ = self.depot(ligne).verifier()
        self.assertEqual(len(echecs), 1)

    def test_tag_decision_orphelin_echoue(self):
        ligne = "- [ ] TST1 — **faire (@decision: D-ABSENT-9=a)** : Constat : x.\n"
        echecs, _ = self.depot(ligne).verifier()
        self.assertTrue(any("orphelin" in e for e in echecs))

    def test_tag_option_inexistante_ou_non_repondue_echoue(self):
        inexistante = "- [ ] TST1 — **faire (@decision: D-T-1=z)** : Constat : x.\n"
        autre = "- [ ] TST2 — **faire (@decision: D-T-1=b)** : Constat : x.\n"
        echecs, _ = self.depot(inexistante, autre).verifier()
        self.assertEqual(len(echecs), 2)

    def test_tag_valide_passe(self):
        ligne = "- [ ] TST1 — **faire (@decision: D-T-1=a)** : Constat : x.\n"
        echecs, _ = self.depot(ligne).verifier()
        self.assertEqual(echecs, [])

    def test_tache_gated_sans_d_id_echoue(self):
        ligne = "- [ ] TST3 — **[GATED: décision fondateur à venir] construire** : Constat : x.\n"
        echecs, _ = self.depot(ligne).verifier()
        self.assertTrue(any("GATED" in e for e in echecs))

    def test_gated_sur_autre_chose_qu_une_decision_n_est_pas_vise(self):
        ligne = "- [ ] TST3 — **[GATED: attend TST1 sur main] construire** : Constat : x.\n"
        echecs, _ = self.depot(ligne).verifier()
        self.assertEqual(echecs, [])

    def test_appliquer_reecrit_en_gardant_id_et_ligne(self):
        d = self.depot(SI_A)
        reecritures, impossibles = dec.planifier(d.racine)
        self.assertEqual(impossibles, [])
        self.assertEqual(len(reecritures), 1)
        dec.appliquer(d.racine, ecrire=True)
        lignes = d.plan.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lignes), 1)
        self.assertTrue(lignes[0].startswith("- [ ] TST1 — **faire la premiere chose"))
        self.assertIn("(@decision: D-T-1=a)", lignes[0])
        self.assertNotIn("seconde", lignes[0])
        self.assertIn("Files: `a.py` (ROUTINE)", lignes[0])
        self.assertEqual(d.verifier()[0], [])

    def test_appliquer_ouvre_sur_si_b_garde_la_branche_repondue(self):
        ligne = ("- [ ] TST1 — **Si (b) : seconde ; si (a) : premiere (m3) ; si (c) : n/a** : "
                 "Constat : x.\n")
        d = self.depot(ligne)
        dec.appliquer(d.racine, ecrire=True)
        texte = d.plan.read_text(encoding="utf-8")
        self.assertIn("**premiere (m3) (@decision: D-T-1=a)**", texte)

    def test_appliquer_degate_une_etiquette_gated_repondue(self):
        ligne = "- [ ] TST1 — **[GATED: decision D-T-1] Si (a) : faire ; si (b) : ne pas** : Constat : x.\n"
        d = self.depot(ligne)
        dec.appliquer(d.racine, ecrire=True)
        texte = d.plan.read_text(encoding="utf-8")
        self.assertIn("[D-T-1 = (a), tranchee le 2026-10-09] faire (@decision: D-T-1=a)", texte)
        self.assertEqual(d.verifier()[0], [])

    def test_dry_run_n_ecrit_rien(self):
        d = self.depot(SI_A)
        avant = d.plan.read_bytes()
        dec.appliquer(d.racine, ecrire=False)
        self.assertEqual(d.plan.read_bytes(), avant)

    def test_registre_reel_se_charge_avec_le_mini_parseur(self):
        brut = plan_lanes._MiniYamlParser(
            (ROOT / "docs" / "audits" / "decisions.yml").read_text(encoding="utf-8")).parse()
        decisions = cd.charger_decisions(ROOT)
        self.assertEqual(len(decisions), len(brut["decisions"]))
        for d in decisions.values():
            self.assertTrue(d["options"], d["id"] + " sans option")
            self.assertTrue(d["reponse"] == "ouverte" or d["reponse"] in d["options"],
                            d["id"] + " : reponse hors options")
        self.assertGreaterEqual(len(decisions), 100)


if __name__ == "__main__":
    unittest.main()
