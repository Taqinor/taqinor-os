"""QJR239 — test du test : la garde 'regex sur code source' rougit-elle sur
un NOUVEAU fichier de la famille, et reste-t-elle verte sur l'allowlist gelee
+ le vrai depot ?
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import scripts.check_tests_source_regex as guard

SOURCE_REGEX_PATTERN = (
    "import { readFileSync } from 'node:fs'\n"
    "const SRC = readFileSync('./autoQuote.js', 'utf8')\n"
    "assert.match(SRC, /panels = 0/)\n"
)


class CheckTestsSourceRegexTests(unittest.TestCase):
    def _scan(self, files, allowlist=None):
        """Ecrit `files` (chemin relatif a frontend/src -> contenu) sous une
        fausse racine et lance le scanner dessus."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            scan_root = root / "frontend" / "src"
            for rel, content in files.items():
                p = scan_root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
            with mock.patch.object(guard, "ROOT", root), \
                 mock.patch.object(guard, "SCAN_ROOT", scan_root), \
                 mock.patch.object(guard, "ALLOWLIST", allowlist or {}):
                return guard.scan()

    def test_nouveau_fichier_de_la_famille_hors_allowlist_rougit(self):
        offenders = self._scan({
            "features/ventes/autoQuote.NouveauTruc.test.mjs": SOURCE_REGEX_PATTERN,
        })
        self.assertEqual(len(offenders), 1, offenders)
        self.assertIn("autoQuote.NouveauTruc.test.mjs", offenders[0])
        self.assertIn("QJR239", offenders[0])

    def test_meme_fichier_dans_lallowlist_ne_rougit_pas(self):
        rel = "features/ventes/autoQuote.NouveauTruc.test.mjs"
        offenders = self._scan(
            {rel: SOURCE_REGEX_PATTERN},
            allowlist={f"frontend/src/{rel}": "raison de test"},
        )
        self.assertEqual(offenders, [])

    def test_fichier_hors_famille_ignore_meme_avec_le_patron(self):
        offenders = self._scan({
            "features/ventes/autreChose.test.mjs": SOURCE_REGEX_PATTERN,
        })
        self.assertEqual(offenders, [])

    def test_readfilesync_dun_fixture_json_sans_regex_ne_rougit_pas(self):
        # Meme patron que autoQuote.e2eSeedRepro.test.mjs : lire un fixture
        # JSON n'est PAS le patron vise (aucune assertion regex sur du CODE).
        offenders = self._scan({
            "features/ventes/autoQuote.FixtureSeule.test.mjs": (
                "import { readFileSync } from 'node:fs'\n"
                "const DATA = JSON.parse(readFileSync('./x.fixture.json', 'utf8'))\n"
                "assert.equal(DATA.length, 3)\n"
            ),
        })
        self.assertEqual(offenders, [])

    def test_fichier_non_test_ignore_meme_avec_le_patron(self):
        offenders = self._scan({
            "features/ventes/solar.js": SOURCE_REGEX_PATTERN,
        })
        self.assertEqual(offenders, [])

    def test_le_depot_reel_est_propre(self):
        # La vraie allowlist doit couvrir tous les vrais fichiers qui
        # utilisent encore le patron aujourd'hui : aucun NOUVEAU depasse.
        self.assertEqual(guard.scan(), [])

    def test_allowlist_pointe_vers_des_fichiers_reels_de_la_famille(self):
        # Chaque entree doit exister, etre un vrai test de la famille, et lire
        # du source via readFileSync (meme quand l'assertion qui suit est un
        # .includes() plutot qu'un assert.match() - ex. autoQuote.paliers - le
        # detecteur mecanique reste volontairement conservateur sur le REGEX,
        # l'allowlist documente le patron au sens large).
        for rel in guard.ALLOWLIST:
            p = guard.ROOT / rel
            self.assertTrue(p.exists(), f"{rel} n'existe pas")
            name = p.name
            self.assertTrue(
                any(name.endswith(suf) for suf in guard.TEST_SUFFIXES),
                f"{rel} n'est pas un fichier de test")
            self.assertTrue(
                name.startswith(guard.FAMILY_PREFIXES),
                f"{rel} n'est pas de la famille DevisGenerator*/solar*/autoQuote*")
            self.assertRegex(
                p.read_text(encoding="utf-8"), r"readFileSync",
                f"{rel} ne lit plus de source via readFileSync - a retirer de l'allowlist")

    def test_allowlist_a_une_raison_non_vide_par_entree(self):
        for rel, raison in guard.ALLOWLIST.items():
            self.assertTrue(raison and raison.strip(), f"{rel} sans raison")

    # ── QJR427 : la liste blanche cesse de grossir en silence ───────────────
    def test_nouvelle_entree_allowlist_sans_raison_datee_rougit(self):
        # Cas negatif EXECUTE (Done de QJR427) : une entree AJOUTEE (hors du
        # socle gele) sans date ni identifiant de tache fait rougir la garde.
        fake_allowlist = dict(guard.ALLOWLIST)
        fake_allowlist[
            "frontend/src/pages/ventes/DevisGeneratorFake.test.mjs"
        ] = "raison sans date ni tache attribuee"
        offenders = guard.check_allowlist_reasons(fake_allowlist)
        self.assertEqual(len(offenders), 1, offenders)
        self.assertIn("DevisGeneratorFake.test.mjs", offenders[0])
        self.assertIn("QJR427", offenders[0])

    def test_nouvelle_entree_allowlist_datee_et_attribuee_ne_rougit_pas(self):
        fake_allowlist = dict(guard.ALLOWLIST)
        fake_allowlist[
            "frontend/src/pages/ventes/DevisGeneratorFake.test.mjs"
        ] = "QJR999 (2026-09-02) - raison correctement datee et attribuee."
        offenders = guard.check_allowlist_reasons(fake_allowlist)
        self.assertEqual(offenders, [])

    def test_nouvelle_entree_attribuee_par_pr_sans_id_de_tache_ne_rougit_pas(self):
        # L'attribution accepte aussi "PR #NNN" (cas de l'entree OFFGRID,
        # qui ne porte pas d'identifiant de tache numerote).
        fake_allowlist = dict(guard.ALLOWLIST)
        fake_allowlist[
            "frontend/src/pages/ventes/DevisGeneratorFake.test.mjs"
        ] = "FAKE PR #999 (2026-09-02) - raison attribuee via PR."
        offenders = guard.check_allowlist_reasons(fake_allowlist)
        self.assertEqual(offenders, [])

    def test_socle_actuel_reste_gele_aucune_retro_datation_exigee(self):
        # Les 21 entrees historiques (dont OFFGRID, desormais documentee par
        # QJR427) ne sont jamais retro-datees de force : le socle actuel du
        # vrai depot doit rester propre.
        self.assertEqual(guard.check_allowlist_reasons(), [])

    def test_entree_offgrid_est_desormais_datee_et_attribuee(self):
        raison = guard.ALLOWLIST[
            "frontend/src/pages/ventes/DevisGeneratorOffgrid.test.mjs"]
        self.assertRegex(raison, guard.REASON_DATE_RE)
        self.assertRegex(raison, guard.REASON_ATTRIBUTION_RE)

    def test_main_sur_le_vrai_depot_est_vert(self):
        self.assertEqual(guard.main(), 0)


if __name__ == "__main__":
    unittest.main()
