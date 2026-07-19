"""ADSDEEP4 — Garde : les fenêtres d'attribution centralisées ne contiennent
JAMAIS une fenêtre morte (7d_view/28d_view, silencieusement vides depuis
2026-01-12) ; la version Graph est épinglée en UN seul point (api_version).

PUB39 (2026-07-19) — re-stamp après la refonte Meta de mars 2026 : le
click-through est LINK-CLICKS-ONLY et la fenêtre « engage-through » (valeur API
``1d_ev``) capture désormais les interactions sociales + l'engaged-view (5 s).
La liste vivante inclut donc ``1d_ev``.
"""
import inspect

from django.test import SimpleTestCase

from apps.adsengine import meta_client
from apps.adsengine.api_version import GRAPH_VERSION


class AttributionWindowsGuardTests(SimpleTestCase):
    def test_live_windows_only(self):
        # PUB39 — conforme à la doc 2026 : click 1j/7j, vue 1j, engage-through
        # (``1d_ev``, refonte mars 2026). Aucune fenêtre de vue > 1 j.
        self.assertEqual(
            meta_client.ATTRIBUTION_WINDOWS,
            ('1d_click', '7d_click', '1d_view', '1d_ev'))
        for dead in ('7d_view', '28d_view'):
            self.assertNotIn(dead, meta_client.ATTRIBUTION_WINDOWS)

    def test_engage_through_window_present(self):
        # La fenêtre engage-through (``1d_ev``) est requise depuis mars 2026 :
        # le click-through link-clicks-only ne compte plus les interactions
        # sociales — sans elle, ces conversions sont perdues.
        self.assertIn('1d_ev', meta_client.ATTRIBUTION_WINDOWS)

    def test_dead_windows_never_in_source(self):
        """Aucune fenêtre morte ne doit apparaître dans le CODE du client
        (hors la liste DEAD_ATTRIBUTION_WINDOWS + les commentaires de garde)."""
        src = inspect.getsource(meta_client)
        # Retire la déclaration volontaire de la liste interdite avant de scanner.
        src_wo_decl = src.replace(
            "DEAD_ATTRIBUTION_WINDOWS = ('7d_view', '28d_view')", '')
        # Les commentaires citent les noms morts à titre pédagogique : on ne
        # scanne donc que les lignes de CODE (hors '#').
        code_lines = [
            ln.split('#', 1)[0] for ln in src_wo_decl.splitlines()]
        code = '\n'.join(code_lines)
        for dead in meta_client.DEAD_ATTRIBUTION_WINDOWS:
            self.assertNotIn(
                f"'{dead}'", code,
                msg=f'Fenêtre morte {dead} présente dans le code du client.')

    def test_graph_version_single_source(self):
        # La version voyage depuis api_version (source unique) — jamais un
        # littéral divergent dans le client.
        self.assertEqual(meta_client.GRAPH_VERSION, GRAPH_VERSION)
        self.assertTrue(GRAPH_VERSION.startswith('v'))
