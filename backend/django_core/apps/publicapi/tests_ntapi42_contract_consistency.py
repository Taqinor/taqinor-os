"""NTAPI42 — garde CI légère : cohérence du contrat de l'API publique.

Verrouille que la surface RÉELLEMENT MONTÉE (`public_urls.py`) et la doc
OpenAPI (NTAPI20, `openapi.py` / `docs.py` FG105) ne divergent JAMAIS :
ajouter un endpoint public sans le documenter fait ROUGIR ce test — les
chemins montés sont reconstruits DEPUIS `public_urls.py` lui-même (router +
`path()` explicites), jamais une seconde liste à la main qui pourrait
diverger silencieusement. Verrouille aussi que tout scope référencé par le
mapping bulk (NTAPI14/15, `EXPORT_SCOPE_BY_ENTITY`/`IMPORT_SCOPE_BY_ENTITY`)
existe bien dans `constants.ALL_SCOPES` (jamais un scope fantôme).

Le 3e volet du critère NTAPI42 (« chaque code d'erreur émis existe au catalogue
NTAPI4 ») est désormais vérifié : NTAPI4 (`publicapi/error_catalog.py`) existe,
et son catalogue est dérivé de la table du handler NTAPI3 — le test ci-dessous
verrouille l'égalité dans les DEUX sens (aucun code émis sans explication,
aucune explication fantôme).

`sandbox/reset/`, `changelog/` et `errors/` restent hors du contrat vérifié
ici : endpoints utilitaires SANS scope métier, déjà couverts par leurs propres
suites (`tests_ntapi27_sandbox.py` / `tests_ntapi24_changelog.py` /
`tests_ntapi4_error_catalog.py`).
"""
import re

from django.test import SimpleTestCase

from .constants import (
    ALL_SCOPES, EXPORT_SCOPE_BY_ENTITY, IMPORT_SCOPE_BY_ENTITY,
    PUBLIC_API_BASE,
)
from .openapi import build_openapi_schema
from .public_urls import router as public_router
from .public_urls import urlpatterns as public_urlpatterns

_PK_GROUP_RE = re.compile(r'\(\?P<pk>[^)]*\)')
# `<type:nom>` -> `{nom}` générique (ex. `<str:entite>` -> `{entite}`, NTAPI30).
_TYPED_CONVERTER_RE = re.compile(r'<(?:\w+:)?(\w+)>')
# Endpoints utilitaires publics SANS scope métier — hors du contrat
# ressources/écritures/bulk documenté en OpenAPI (voir docstring module).
_UTILITY_PATHS = {'sandbox/reset/', 'changelog/', 'errors/'}


def _router_mounted_paths():
    """Chemins `/api/public/v1/...` RÉELLEMENT montés par le routeur DRF
    (`public_urls.router`) : list/retrieve ET toute action custom (ex.
    `jobs/{id}/relancer/`). Les suffixes de format DRF (`.json`/`.csv`) et la
    vue racine du routeur sont exclus — pas des endpoints métier."""
    paths = set()
    for entry in public_router.urls:
        raw = str(entry.pattern)
        if 'format' in raw:
            continue
        raw = raw.strip('^$')
        if not raw:
            continue
        raw = _PK_GROUP_RE.sub('{id}', raw)
        paths.add(PUBLIC_API_BASE + raw)
    return paths


def _explicit_mounted_paths():
    """Chemins `/api/public/v1/...` des `path()` explicites de `public_urls.py`
    (hors `include(router.urls)`, hors endpoints utilitaires). `<int:pk>`
    suit la convention `<id>`/`{id}` de docs.py/openapi.py ; tout autre
    convertisseur nommé (ex. `<str:entite>`, NTAPI30) garde son nom."""
    paths = set()
    for entry in public_urlpatterns:
        raw = str(getattr(entry, 'pattern', ''))
        if not raw or raw in _UTILITY_PATHS:
            continue
        raw = raw.replace('<int:pk>', '<id>')
        raw = _TYPED_CONVERTER_RE.sub(r'{\1}', raw)
        paths.add(PUBLIC_API_BASE + raw)
    return paths


def _mounted_paths():
    return _router_mounted_paths() | _explicit_mounted_paths()


class Ntapi42ApiContractConsistencyTests(SimpleTestCase):
    def test_every_mounted_path_is_documented_in_openapi(self):
        """Ajouter un endpoint public sans le documenter (`docs.py` +
        `openapi.py`) fait ROUGIR ce test — l'état courant est vert."""
        schema = build_openapi_schema()
        documented = set(schema['paths'].keys())
        mounted = _mounted_paths()
        missing = mounted - documented
        self.assertEqual(
            missing, set(),
            f"Endpoint(s) monté(s) sans documentation OpenAPI : {sorted(missing)}")

    def test_no_phantom_documented_path(self):
        """L'inverse : un chemin documenté qui ne correspond à AUCUN endpoint
        réellement monté serait une doc mensongère — jamais silencieux."""
        schema = build_openapi_schema()
        documented = set(schema['paths'].keys())
        mounted = _mounted_paths()
        phantom = documented - mounted
        self.assertEqual(
            phantom, set(),
            f"Chemin(s) documenté(s) sans endpoint monté correspondant : "
            f"{sorted(phantom)}")

    def test_every_emitted_error_code_is_in_the_catalog(self):
        """3e volet NTAPI42 (débloqué par NTAPI4) : chaque code d'erreur que
        le handler NTAPI3 peut émettre existe au catalogue — et l'inverse,
        aucune explication fantôme sans code émis correspondant."""
        from .error_catalog import codes_documentes, codes_emis

        emis, documentes = codes_emis(), codes_documentes()
        self.assertEqual(
            emis - documentes, set(),
            "Code(s) d'erreur émis sans entrée au catalogue NTAPI4.")
        self.assertEqual(
            documentes - emis, set(),
            "Entrée(s) du catalogue NTAPI4 sans code d'erreur émis.")

    def test_bulk_scope_mapping_uses_only_known_scopes(self):
        combined = {**EXPORT_SCOPE_BY_ENTITY, **IMPORT_SCOPE_BY_ENTITY}
        self.assertTrue(combined, 'Le mapping bulk ne doit jamais être vide.')
        for entite, scope in combined.items():
            self.assertIn(
                scope, ALL_SCOPES,
                f"Scope {scope!r} (entité {entite!r}) absent de ALL_SCOPES.")
