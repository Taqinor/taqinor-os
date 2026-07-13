"""YAPIC11 — sonde de parité de surface API : tout viewset ModelViewSet
enregistré (via les routers, comme YAPIC2) a AU MOINS un mécanisme de
tri OU de recherche déclaré (``ordering_fields`` non vide/non
``'__all__'``, OU ``search_fields`` présent).

DB-free (AST uniquement, réutilise le scan de
``tests/test_api_ordering_whitelist.py`` — YAPIC2, dont ce test est la
suite : même énumération "viewsets enregistrés via les routers").

RATCHET (même convention que YAPIC2/``core/tests/test_action_permissions.py``) :
empiriquement, AUCUN des viewsets qui échouaient déjà le contrôle
"ordering_fields" de YAPIC2 (212, cf. ``ORDERING_WHITELIST_EXEMPT``) ne
porte non plus de ``search_fields`` — le baseline de ce test est donc
IDENTIQUE à celui de YAPIC2 (vérifié par un balayage combiné avant
d'écrire ce fichier). Un NOUVEAU viewset sans ni l'un ni l'autre, absent
de cette liste, fait échouer le test.
"""
from __future__ import annotations

import ast
import functools

from django.test import SimpleTestCase

from tests.test_api_ordering_whitelist import (
    ORDERING_WHITELIST_EXEMPT,
    _iter_view_files,
    _registered_viewsets,
)

# YAPIC11 — endpoints singleton/agrégats explicitement exemptés (jamais une
# "liste métier" au sens du sondage — pas de notion de tri/recherche
# significative). Vide aujourd'hui : aucun viewset enregistré via
# router.register() dans ce repo n'est un singleton pur (les singletons
# connus, ex. CompanyProfile, sont exposés par des vues dédiées hors
# ModelViewSet/router — jamais scannés ici).
SINGLETON_OR_AGGREGATE_EXEMPT: set[str] = set()


@functools.lru_cache(maxsize=None)
def _app_class_config(app: str):
    """{class_name: has_tri_ou_recherche} for EVERY class in the app's view
    files — computed ONCE per app (cached), not once per registered
    viewset: an app with N viewsets would otherwise re-glob + re-parse all
    its view files N times (the same O(files x lookups) trap fixed in
    scripts/check_on_delete.py's YDATA1/2 perf fix)."""
    config = {}
    for path in _iter_view_files(app):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            has_search = False
            ordering_ok = False
            for stmt in node.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                targets = [t.id for t in stmt.targets
                           if isinstance(t, ast.Name)]
                if "search_fields" in targets:
                    has_search = True
                if "ordering_fields" in targets:
                    value = stmt.value
                    if isinstance(value, ast.Constant):
                        ordering_ok = value.value not in (None, "__all__")
                    elif isinstance(value, (ast.List, ast.Tuple)):
                        ordering_ok = True
            config[node.name] = has_search or ordering_ok
    return config


def _has_tri_ou_recherche(app: str, class_name: str):
    """Retourne True si le viewset déclare ordering_fields (non vide/non
    '__all__') OU search_fields ; None si la classe est introuvable."""
    return _app_class_config(app).get(class_name)


def scan_noncompliant_viewsets():
    violations = []
    for app, class_name in _registered_viewsets():
        result = _has_tri_ou_recherche(app, class_name)
        if result is None:
            continue
        if not result:
            violations.append(f"{app}.{class_name}")
    return sorted(violations)


class ApiSurfaceParityTests(SimpleTestCase):

    def setUp(self):
        self.violations = set(scan_noncompliant_viewsets())

    def test_no_new_viewset_lacks_ordering_or_search(self):
        exempt = ORDERING_WHITELIST_EXEMPT | SINGLETON_OR_AGGREGATE_EXEMPT
        new_violations = self.violations - exempt
        self.assertEqual(
            new_violations, set(),
            "NOUVEAU(X) viewset(s) sans AUCUN mécanisme de tri/recherche "
            "(ni ordering_fields ni search_fields) — voir YAPIC11 :\n  "
            + "\n  ".join(sorted(new_violations)))

    def test_baseline_matches_yapic2_ordering_baseline(self):
        """Documente/verrouille le constat : aucun des 212 viewsets déjà
        signalés par YAPIC2 n'a de search_fields — si une future correction
        ajoute un search_fields à l'un d'eux sans ordering_fields, il doit
        sortir du baseline YAPIC2 aussi (autrement le ratchet mentirait)."""
        stale = ORDERING_WHITELIST_EXEMPT - self.violations
        self.assertEqual(
            stale, set(),
            "Un viewset du baseline YAPIC2 a désormais un tri OU une "
            "recherche — retirez-le de ORDERING_WHITELIST_EXEMPT ET "
            "confirmez qu'il est bien conforme.")
