"""L4 assistant (21/11/2026) — la carte de l'ERP servie à l'assistant (`scripts/assistant_carte_erp.py`).

Nouveau fichier car : le générateur est neuf (aucun module de test existant ne le couvre).
KA : chaque entrée de menu, chaque action du registre et chaque rôle système figure dans la carte.
KB : un écran, une action ou un droit ajouté sans régénérer la carte rend `--check` ROUGE.
"""
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scripts import assistant_carte_erp as carte_erp


class CouvertureTests(unittest.TestCase):

    def setUp(self):
        self.texte = carte_erp.carte()

    def test_chaque_menu_chaque_action_chaque_role(self):
        for _section, items in carte_erp.menus():
            for chemin, libelle, _roles in items:
                self.assertIn(f"`{chemin}` {libelle}", self.texte)
        for action in carte_erp.actions():
            self.assertIn(f"`{action['cle']}`", self.texte)
        for nom, _codes in carte_erp.roles()[0]:
            self.assertIn(f"**{nom}**", self.texte)

    def test_sources_lues_non_vides(self):
        """Un format de source changé ne doit pas vider la carte en silence."""
        self.assertGreaterEqual(sum(len(items) for _s, items in carte_erp.menus()), 40)
        self.assertGreaterEqual(len(carte_erp.actions()), 100)
        self.assertGreaterEqual(len(carte_erp.chemins()), 60)

    def test_gestes_d_cop_5_et_droits_sensibles(self):
        par_cle = {a["cle"]: a["geste"] for a in carte_erp.actions()}
        self.assertEqual(par_cle["crm.lead.creer"], "fait")
        self.assertEqual(par_cle["ventes.facture.enregistrer_paiement"], "carte")
        self.assertEqual(par_cle["crm.lead.chercher"], "lit")
        ligne = next(x for x in self.texte.splitlines() if x.startswith("- **Commercial responsable**"))
        self.assertIn("SANS prix_achat_voir, marge_voir", ligne)
        directeur = next(x for x in self.texte.splitlines() if x.startswith("- **Directeur**"))
        self.assertIn("prix_achat_voir", directeur)
        self.assertNotIn("SANS prix_achat_voir", directeur)


class FraicheurTests(unittest.TestCase):

    def _check(self, sortie: Path) -> int:
        with mock.patch.object(carte_erp, "SORTIE", sortie), redirect_stdout(io.StringIO()):
            return carte_erp.main(["--check"])

    def test_carte_du_depot_a_jour(self):
        self.assertEqual(self._check(carte_erp.SORTIE), 0)

    def test_ecran_ajoute_sans_regenerer_rouge_puis_vert(self):
        import tempfile
        with tempfile.TemporaryDirectory() as dossier:
            sortie = Path(dossier) / "carte_erp.md"
            sortie.write_text(carte_erp.carte(), encoding="utf-8")
            self.assertEqual(self._check(sortie), 0)
            neuf = carte_erp.menus() + [("ESSAI", [("/essai/neuf", "Écran neuf", "")])]
            with mock.patch.object(carte_erp, "menus", return_value=neuf):
                self.assertEqual(self._check(sortie), 1)
                with mock.patch.object(carte_erp, "SORTIE", sortie), redirect_stdout(io.StringIO()):
                    carte_erp.main([])
                self.assertEqual(self._check(sortie), 0)


if __name__ == "__main__":
    unittest.main()
