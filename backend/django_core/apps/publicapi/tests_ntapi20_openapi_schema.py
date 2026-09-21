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
        # Les ressources montées sur le routeur lecture seule, dérivées de
        # `public_urls.py` lui-même — jamais une liste dupliquée à la main qui
        # pourrait diverger silencieusement. NTAPI16 ajoute `public-job` (suivi
        # des jobs bulk, ReadOnlyModelViewSet) aux 5 ressources métier ;
        # NTUX33 ajoute 2 ressources UX (`read:vues`/`read:favoris`) ;
        # NTP2P39 ajoute 2 ressources Procure-to-Pay (`lecture_achats`), pour
        # 11 au total (CAL214 : `public-calepinage`) : on fige l'ENSEMBLE
        # exact (plus fort qu'un simple compte), donc un 12e enregistrement
        # resterait un choix délibéré, pas un accident. SOLMVP22 (2026-09-21)
        # a retiré les 2 ressources supply chain NTSCM38 (`read:scm`) et les
        # 4 ressources BTP/EPC NTCON31 (`read:btp`) : modules `scm`/
        # `btp_chantier` sortis du produit (Groupe SOLMVP).
        registered_basenames = {r[2] for r in public_router.registry}
        self.assertEqual(registered_basenames, {
            'public-lead', 'public-devis', 'public-facture',
            'public-chantier', 'public-produit', 'public-job',
            'public-favori', 'public-saved-view',
            # NTP2P39 — 2 ressources Procure-to-Pay (`lecture_achats` :
            # demandes d'achat FG310 et RFQ FG311, sans aucun prix d'achat).
            'public-achats-demande', 'public-achats-rfq',
            # CAL214 — les conceptions de toiture (`read:calepinages`).
            'public-calepinage',
        })
        for prefix, _viewset, _basename in public_router.registry:
            list_path = f'/api/public/v1/{prefix}/'
            detail_path = f'/api/public/v1/{prefix}/{{id}}/'
            self.assertIn(list_path, schema['paths'])
            self.assertIn('get', schema['paths'][list_path])
            self.assertIn(detail_path, schema['paths'])
            self.assertIn('get', schema['paths'][detail_path])

    def test_covers_every_write_endpoint(self):
        schema = build_openapi_schema()
        expected = {
            ('/api/public/v1/leads-write/', 'post'),
            ('/api/public/v1/leads-write/{id}/', 'patch'),
            ('/api/public/v1/leads-write/{id}/activites/', 'post'),
        }
        for path, method in expected:
            self.assertIn(path, schema['paths'])
            self.assertIn(method, schema['paths'][path])

    def test_no_undocumented_paths_beyond_mounted_surface(self):
        # 10 ressources en lecture seule (`docs.py::endpoints`) × 2
        # (list+detail) = 20 (5 métier + CAL214 calepinages + 2 UX NTUX33 +
        # 2 Procure-to-Pay NTP2P39 — `public-job` n'y est PAS : ses chemins
        # viennent de `endpoints_bulk` ci-dessous) + 5 écritures (leads-write
        # POST/PATCH, activités POST, devis-write POST, tickets-write POST) +
        # 6 bulk (NTAPI14/15/16/43/30 : exports, imports, jobs list/detail,
        # jobs/<id>/relancer, exports/<entite>.csv) + 1 lecture simple
        # (NTADM42 statut de licence) = 32, + 3 (2026-09-20, NTOBS27 —
        # surface « Fiabilité » en lecture seule : fiabilite/sauvegardes/,
        # fiabilite/sla/<periode>/, fiabilite/usage/, chacune un objet unique
        # en GET) = 35 opérations, sur autant de chemins distincts (aucun
        # chemin ne cumule 2 méthodes ici) — jamais un chemin fantôme ajouté
        # par erreur. SOLMVP22 (2026-09-21) a retiré les 2 surfaces supply
        # chain NTSCM38 et les 4 ressources BTP/EPC NTCON31 (list+detail,
        # -12) ainsi que la lecture simple NTSCM38 « tableau de bord réappro »
        # (-1) : modules `scm`/`btp_chantier` sortis du produit (Groupe
        # SOLMVP), soit 48 - 13 = 35.
        schema = build_openapi_schema()
        nb_operations = sum(len(ops) for ops in schema['paths'].values())
        self.assertEqual(nb_operations, 35)

    def test_covers_licence_statut_ntadm42(self):
        schema = build_openapi_schema()
        path = '/api/public/v1/licence/statut/'
        self.assertIn(path, schema['paths'])
        self.assertIn('get', schema['paths'][path])

    def test_never_exposes_purchase_price_or_margin_fields(self):
        import json
        blob = json.dumps(build_openapi_schema())
        self.assertNotIn('prix_achat', blob)
        self.assertNotIn('marge', blob)

    def test_error_responses_use_stripe_like_envelope_schema(self):
        schema = build_openapi_schema()
        list_path = '/api/public/v1/leads/'
        error_400 = schema['paths'][list_path]['get']['responses']['400']
        ref = error_400['content']['application/json']['schema']['$ref']
        self.assertEqual(ref, '#/components/schemas/ErrorEnvelope')

    def test_rate_limit_headers_documented_on_success_and_429(self):
        schema = build_openapi_schema()
        list_op = schema['paths']['/api/public/v1/leads/']['get']
        self.assertIn('X-RateLimit-Limit', list_op['responses']['200']['headers'])
        self.assertIn('X-RateLimit-Remaining', list_op['responses']['429']['headers'])
