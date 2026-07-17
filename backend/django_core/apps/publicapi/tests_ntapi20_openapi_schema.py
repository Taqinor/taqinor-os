"""NTAPI20 — document OpenAPI 3.1 servi par `GET /api/public/v1/openapi.json`.

Couvre : accessible sans clé API (document de découverte), structure OpenAPI
3.1 minimale valide (`openapi`/`info`/`paths`/`components`), et couverture à
100 % des endpoints publics réellement MONTÉS (`public_urls.py`) — une
divergence future entre les deux serait un bug détecté ICI, pas une note de
doc oubliée. Aucune fuite de `prix_achat`/marge dans le schéma généré.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from .openapi import build_openapi_schema
from .public_urls import router as public_router


class Ntapi20OpenApiSchemaTests(TestCase):
    def test_endpoint_accessible_without_api_key(self):
        resp = APIClient().get('/api/public/v1/openapi.json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['openapi'], '3.1.0')

    def test_minimal_openapi_structure(self):
        schema = build_openapi_schema()
        for key in ('openapi', 'info', 'servers', 'paths', 'components'):
            self.assertIn(key, schema)
        self.assertIn('securitySchemes', schema['components'])
        self.assertIn('ApiKeyAuth', schema['components']['securitySchemes'])
        self.assertIn('schemas', schema['components'])
        self.assertIn('ErrorEnvelope', schema['components']['schemas'])

    def test_covers_every_read_only_resource_list_and_detail(self):
        schema = build_openapi_schema()
        # Les 5 ressources en lecture (leads/devis/factures/chantiers/produits),
        # dérivées de `public_urls.py` lui-même — jamais une liste dupliquée à
        # la main qui pourrait diverger silencieusement.
        registered_basenames = {r[2] for r in public_router.registry}
        self.assertEqual(len(registered_basenames), 5)
        for prefix, _viewset, _basename in public_router.registry:
            list_path = f'/api/public/{prefix}/'
            detail_path = f'/api/public/{prefix}/{{id}}/'
            self.assertIn(list_path, schema['paths'])
            self.assertIn('get', schema['paths'][list_path])
            self.assertIn(detail_path, schema['paths'])
            self.assertIn('get', schema['paths'][detail_path])

    def test_covers_every_write_endpoint(self):
        schema = build_openapi_schema()
        expected = {
            ('/api/public/leads-write/', 'post'),
            ('/api/public/leads-write/{id}/', 'patch'),
            ('/api/public/leads-write/{id}/activites/', 'post'),
        }
        for path, method in expected:
            self.assertIn(path, schema['paths'])
            self.assertIn(method, schema['paths'][path])

    def test_no_undocumented_paths_beyond_mounted_surface(self):
        # 5 ressources × 2 (list+detail) + 3 écritures = 13 opérations, sur
        # au plus 5*2 + 3 = 13 chemins distincts (les 3 écritures utilisent
        # 3 chemins différents) — jamais un chemin fantôme ajouté par erreur.
        schema = build_openapi_schema()
        nb_operations = sum(len(ops) for ops in schema['paths'].values())
        self.assertEqual(nb_operations, 13)

    def test_never_exposes_purchase_price_or_margin_fields(self):
        import json
        blob = json.dumps(build_openapi_schema())
        self.assertNotIn('prix_achat', blob)
        self.assertNotIn('marge', blob)

    def test_error_responses_use_stripe_like_envelope_schema(self):
        schema = build_openapi_schema()
        list_path = '/api/public/leads/'
        error_400 = schema['paths'][list_path]['get']['responses']['400']
        ref = error_400['content']['application/json']['schema']['$ref']
        self.assertEqual(ref, '#/components/schemas/ErrorEnvelope')

    def test_rate_limit_headers_documented_on_success_and_429(self):
        schema = build_openapi_schema()
        list_op = schema['paths']['/api/public/leads/']['get']
        self.assertIn('X-RateLimit-Limit', list_op['responses']['200']['headers'])
        self.assertIn('X-RateLimit-Remaining', list_op['responses']['429']['headers'])
