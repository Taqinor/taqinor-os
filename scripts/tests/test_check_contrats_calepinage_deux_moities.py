"""Tests de scripts/check_contrats_calepinage_deux_moities.py (CALX385).

Stdlib pur (unittest), aucune base de donnees :
    python -m unittest scripts.tests.test_check_contrats_calepinage_deux_moities -v

DETECTION : un échantillon cité d'un SEUL côté rougit en NOMMANT le fichier
et QUELLE moitié manque (serveur ou cliente — les deux chemins sont testés
séparément). SILENCE : un échantillon cité des DEUX côtés, et une dette
gelée dans la base ne fait pas échouer `main`. BASE : une ligne de passif
devenue inutile (l'échantillon a gagné sa moitié cliente) rougit `main`.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_contrats_calepinage_deux_moities as ccm  # noqa: E402


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class FauxDepot:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        self.calepinage = self.racine / "backend" / "django_core" / "apps" / "calepinage"
        self.samples = self.calepinage / "contract_samples"
        self.samples.mkdir(parents=True)
        self.front = self.racine / "frontend" / "src"
        self.web = self.racine / "apps" / "web" / "src"
        self.baseline = self.racine / "scripts" / "allow.txt"

        self._sauvegarde = (
            ccm.ROOT, ccm.CALEPINAGE_DIR, ccm.SAMPLES_DIR, ccm.FRONTEND_ROOTS,
            ccm.BASELINE_PATH,
        )
        ccm.ROOT = self.racine
        ccm.CALEPINAGE_DIR = self.calepinage
        ccm.SAMPLES_DIR = self.samples
        ccm.FRONTEND_ROOTS = (self.front, self.web)
        ccm.BASELINE_PATH = self.baseline

    def echantillon(self, nom: str) -> Path:
        return write(self.samples / nom, "{}\n")

    def citation_serveur(self, relatif: str, contenu: str) -> Path:
        return write(self.calepinage / relatif, contenu)

    def citation_client(self, relatif: str, contenu: str) -> Path:
        return write(self.front / relatif, contenu)

    def close(self):
        (ccm.ROOT, ccm.CALEPINAGE_DIR, ccm.SAMPLES_DIR, ccm.FRONTEND_ROOTS,
         ccm.BASELINE_PATH) = self._sauvegarde
        self.tmp.cleanup()


class BaseDepot(unittest.TestCase):
    def setUp(self):
        self.depot = FauxDepot()
        self.addCleanup(self.depot.close)


# ===========================================================================
# Detection
# ===========================================================================

class DetectionTests(BaseDepot):
    def test_echantillon_sans_moitie_cliente_est_nomme(self):
        self.depot.echantillon("x_contrat.json")
        self.depot.citation_serveur(
            "tests/test_x.py", "# x_contrat.json\n")
        resultat = ccm.analyse()
        self.assertEqual(resultat["sans_moitie_cliente"], ["x_contrat.json"])
        self.assertEqual(resultat["sans_moitie_serveur"], [])

    def test_echantillon_sans_moitie_serveur_est_nomme(self):
        self.depot.echantillon("x_contrat.json")
        self.depot.citation_client("api/xApi.js", "// x_contrat.json\n")
        resultat = ccm.analyse()
        self.assertEqual(resultat["sans_moitie_serveur"], ["x_contrat.json"])

    def test_main_rend_1_et_dit_quelle_moitie_manque(self):
        import contextlib
        import io
        self.depot.echantillon("x_contrat.json")
        self.depot.citation_serveur("tests/test_x.py", "# x_contrat.json\n")
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = ccm.main([])
        self.assertEqual(code, 1)
        texte = sortie.getvalue()
        self.assertIn("x_contrat.json", texte)
        self.assertIn("moitié cliente", texte)

    def test_moitie_serveur_manquante_nest_jamais_couverte_par_le_passif(self):
        import contextlib
        import io
        self.depot.echantillon("x_contrat.json")
        self.depot.citation_client("api/xApi.js", "// x_contrat.json\n")
        write(self.depot.baseline, ccm.ENTETE_BASE + "x_contrat.json  # dette\n")
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = ccm.main([])
        self.assertEqual(code, 1)
        self.assertIn("moitié serveur manquante", sortie.getvalue())


# ===========================================================================
# Silence
# ===========================================================================

class SilenceTests(BaseDepot):
    def test_echantillon_cite_des_deux_cotes_ne_rougit_pas(self):
        self.depot.echantillon("x_contrat.json")
        self.depot.citation_serveur("tests/test_x.py", "# x_contrat.json\n")
        self.depot.citation_client("api/xApi.js", "// x_contrat.json\n")
        resultat = ccm.analyse()
        self.assertEqual(resultat["sans_moitie_cliente"], [])
        self.assertEqual(resultat["sans_moitie_serveur"], [])
        self.assertEqual(ccm.main([]), 0)

    def test_dette_gelee_ne_fait_pas_echouer_main(self):
        self.depot.echantillon("x_contrat.json")
        self.depot.citation_serveur("tests/test_x.py", "# x_contrat.json\n")
        write(self.depot.baseline, ccm.ENTETE_BASE + "x_contrat.json  # dette datee\n")
        self.assertEqual(ccm.main([]), 0)

    def test_contract_samples_ne_se_cite_jamais_lui_meme(self):
        # Le fichier JSON lui-même contient forcément son propre nom dans son
        # CHEMIN de disque — s'il comptait comme citation, la garde serait
        # structurellement muette. Vérifié explicitement.
        self.depot.echantillon("x_contrat.json")
        resultat = ccm.analyse()
        self.assertIn("x_contrat.json", resultat["sans_moitie_serveur"])


# ===========================================================================
# Base de reference
# ===========================================================================

class BaselineTests(BaseDepot):
    def test_write_baseline_refuse_de_grandir_sans_lautorisation(self):
        self.depot.echantillon("x_contrat.json")
        self.depot.citation_serveur("tests/test_x.py", "# x_contrat.json\n")
        write(self.depot.baseline, ccm.ENTETE_BASE)
        code = ccm.main(["--write-baseline"])
        self.assertEqual(code, 1)

    def test_ligne_de_passif_devenue_inutile_rougit(self):
        import contextlib
        import io
        self.depot.echantillon("x_contrat.json")
        self.depot.citation_serveur("tests/test_x.py", "# x_contrat.json\n")
        self.depot.citation_client("api/xApi.js", "// x_contrat.json\n")
        write(self.depot.baseline, ccm.ENTETE_BASE + "x_contrat.json  # ancienne dette\n")
        # La dette est désormais couverte côté client : la ligne de passif
        # est PÉRIMÉE — main() rougit pour qu'elle ne traîne jamais en
        # silence, en NOMMANT la ligne à retirer.
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = ccm.main([])
        self.assertEqual(code, 1)
        self.assertIn("x_contrat.json", sortie.getvalue())
        self.assertIn("INUTILE", sortie.getvalue())
        # --write-baseline la retire effectivement.
        self.assertEqual(ccm.main(["--write-baseline"]), 0)
        base = ccm.charger_base(self.depot.baseline)
        self.assertNotIn("x_contrat.json", base)


if __name__ == "__main__":
    unittest.main()
