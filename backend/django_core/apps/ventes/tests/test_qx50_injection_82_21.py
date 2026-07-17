"""QX50 — Injection 82-21 (industriel/commercial) : constantes sourcées + bornes.

Le surplus injectable est plafonné à 20 % de la production et valorisé au tarif
ANRE NET des frais d'accès réseau. OFF par défaut ; la mention réglementaire
accompagne toujours la ligne. Valeurs canoniques IDENTIQUES au miroir JS
(solar.injection.test.mjs) — test de parité.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qx50_injection_82_21 -v 2
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import constants_82_21 as c


class TestNetTarif(SimpleTestCase):
    def test_net_hors_pointe(self):
        # 0,18 − (6,07 + 6,38)/100 = 0,0555 DH/kWh
        self.assertAlmostEqual(c.net_tarif_dh_kwh(pointe=False), 0.0555, places=4)

    def test_net_pointe(self):
        self.assertAlmostEqual(c.net_tarif_dh_kwh(pointe=True), 0.0855, places=4)

    def test_never_negative(self):
        # même si les frais dépassaient le tarif, le net reste ≥ 0
        self.assertGreaterEqual(c.net_tarif_dh_kwh(), 0)


class TestInjectionBornes(SimpleTestCase):
    def test_normal_surplus(self):
        # prod 400000, autoconso 352000 → surplus 48000 (< plafond 80000)
        kwh, dh = c.injection_annuelle(400000, 352000)
        self.assertEqual(kwh, 48000)
        self.assertEqual(dh, 2664)          # 48000 × 0,0555

    def test_capped_at_20pct(self):
        # prod 100000, autoconso 0 → surplus 100000 BORNÉ à 20 % = 20000
        kwh, dh = c.injection_annuelle(100000, 0)
        self.assertEqual(kwh, 20000)
        self.assertEqual(dh, 1110)          # 20000 × 0,0555

    def test_no_surplus(self):
        self.assertEqual(c.injection_annuelle(100000, 100000), (0, 0))

    def test_never_negative(self):
        # autoconso > prod ne donne jamais un surplus négatif
        self.assertEqual(c.injection_annuelle(100000, 150000), (0, 0))

    def test_defensive_on_bad_input(self):
        self.assertEqual(c.injection_annuelle(None, None), (0, 0))
        self.assertEqual(c.injection_annuelle("x", "y"), (0, 0))


class TestSourcedConstants(SimpleTestCase):
    def test_mention_present(self):
        self.assertIn("ANRE 03/2026-02/2027", c.MENTION_82_21)
        self.assertIn("plafond en révision", c.MENTION_82_21)

    def test_cap_is_20(self):
        self.assertEqual(c.PLAFOND_INJECTION_PCT, 20)

    def test_reseau_fees(self):
        self.assertAlmostEqual(c.FRAIS_RESEAU_DH_KWH, 0.1245, places=4)
