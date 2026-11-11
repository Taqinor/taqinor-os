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

    def test_lecteur_unique_du_generateur_est_vu_comme_lecture_de_source(self):
        # SPL42 — `lireSourceGenerateur(` / `lireSourceCoquille(` remplacent
        # readFileSync : un nouveau lecteur reste visible du cliquet.
        for lecteur in ("lireSourceGenerateur()", "lireSourceCoquille()"):
            offenders = self._scan({
                "pages/ventes/DevisGeneratorNouveau.test.mjs": (
                    "import { lireSourceGenerateur } from './DevisGeneratorSource.js'\n"
                    f"const DG = {lecteur}\n"
                    "assert.match(DG, /quelque chose/)\n"
                ),
            })
            self.assertEqual(len(offenders), 1, (lecteur, offenders))

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
                p.read_text(encoding="utf-8"), guard.RE_READFILESYNC,
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

    # ── ATST53 : tout le depot (front + back) et les codes hors registre ─────
    REGISTRE = ("import re\n"
                "EST_PERMISSION_APP = re.compile(r'^app_[a-z0-9][a-z0-9_]*_voir$')\n"
                "ALL_PERMISSIONS = ['crm_voir']\n"
                "PORTAIL_CLIENT_PERMISSIONS = ['portail_client_acces']\n")
    FAUTIFS = {
        "frontend/src/pages/ventes/FactureListNouveau.test.mjs": SOURCE_REGEX_PATTERN,
        "backend/django_core/apps/ventes/tests/test_x.py": (
            "from pathlib import Path\n\n\nclass XTests:\n"
            "    def test_y(self):\n"
            "        src = (Path(__file__).parent.parent / 'views' / 'devis.py').read_text()\n"
            "        self.assertIn('generer', src)\n\n"
            "    def test_z(self):\n"
            "        Role(permissions=['tickets_gerer', 'app_crm_voir', 'portail_client_acces',\n"
            "                          'custom_object.x.voir', 'crm_voir'])\n"),
    }
    CLES = ("frontend/src/pages/ventes/FactureListNouveau.test.mjs",
            "backend/django_core/apps/ventes/tests/test_x.py::XTests.test_y",
            "backend/django_core/apps/ventes/tests/test_x.py::XTests.test_z::tickets_gerer")

    def _main_atst53(self, files, argv=(), bases=None):
        """Arbre factice (registre compris) + bases ; rend (code, sortie, bases relues)."""
        import contextlib
        import io
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, content in {"backend/django_core/apps/roles/permissions_registre.py": self.REGISTRE,
                                 **files}.items():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(content, encoding="utf-8")
            base_source, base_codes = root / "source_allow.txt", root / "codes_allow.txt"
            for chemin, cles in zip((base_source, base_codes), bases or ()):
                chemin.write_text("".join(f"{c}  # test\n" for c in cles), encoding="utf-8")
            sortie = io.StringIO()
            with mock.patch.object(guard, "ROOT", root), \
                 mock.patch.object(guard, "SCAN_ROOT", root / "frontend" / "src"), \
                 mock.patch.object(guard, "CRM_SCAN_ROOTS", (root / "frontend" / "src" / "pages" / "crm",)), \
                 mock.patch.object(guard, "ALLOWLIST", {}), mock.patch.object(guard, "CRM_ALLOWLIST", {}), \
                 mock.patch.object(guard, "BASELINE_SOURCE", base_source), \
                 mock.patch.object(guard, "BASELINE_CODES", base_codes), \
                 contextlib.redirect_stdout(sortie):
                code = guard.main(list(argv))
            relues = [guard._cliquet.charger(c) for c in (base_source, base_codes)]
        return code, sortie.getvalue(), relues

    def test_tout_test_qui_lit_le_source_hors_base_rougit(self):
        code, sortie, _ = self._main_atst53(self.FAUTIFS)
        self.assertEqual(code, 1, sortie)
        for cle in self.CLES[:2]:
            self.assertIn(f"{cle} - NOUVEAU test qui lit un source", sortie)

    def test_code_de_permission_hors_registre_rougit(self):
        code, sortie, _ = self._main_atst53(self.FAUTIFS)
        self.assertEqual(code, 1, sortie)
        self.assertIn(f"{self.CLES[2]} - code de permission absent du registre", sortie)
        for admis in ("app_crm_voir", "portail_client_acces", "custom_object.x.voir", "::crm_voir"):
            self.assertNotIn(admis, sortie)

    def test_entree_de_base_disparue_rougit(self):
        code, sortie, _ = self._main_atst53(
            self.FAUTIFS, bases=(self.CLES[:2] + ("frontend/src/Disparu.test.mjs",), self.CLES[2:]))
        self.assertEqual(code, 1, sortie)
        self.assertIn("entrée MORTE de source_allow.txt : frontend/src/Disparu.test.mjs", sortie)

    def test_base_amorcee_sort_zero_et_ne_peut_que_retrecir(self):
        code, sortie, _ = self._main_atst53(self.FAUTIFS, bases=(self.CLES[:2], self.CLES[2:]))
        self.assertEqual(code, 0, sortie)
        self.assertIn("1 test(s) front, 1 test(s) back, 1 code(s)", sortie)
        code, _, relues = self._main_atst53(self.FAUTIFS, argv=["--write-baseline"])  # amorçage
        self.assertEqual((code, relues), (0, [set(self.CLES[:2]), set(self.CLES[2:])]))
        code, sortie, relues = self._main_atst53(
            self.FAUTIFS, argv=["--write-baseline"], bases=(self.CLES[:1], self.CLES[2:]))
        self.assertEqual(code, 1, sortie)
        self.assertIn("REFUS", sortie)
        self.assertEqual(relues[0], set(self.CLES[:1]))


if __name__ == "__main__":
    unittest.main()
