"""AGNR41 - scripts/check_champs_ecran_sans_consommateur.py (fixtures JSX)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_champs_ecran_sans_consommateur as guard  # noqa: E402

SNAPSHOT_SEUL = """
function Ecran() {
  const [heures, setHeures] = useState('7')
  const [kwc, setKwc] = useState('')
  const draftSnapshot = useMemo(() => ({
    heures, kwc,
  }), [
    heures, kwc,
  ])
  const restaurer = (d) => {
    if (d.heures != null) setHeures(d.heures)
    if (d.kwc != null) setKwc(d.kwc)
  }
  return (
    <div>
      <input value={heures} onChange={(e) => setHeures(e.target.value)} />
      <input value={kwc} onChange={(e) => setKwc(e.target.value)} />
    </div>
  )
}
"""

CONSOMME_PAR_CALCUL = SNAPSHOT_SEUL.replace(
    "  return (\n", "  const production = Number(kwc) * 1500\n  return (\n")

CONSOMME_PAR_ETAT_ECRAN = SNAPSHOT_SEUL.replace(
    "  return (\n", "  const etatEcran = () => ({ heures: Number(heures), kwc })\n  return (\n")


class ChampsSansConsommateurTests(unittest.TestCase):
    def test_etat_lu_seulement_par_l_instantane_est_rouge(self):
        self.assertEqual(set(guard.etats_sans_consommateur(SNAPSHOT_SEUL)), {"heures", "kwc"})

    def test_etat_lu_par_un_calcul_ou_etat_ecran_est_vert(self):
        self.assertEqual(set(guard.etats_sans_consommateur(CONSOMME_PAR_CALCUL)), {"heures"})
        self.assertEqual(guard.etats_sans_consommateur(CONSOMME_PAR_ETAT_ECRAN), {})

    def test_commentaire_n_est_pas_une_lecture(self):
        source = SNAPSHOT_SEUL.replace("  return (\n", "  // kwc heures utilises plus tard\n  return (\n")
        self.assertEqual(set(guard.etats_sans_consommateur(source)), {"heures", "kwc"})

    def test_liste_figee_et_entree_morte(self):
        tmp = Path(tempfile.mkdtemp())
        f = tmp / guard.VENTES / "DevisGenerator.jsx"
        f.parent.mkdir(parents=True)
        f.write_text(SNAPSHOT_SEUL, encoding="utf-8")
        trouves = guard.analyser(tmp)
        cle = "frontend/src/pages/ventes/DevisGenerator.jsx"
        self.assertEqual(set(trouves), {f"{cle}::heures", f"{cle}::kwc"})
        self.assertEqual(len(guard.verifier(trouves, {})), 2)
        figes = {cle: {"heures": "r", "kwc": "r"}}
        self.assertEqual(guard.verifier(trouves, figes), [])
        self.assertTrue(any("MORTE" in e for e in guard.verifier(
            {}, {cle: {"heures": "r"}})))

    def test_depot_reel_vert(self):
        self.assertEqual(guard.verifier(guard.analyser()), [])


if __name__ == "__main__":
    unittest.main()
