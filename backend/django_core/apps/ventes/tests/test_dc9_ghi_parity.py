"""DC9 — parité de la table GHI (Python ⇄ solar.js) + productible réconcilié.

La table d'irradiance GHI mensuelle était dupliquée entre
``quote_engine/constants.py`` (source Python unique) et ``solar.js`` (miroir
front). Ce test lit la table du JS et la compare à la constante Python.
AMOT47 — la troisième copie du productible de référence (une constante sans
lecteur) a été supprimée : le repère est CompanyProfile.productible_kwh_kwc.
"""
import os
import re

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

    def test_productible_constante_morte_retiree(self):
        # AMOT47 — ``constants.PRODUCTIBLE_DEFAUT`` (troisième copie du 1600,
        # sans lecteur) est SUPPRIMÉE : le repère canonique reste
        # ``CompanyProfile.productible_kwh_kwc``.
        self.assertFalse(hasattr(constants, 'PRODUCTIBLE_DEFAUT'))
