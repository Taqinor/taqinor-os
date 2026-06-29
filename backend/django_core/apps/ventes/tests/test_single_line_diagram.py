"""FG252 — tests du brouillon de schéma unifilaire (SVG).

Couvre :
* le module PUR ``single_line_diagram`` (normalisation, rendu SVG, dérivation
  depuis un devis) — calcul pur, ``SimpleTestCase``.
* les endpoints (POST paramètres + GET par devis), scope société et jamais de
  prix dans la sortie.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_single_line_diagram -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.ventes import single_line_diagram as sld
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company
from apps.crm.models import Client

User = get_user_model()


# ── Module pur ────────────────────────────────────────────────────────────────
class SingleLineModuleTest(SimpleTestCase):
    def test_normalize_defaults_and_bounds(self):
        p = sld.normalize_diagram_params({})
        self.assertEqual(p["n_panneaux"], 0)
        self.assertEqual(p["n_strings"], 0)  # pas de panneaux → pas de chaîne
        self.assertEqual(p["phases"], 1)
        self.assertTrue(p["injection"])

    def test_normalize_strings_implied_and_capped(self):
        # n_strings non fourni mais des panneaux → au moins 1 chaîne.
        p = sld.normalize_diagram_params({"n_panneaux": 12})
        self.assertEqual(p["n_strings"], 1)
        # n_strings > n_panneaux → ramené à n_panneaux.
        p2 = sld.normalize_diagram_params({"n_panneaux": 3, "n_strings": 9})
        self.assertEqual(p2["n_strings"], 3)

    def test_phases_coerced_to_1_or_3(self):
        self.assertEqual(
            sld.normalize_diagram_params({"phases": 3})["phases"], 3)
        self.assertEqual(
            sld.normalize_diagram_params({"phases": 2})["phases"], 1)

    def test_garbage_input_never_raises(self):
        p = sld.normalize_diagram_params(
            {"n_panneaux": "abc", "puissance_onduleur_kw": None})
        self.assertEqual(p["n_panneaux"], 0)
        self.assertEqual(p["puissance_onduleur_kw"], 0.0)

    def test_svg_contains_full_chain(self):
        svg = sld.build_single_line_svg(
            {"n_panneaux": 24, "puissance_panneau_wc": 550,
             "onduleur": "Huawei SUN2000 10KTL", "puissance_onduleur_kw": 10,
             "phases": 3, "injection": True})
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("Panneaux PV", svg)
        self.assertIn("String", svg)
        self.assertIn("Huawei SUN2000 10KTL", svg)
        self.assertIn("Comptage", svg)
        self.assertIn("ONEE", svg)
        # kWc dérivé : 24 × 550 = 13.2 kWc
        self.assertIn("13.2 kWc", svg)
        self.assertIn("triphasé", svg)

    def test_svg_autonome_mode_says_site_not_onee(self):
        svg = sld.build_single_line_svg(
            {"n_panneaux": 8, "injection": False})
        self.assertIn("Site (autonome)", svg)
        self.assertNotIn("ONEE", svg)

    def test_svg_battery_branch_added(self):
        svg = sld.build_single_line_svg(
            {"n_panneaux": 10, "has_battery": True})
        self.assertIn("Batterie", svg)

    def test_svg_escapes_injection_in_titre(self):
        svg = sld.build_single_line_svg(
            {"n_panneaux": 1, "titre": "Devis <script>x</script>"})
        self.assertNotIn("<script>", svg)
        self.assertIn("&lt;script&gt;", svg)

    def test_empty_config_still_valid_svg(self):
        svg = sld.build_single_line_svg({})
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.endswith("</svg>"))
        self.assertIn("Aucun panneau", svg)


# ── Endpoints ─────────────────────────────────────────────────────────────────
class SingleLineEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom="Acme Solaire", slug="fg252-acme")
        self.other = Company.objects.create(
            nom="Autre", slug="fg252-autre")
        self.user = User.objects.create_user(
            username="fg252_vendeur", password="x",
            role_legacy="responsable", company=self.company)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client Test",
            email="fg252@example.com")

    def _make_devis(self, company):
        devis = Devis.objects.create(
            company=company, reference="DV-001", client=self.crm_client,
            etude_params={"phases": 3, "injection": True})
        LigneDevis.objects.create(
            devis=devis, designation="Panneau PV 550W mono",
            quantite=20, prix_unitaire=Decimal("1000"))
        LigneDevis.objects.create(
            devis=devis, designation="Onduleur réseau 10kW triphasé",
            quantite=1, prix_unitaire=Decimal("12000"))
        return devis

    def test_post_returns_svg(self):
        resp = self.client_api.post(
            "/api/django/ventes/schema-unifilaire/",
            {"n_panneaux": 12, "puissance_panneau_wc": 550}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("image/svg+xml", resp["Content-Type"])
        body = resp.content.decode()
        self.assertTrue(body.startswith("<svg"))
        self.assertIn("Panneaux PV", body)

    def test_post_json_format_returns_params_and_svg(self):
        resp = self.client_api.post(
            "/api/django/ventes/schema-unifilaire/?format=json",
            {"n_panneaux": 12}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["params"]["n_panneaux"], 12)
        self.assertIn("<svg", resp.data["svg"])

    def test_get_by_devis_derives_from_lines(self):
        devis = self._make_devis(self.company)
        resp = self.client_api.get(
            f"/api/django/ventes/devis/{devis.id}/schema-unifilaire/"
            "?format=json")
        self.assertEqual(resp.status_code, 200)
        params = resp.data["params"]
        self.assertEqual(params["n_panneaux"], 20)
        self.assertEqual(params["puissance_panneau_wc"], 550)
        self.assertEqual(params["phases"], 3)
        self.assertIn("Onduleur", params["onduleur"])

    def test_get_by_devis_other_company_404(self):
        devis = self._make_devis(self.other)
        resp = self.client_api.get(
            f"/api/django/ventes/devis/{devis.id}/schema-unifilaire/")
        self.assertEqual(resp.status_code, 404)

    def test_svg_never_contains_price(self):
        devis = self._make_devis(self.company)
        resp = self.client_api.get(
            f"/api/django/ventes/devis/{devis.id}/schema-unifilaire/")
        body = resp.content.decode()
        # aucun montant du devis (prix unitaires) ne fuit dans le schéma
        self.assertNotIn("1000", body)
        self.assertNotIn("12000", body)
