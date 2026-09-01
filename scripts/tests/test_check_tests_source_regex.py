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


if __name__ == "__main__":
    unittest.main()
