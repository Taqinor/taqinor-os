"""FG253 — tests de l'aide au calcul de charge structure toiture.

Couvre :
* module PUR ``roof_load`` — surcharge kg/m², comparaison par type, alerte
  dépassement, replis sur entrée incomplète (``SimpleTestCase``).
* endpoints GET (types) + POST (calcul), jamais de prix en sortie.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_roof_load -v 2
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.ventes import roof_load as rl
from authentication.models import Company

User = get_user_model()


class RoofLoadModuleTest(SimpleTestCase):
    def test_list_roof_types_includes_known(self):
        keys = {t["key"] for t in rl.list_roof_types()}
        self.assertIn("tole_bac_acier", keys)
        self.assertIn("dalle_beton", keys)
        self.assertIn("fibrociment", keys)

    def test_unknown_roof_type_falls_back_to_autre(self):
        res = rl.compute_roof_load(roof_type="zzz", module_kg_m2=9)
        self.assertEqual(res["roof_type"], "autre")

    def test_dalle_beton_is_ok_for_typical_pv(self):
        # Dalle béton (120 kg/m²) supporte largement ~9 kg/m².
        res = rl.compute_roof_load(roof_type="dalle_beton", module_kg_m2=9)
        self.assertFalse(res["depassement"])
        self.assertEqual(res["severite"], "ok")
        self.assertGreater(res["marge_kg_m2"], 0)

    def test_fibrociment_overload_alerts(self):
        # Fibrociment (10 kg/m²) avec une charge lourde → dépassement.
        res = rl.compute_roof_load(roof_type="fibrociment", module_kg_m2=20)
        self.assertTrue(res["depassement"])
        self.assertEqual(res["severite"], "depassement")
        self.assertLess(res["marge_kg_m2"], 0)
        self.assertIn("Dépassement", res["message"])

    def test_attention_band_near_capacity(self):
        # Charge majorée entre 80% et 100% de la capacité → 'attention'.
        # tole capacité 15 ; charge 12 → majorée 13.2 (>12=80%, <15).
        res = rl.compute_roof_load(roof_type="tole_bac_acier", module_kg_m2=12)
        self.assertEqual(res["severite"], "attention")
        self.assertFalse(res["depassement"])

    def test_safety_factor_applied(self):
        res = rl.compute_roof_load(roof_type="dalle_beton", module_kg_m2=10)
        self.assertEqual(res["charge_pv_kg_m2"], 10.0)
        self.assertEqual(res["charge_majoree_kg_m2"], 11.0)  # ×1.1

    def test_weight_and_surface_derive_surface_load(self):
        # 24 kg module sur 2.4 m² → 10 kg/m².
        res = rl.compute_roof_load(
            roof_type="dalle_beton", poids_module_kg=24, surface_module_m2=2.4)
        self.assertEqual(res["charge_pv_kg_m2"], 10.0)

    def test_total_load_from_surface(self):
        res = rl.compute_roof_load(
            roof_type="dalle_beton", module_kg_m2=9, surface_toiture_m2=50)
        self.assertEqual(res["charge_totale_kg"], 450.0)

    def test_total_load_from_module_count(self):
        res = rl.compute_roof_load(
            roof_type="dalle_beton", module_kg_m2=9, n_modules=10,
            surface_module_m2=2.0)
        self.assertEqual(res["charge_totale_kg"], 180.0)

    def test_garbage_input_never_raises(self):
        res = rl.compute_roof_load(
            roof_type=None, module_kg_m2="abc", n_modules="x")
        self.assertEqual(res["roof_type"], "autre")
        self.assertIn("avertissement", res)

    def test_explicit_capacity_override(self):
        res = rl.compute_roof_load(
            roof_type="dalle_beton", module_kg_m2=50, capacite_kg_m2=40)
        self.assertEqual(res["capacite_kg_m2"], 40.0)
        self.assertTrue(res["depassement"])


class RoofLoadEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom="Acme", slug="fg253-acme")
        self.user = User.objects.create_user(
            username="fg253_u", password="x",
            role_legacy="responsable", company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_get_lists_roof_types(self):
        resp = self.api.get("/api/django/ventes/toiture/charge/")
        self.assertEqual(resp.status_code, 200)
        keys = {t["key"] for t in resp.data["roof_types"]}
        self.assertIn("tole_bac_acier", keys)

    def test_post_returns_overload_alert(self):
        resp = self.api.post(
            "/api/django/ventes/toiture/charge/",
            {"roof_type": "fibrociment", "module_kg_m2": 20}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["depassement"])
        self.assertEqual(resp.data["severite"], "depassement")

    def test_post_ok_case(self):
        resp = self.api.post(
            "/api/django/ventes/toiture/charge/",
            {"roof_type": "dalle_beton", "module_kg_m2": 9}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["severite"], "ok")
        # aucune donnée de prix dans la réponse
        self.assertNotIn("prix", str(resp.data).lower())
