"""CAD177 — tests hote de scripts/nightly_alert_gate.py (decision d'alerte
nocturne pour `release-verify.yml`). Pure stdlib, aucun docker/API GitHub. Run
avec :
    python -m unittest scripts.tests.test_nightly_alert_gate -v
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import nightly_alert_gate as gate  # noqa: E402

SCRIPT = ROOT / "scripts" / "nightly_alert_gate.py"


class IsRunGreenTests(unittest.TestCase):
    def test_all_success_is_green(self):
        self.assertTrue(gate.is_run_green(["success", "success", "success"]))

    def test_one_failure_not_green(self):
        self.assertFalse(gate.is_run_green(["success", "failure", "success"]))

    def test_one_skipped_not_green(self):
        # Un job saute (prerequis en echec, ex. ci-image-check) n'a pas
        # valide la matrice — jamais lu comme un succes.
        self.assertFalse(gate.is_run_green(["success", "skipped"]))

    def test_one_cancelled_not_green(self):
        self.assertFalse(gate.is_run_green(["success", "cancelled"]))

    def test_empty_is_never_green(self):
        # Fail-safe : un cablage casse (aucun resultat transmis) ne doit
        # jamais se lire comme "tout est vert".
        self.assertFalse(gate.is_run_green([]))


class ShouldAlertTests(unittest.TestCase):
    def test_this_run_green_never_alerts_regardless_of_history(self):
        self.assertFalse(gate.should_alert(["success", "success"], "failure"))
        self.assertFalse(gate.should_alert(["success", "success"], None))
        self.assertFalse(gate.should_alert(["success"], "cancelled"))

    def test_two_red_nights_in_a_row_alerts(self):
        self.assertTrue(gate.should_alert(["success", "failure"], "failure"))

    def test_single_red_night_does_not_alert(self):
        # Le run precedent etait vert : ce n'est que LA PREMIERE nuit rouge.
        self.assertFalse(gate.should_alert(["success", "failure"], "success"))

    def test_unknown_previous_history_is_fail_safe(self):
        # Historique absent (premier run jamais termine, run precedent
        # introuvable) : jamais suppose vert par defaut — CAD177 est
        # precisement le cas ou 12 nuits rouges de suite n'ont alerte
        # personne ; le defaut doit pencher vers l'alerte, pas le silence.
        self.assertTrue(gate.should_alert(["failure"], None))
        self.assertTrue(gate.should_alert(["failure"], ""))

    def test_skipped_job_counts_as_not_green(self):
        self.assertTrue(gate.should_alert(["success", "skipped"], "failure"))

    def test_cancelled_previous_counts_as_not_green(self):
        self.assertTrue(gate.should_alert(["failure"], "cancelled"))


class CliTests(unittest.TestCase):
    """Le CLI reellement appele par le job `alert-on-repeated-failure` du
    workflow — argparse + le format de sortie stdout exact que le `run:`
    bash lit (`true`/`false`, rien d'autre)."""

    def _run(self, *args):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.returncode, 0)
        return result.stdout.strip()

    def test_cli_two_red_nights(self):
        out = self._run(
            "--job-result", "success", "--job-result", "failure",
            "--previous-conclusion", "failure",
        )
        self.assertEqual(out, "true")

    def test_cli_green_run_no_alert(self):
        out = self._run(
            "--job-result", "success", "--job-result", "success",
            "--previous-conclusion", "failure",
        )
        self.assertEqual(out, "false")

    def test_cli_missing_previous_conclusion_flag_is_fail_safe(self):
        # Le workflow omet le flag quand `gh run list` ne renvoie rien
        # (aucun run nocturne precedent connu) : doit alerter si CE run est
        # rouge, jamais supposer un historique vert absent.
        out = self._run("--job-result", "failure")
        self.assertEqual(out, "true")

    def test_cli_multiple_job_results(self):
        out = self._run(
            "--job-result", "success", "--job-result", "success",
            "--job-result", "success", "--job-result", "success",
            "--job-result", "success", "--job-result", "success",
            "--previous-conclusion", "failure",
        )
        self.assertEqual(out, "false")


if __name__ == "__main__":
    unittest.main()
