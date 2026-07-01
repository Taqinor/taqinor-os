"""DC9 — parité de la table GHI (Python ⇄ solar.js) + productible réconcilié.

La table d'irradiance GHI mensuelle était dupliquée entre
``quote_engine/constants.py`` (source Python unique) et ``solar.js`` (miroir
front). Ce test lit la table du JS et la compare à la constante Python, et
vérifie que le productible de RÉFÉRENCE documenté (constants.PRODUCTIBLE_DEFAUT)
est aligné sur le défaut CompanyProfile.productible_kwh_kwc.
"""
import os
import re

from decimal import Decimal

from django.test import SimpleTestCase

from apps.ventes.quote_engine import constants

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
SOLAR_JS = os.path.join(
    _REPO_ROOT, 'frontend', 'src', 'features', 'ventes', 'solar.js')


def _parse_solarjs_ghi():
    """Extrait le tableau `export const GHI = [ ... ]` de solar.js."""
    with open(SOLAR_JS, encoding='utf-8') as fh:
        src = fh.read()
    m = re.search(r'export const GHI\s*=\s*\[(.*?)\]', src, re.DOTALL)
    if not m:
        return None
    nums = re.findall(r'-?\d+(?:\.\d+)?', m.group(1))
    return [float(x) for x in nums]


class TestDC9GhiParity(SimpleTestCase):
    def test_ghi_table_mirrors_between_python_and_js(self):
        js_ghi = _parse_solarjs_ghi()
        self.assertIsNotNone(js_ghi, "GHI introuvable dans solar.js")
        self.assertEqual(len(js_ghi), 12)
        self.assertEqual(len(constants.GHI), 12)
        for i, (py, js) in enumerate(zip(constants.GHI, js_ghi)):
            self.assertAlmostEqual(
                py, js, places=2,
                msg=f"GHI[{i}] diverge : Python {py} ≠ solar.js {js}")

    def test_productible_default_aligns_with_company_profile(self):
        # DC9 — le productible de référence documenté suit le défaut du profil.
        from apps.parametres.models import CompanyProfile
        field = CompanyProfile._meta.get_field('productible_kwh_kwc')
        self.assertEqual(
            Decimal(str(constants.PRODUCTIBLE_DEFAUT)),
            Decimal(str(field.default)),
            "constants.PRODUCTIBLE_DEFAUT doit égaler le défaut "
            "CompanyProfile.productible_kwh_kwc (source canonique).")
