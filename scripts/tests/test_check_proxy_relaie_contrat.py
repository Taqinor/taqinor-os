"""ADEV72 - scripts/check_proxy_relaie_contrat.py (fixtures)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_proxy_relaie_contrat as guard  # noqa: E402

CONTRAT = {
    "corps": {"empreinte_contenu": "Texte, OBLIGATOIRE : ...", "autres": "nom, option"},
}
CONTRAT_ENTREPRISE = {
    "regles": {"en_ligne": "les trois champs `entreprise.raison_sociale`, "
                           "`entreprise.signataire_qualite`, `entreprise.ice` sont OBLIGATOIRES"},
}
PROXY_COMPLET = """
const entreprise = { raison_sociale: x, signataire_qualite: y, ice: z };
const body = { empreinte_contenu: e, entreprise };
"""
PROXY_SANS_ENTREPRISE = "const body = { empreinte_contenu: e };\n"


def _repo(proxy_source):
    tmp = Path(tempfile.mkdtemp())
    api = tmp / guard.WEB / "pages" / "api"
    api.mkdir(parents=True)
    (api / "proposition-accept.ts").write_text(proxy_source, encoding="utf-8")
    cs = tmp / guard.WEB / "contract_samples"
    cs.mkdir(parents=True)
    (cs / "proposal_accept.json").write_text(json.dumps(CONTRAT), encoding="utf-8")
    (cs / "acceptation_entreprise.json").write_text(
        json.dumps(CONTRAT_ENTREPRISE), encoding="utf-8")
    return tmp


class ProxyRelaieContratTests(unittest.TestCase):
    def test_cle_obligatoire_non_relayee_rouge(self):
        root = _repo(PROXY_SANS_ENTREPRISE)
        erreurs = guard.verifier(root, dette={})
        texte = " ".join(erreurs)
        self.assertIn("proposition-accept.ts", texte)
        self.assertIn("raison_sociale", texte)
        self.assertIn("ice", texte)
        self.assertNotIn("empreinte_contenu", texte)

    def test_proxy_conforme_vert(self):
        self.assertEqual(guard.verifier(_repo(PROXY_COMPLET), dette={}), [])

    def test_commentaire_n_est_pas_un_relais(self):
        root = _repo("// empreinte_contenu, raison_sociale, signataire_qualite, ice\n")
        self.assertEqual(len(guard.manques(root)), 4)

    def test_dette_connue_et_entree_morte(self):
        root = _repo(PROXY_COMPLET)
        erreurs = guard.verifier(root, dette={("proposition-accept.ts", "empreinte_contenu"): "x"})
        self.assertTrue(any("MORTE" in e for e in erreurs))

    def test_depot_reel_vert(self):
        self.assertEqual(guard.verifier(), [])


if __name__ == "__main__":
    unittest.main()
