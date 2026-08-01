"""EZ16 — test du test : la garde anti-jargon rougit-elle vraiment ?

Une garde qui ne rougit jamais ne garde rien. On plante les deux motifs
interdits dans une arborescence temporaire et on vérifie que le scanner les
voit ; puis on vérifie qu'un commentaire qui les CITE ne déclenche rien (les
commentaires racontent le bug corrigé — ce n'est pas une régression).
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import scripts.check_frontend_errors as guard


class CheckFrontendErrorsTests(unittest.TestCase):
    def _scan(self, files):
        """Écrit `files` (nom → contenu) sous un faux `frontend/src/pages` et
        lance le scanner dessus."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages = root / "frontend" / "src" / "pages"
            pages.mkdir(parents=True)
            for name, content in files.items():
                (pages / name).write_text(content, encoding="utf-8")
            with mock.patch.object(guard, "ROOT", root), \
                 mock.patch.object(guard, "SCANNED_DIRS", [pages]):
                return guard.scan()

    def test_json_stringify_dune_erreur_est_refuse(self):
        offenders = self._scan({
            "Bad.jsx": "const msg = err?.detail ?? JSON.stringify(err)\n",
        })
        self.assertEqual(len(offenders), 1, offenders)
        self.assertIn("Bad.jsx:1", offenders[0])
        self.assertIn("JSON brut", offenders[0])

    def test_toast_error_nu_est_refuse(self):
        offenders = self._scan({"Bad.jsx": "toast.error(err)\n"})
        self.assertEqual(len(offenders), 1, offenders)
        self.assertIn("toast.error(err) nu", offenders[0])

    def test_un_commentaire_qui_cite_le_motif_ne_declenche_rien(self):
        offenders = self._scan({
            "Ok.jsx": (
                "// EZ16 - le repli faisait JSON.stringify(err) : purge.\n"
                "/* ancien code : toast.error(err) */\n"
                "toast.error(frenchError(err, 'Message francais.'))\n"
            ),
        })
        self.assertEqual(offenders, [])

    def test_un_fichier_de_test_a_le_droit_de_fabriquer_un_payload(self):
        offenders = self._scan({
            "Bad.test.jsx": "expect(JSON.stringify(err)).toBe('{}')\n",
        })
        self.assertEqual(offenders, [])

    def test_serialiser_pour_un_log_reste_permis(self):
        # Seul l'AFFICHAGE utilisateur est vise : `payload` n'est pas une erreur.
        offenders = self._scan({"Ok.jsx": "console.debug(JSON.stringify(payload))\n"})
        self.assertEqual(offenders, [])

    def test_le_repo_reel_est_propre(self):
        self.assertEqual(guard.scan(), [])

    def test_allowlist_vide(self):
        # EZ16 a purge le dernier site : toute entree future doit etre justifiee.
        self.assertEqual(guard.ALLOWLIST, set())


if __name__ == "__main__":
    unittest.main()
