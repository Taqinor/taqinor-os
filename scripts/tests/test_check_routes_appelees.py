"""ACRM49 - tests de scripts/check_routes_appelees.py.

Stdlib pur. Lancer :
    python -m unittest scripts.tests.test_check_routes_appelees -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_routes_appelees as cra  # noqa: E402

M = ("api", "django", "crm")


class RouteSansAppelantTests(unittest.TestCase):
    def test_route_sans_appelant_detectee(self):
        routes = {M + ("leads",), M + ("leads", "<pk>"), M + ("fantome",)}
        appels = {M + ("leads",)}
        violations, perimees = cra.verifier(routes, appels, a_corriger={})
        self.assertEqual(violations, [M + ("fantome",)])
        self.assertEqual(perimees, [])

    def test_detail_couvert_par_la_liste_de_sa_ressource(self):
        routes = {M + ("leads",), M + ("leads", "<pk>")}
        self.assertEqual(cra.routes_sans_appelant(routes, {M + ("leads",)}), [])

    def test_action_appelee_couvre_le_detail(self):
        routes = {M + ("clients", "<pk>"), M + ("clients", "<>", "fusion")}
        appels = {M + ("clients", "<>", "fusion")}
        self.assertEqual(cra.routes_sans_appelant(routes, appels), [])

    def test_public_et_webhooks_sans_ecran_par_construction(self):
        routes = {M + ("public", "visite"), M + ("webhooks", "website-leads"),
                  M + ("apporteur-portail", "<>", "mes-deals")}
        self.assertEqual(cra.routes_sans_appelant(routes, set()), [])

    def test_routes_hors_crm_ignorees(self):
        routes = {("api", "django", "ventes", "devis")}
        self.assertEqual(cra.routes_sans_appelant(routes, set()), [])

    def test_entree_perimee_signalee(self):
        routes = {M + ("leads",)}
        appels = {M + ("leads",)}
        violations, perimees = cra.verifier(
            routes, appels, a_corriger={"crm/leads": "x", "crm/disparue": "y"})
        self.assertEqual(violations, [])
        self.assertEqual(perimees, ["crm/disparue", "crm/leads"])

    def test_exemption_motivee_accepte_la_route(self):
        routes = {M + ("objectifs",)}
        violations, perimees = cra.verifier(
            routes, set(), a_corriger={"crm/objectifs": "A CORRIGER : x"})
        self.assertEqual((violations, perimees), ([], []))

    def test_appels_e2e_joker_et_litteral(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.spec.js").write_text(
                "await page.request.get(`/api/django/crm/leads/${id}/historique/?x=1`)\n"
                "await r.get('/api/django/crm/objectifs/')\n", encoding="utf-8")
            appels = cra.appels_e2e(Path(d))
        self.assertIn(M + ("leads", "<>", "historique"), appels)
        self.assertIn(M + ("objectifs",), appels)

    def test_liste_blanche_motivee_une_ligne_par_route(self):
        for cle, raison in cra.A_CORRIGER.items():
            self.assertTrue(cle.startswith("crm/"), cle)
            self.assertTrue(raison.startswith("A CORRIGER"), cle)


class DepotReelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routes, cls.appels = cra.mesurer()

    def test_depot_vert(self):
        violations, perimees = cra.verifier(self.routes, self.appels)
        self.assertEqual(violations, [], f"routes crm sans appelant : {violations}")
        self.assertEqual(perimees, [], f"entrees perimees : {perimees}")
        self.assertTrue(cra.routes_crm(self.routes), "aucune route crm resolue")

    def test_liste_blanche_videe_nomme_les_routes_gardees_sans_ecran(self):
        # Test-du-test : sans la liste blanche, la garde NOMME les routes
        # servies sans ecran (kpi-adherence, mes-stats, salles-vente...).
        violations, _ = cra.verifier(self.routes, self.appels, a_corriger={})
        noms = {cra._cle(r) for r in violations}
        self.assertIn("crm/relance-etapes/kpi-adherence", noms)
        self.assertIn("crm/relance-etapes/mes-stats", noms)
        self.assertIn("crm/salles-vente", noms)
        self.assertEqual(noms, set(cra.A_CORRIGER))


if __name__ == "__main__":
    unittest.main()
