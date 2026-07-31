"""NTAPI20 — document OpenAPI 3.1 généré À LA MAIN, sans nouvelle dépendance
lourde (ni ``drf-spectacular``, ni générateur externe) — servi en JSON par
``GET /api/public/v1/openapi.json``.

Source de vérité UNIQUE : ``docs.py`` (FG105 — déjà la référence FR de l'API
publique, lue depuis ``constants.py``). Ce module ne fait que RE-PROJETER la
même structure au format OpenAPI 3.1, pour ne jamais diverger de la doc FR ni
de l'implémentation réelle des vues.

Couvre 100 % des endpoints publics MONTÉS aujourd'hui (``public_urls.py``) :
les 5 ressources en lecture seule (``list`` + ``retrieve``) et les 3
endpoints d'écriture. ``tests_ntapi20_openapi_schema.py`` vérifie que chaque
chemin déclaré ici existe réellement dans ``public_urls.py`` (et
inversement) — une divergence future serait un bug détecté par ce test, pas
une note de doc oubliée.
"""
import re

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .docs import public_api_reference

OPENAPI_VERSION = '3.1.0'

# Repère générique un placeholder de chemin `<nom>` (ex. `<id>`, `<entite>`) —
# utilisé par `_bulk_operation` pour ne jamais dépendre d'un nom fixe.
_PATH_PLACEHOLDER_RE = re.compile(r'<(\w+)>')

# Enveloppe d'erreur NTAPI3 (Stripe-like) — dédiée à /api/public/, distincte
# du contrat interne YAPIC3.
_ERROR_SCHEMA_NAME = 'ErrorEnvelope'
_ERROR_SCHEMA = {
    'type': 'object',
    'properties': {
        'error': {
            'type': 'object',
            'properties': {
                'type': {'type': 'string'},
                'code': {'type': 'string'},
                'message': {'type': 'string'},
                'param': {'type': ['string', 'null']},
                'doc_url': {'type': 'string'},
                'request_id': {'type': ['string', 'null']},
            },
            'required': ['type', 'code', 'message', 'request_id'],
        },
    },
    'required': ['error'],
}

# NTAPI6 (débit réellement appliqué) posera ces en-têtes sur CHAQUE réponse —
# déjà documentés ici en avance de phase, comme `doc_url` anticipe NTAPI4.
_RATE_LIMIT_HEADERS = {
    'X-RateLimit-Limit': {
        'schema': {'type': 'integer'},
        'description': 'Quota maximal de la fenêtre courante.'},
    'X-RateLimit-Remaining': {
        'schema': {'type': 'integer'},
        'description': 'Requêtes restantes sur la fenêtre courante.'},
    'X-RateLimit-Reset': {
        'schema': {'type': 'integer'},
        'description': "Epoch (secondes) de réinitialisation du quota."},
}


def _error_response(description):
    return {
        'description': description,
        'content': {
            'application/json': {
                'schema': {'$ref': f'#/components/schemas/{_ERROR_SCHEMA_NAME}'}
            }
        },
    }


def _common_error_responses():
    """Réponses d'erreur communes à TOUTE opération de l'API publique."""
    return {
        '400': _error_response('Requête invalide (filtre inconnu, validation).'),
        '401': _error_response("Clé API absente ou invalide."),
        '403': _error_response("Scope manquant pour cette clé."),
        '404': _error_response("Ressource introuvable pour cette société."),
        '409': _error_response("Conflit d'idempotence (corps différent)."),
        '429': {
            **_error_response('Quota dépassé.'),
            'headers': _RATE_LIMIT_HEADERS,
        },
    }


def _list_operation(endpoint):
    params = [
        {'name': 'page', 'in': 'query',
         'schema': {'type': 'integer'}, 'description': 'Numéro de page.'},
        {'name': 'page_size', 'in': 'query',
         'schema': {'type': 'integer'}, 'description': 'Taille de page.'},
        {'name': 'ordering', 'in': 'query', 'schema': {'type': 'string'},
         'description': f"Champs triables : {', '.join(endpoint['tri'])}."},
    ]
    if endpoint.get('updated_since'):
        params.append({
            'name': 'updated_since', 'in': 'query',
            'schema': {'type': 'string', 'format': 'date-time'},
            'description': 'Synchro incrémentale (ISO-8601).'})
    for champ in endpoint.get('filtres', []):
        params.append({
            'name': champ, 'in': 'query', 'schema': {'type': 'string'},
            'description': f'Filtre par égalité sur « {champ} ».'})
    return {
        'summary': endpoint['description'],
        'security': [{'ApiKeyAuth': []}],
        'parameters': params,
        'responses': {
            '200': {
                'description': 'Liste paginée.',
                'headers': _RATE_LIMIT_HEADERS,
                'content': {'application/json': {'schema': {'type': 'object'}}},
            },
            **_common_error_responses(),
        },
    }


def _retrieve_operation(endpoint):
    return {
        'summary': f"{endpoint['description']} (détail)",
        'security': [{'ApiKeyAuth': []}],
        'parameters': [{
            'name': 'id', 'in': 'path', 'required': True,
            'schema': {'type': 'integer'},
        }],
        'responses': {
            '200': {
                'description': 'Objet trouvé.',
                'headers': _RATE_LIMIT_HEADERS,
                'content': {'application/json': {'schema': {'type': 'object'}}},
            },
            **_common_error_responses(),
        },
    }


def _write_operation(write_endpoint):
    path_params = []
    if '<id>' in write_endpoint['chemin']:
        path_params.append({
            'name': 'id', 'in': 'path', 'required': True,
            'schema': {'type': 'integer'},
        })
    success_status = '201' if write_endpoint['methode'] == 'POST' else '200'
    return {
        'summary': write_endpoint['description'],
        'security': [{'ApiKeyAuth': []}],
        'parameters': path_params + [{
            'name': 'Idempotency-Key', 'in': 'header', 'required': False,
            'schema': {'type': 'string'},
            'description': (
                'Un rejeu identique (même clé, même corps) renvoie la '
                'réponse mémorisée sans recréer l’objet.'),
        }],
        'requestBody': {
            'required': True,
            'content': {'application/json': {'schema': {'type': 'object'}}},
        },
        'responses': {
            success_status: {
                'description': 'Créé/mis à jour.',
                'content': {'application/json': {'schema': {'type': 'object'}}},
            },
            **_common_error_responses(),
        },
    }


def _bulk_operation(entry):
    """NTAPI14/15/16/43/30 — opération générique pour un endpoint
    `endpoints_bulk` (export/import/jobs/pull CSV). Contrairement à
    `_write_operation` (toujours 201/200 fixe selon la méthode), le statut de
    succès varie ici (202 pour une création de job, 200 pour un GET/relancer/
    pull) — porté explicitement par l'entrée plutôt que déduit. Tout
    placeholder `<nom>` du chemin (pas seulement `<id>`) devient un paramètre
    de chemin déclaré.
    """
    path_params = [
        {
            'name': name, 'in': 'path', 'required': True,
            'schema': {'type': 'integer' if name == 'id' else 'string'},
        }
        for name in _PATH_PLACEHOLDER_RE.findall(entry['chemin'])
    ]
    # NTAPI30 — le pull CSV Google Sheets s'authentifie par TOKEN en query
    # string (pas d'en-tête possible côté tableur), jamais par ApiKeyAuth.
    query_token = bool(entry.get('query_token_auth'))
    security = [] if query_token else [{'ApiKeyAuth': []}]
    query_params = [{
        'name': 'token', 'in': 'query', 'required': True,
        'schema': {'type': 'string'},
        'description': (
            "Clé API en clair (scope lecture seule) — aucun en-tête "
            "possible côté tableur (=IMPORTDATA())."),
    }] if query_token else []
    content_type = 'text/csv' if entry.get('response_csv') else 'application/json'
    operation = {
        'summary': entry['description'],
        'security': security,
        'parameters': path_params + query_params,
        'responses': {
            entry['success_status']: {
                'description': entry['description'],
                'headers': _RATE_LIMIT_HEADERS,
                'content': {content_type: {'schema': {'type': 'string' if content_type == 'text/csv' else 'object'}}},
            },
            **_common_error_responses(),
        },
    }
    if entry.get('request_body'):
        operation['requestBody'] = {
            'required': True,
            'content': {'application/json': {'schema': {'type': 'object'}}},
        }
    return operation


def build_openapi_schema():
    """Construit le document OpenAPI 3.1 complet — 100 % dérivé de
    `docs.public_api_reference()` (source de vérité unique, FG105)."""
    ref = public_api_reference()
    paths = {}

    for endpoint in ref['endpoints']:
        chemin = endpoint['chemin']
        paths[chemin] = {'get': _list_operation(endpoint)}
        detail_chemin = f"{chemin}{{id}}/"
        paths[detail_chemin] = {'get': _retrieve_operation(endpoint)}

    for write_endpoint in ref['endpoints_ecriture']['liste']:
        openapi_path = write_endpoint['chemin'].replace('<id>', '{id}')
        method = write_endpoint['methode'].lower()
        paths.setdefault(openapi_path, {})[method] = _write_operation(
            write_endpoint)

    for bulk_endpoint in ref.get('endpoints_bulk', {}).get('liste', []):
        openapi_path = _PATH_PLACEHOLDER_RE.sub(r'{\1}', bulk_endpoint['chemin'])
        method = bulk_endpoint['methode'].lower()
        paths.setdefault(openapi_path, {})[method] = _bulk_operation(
            bulk_endpoint)

    return {
        'openapi': OPENAPI_VERSION,
        'info': {
            'title': 'API publique Taqinor',
            'version': ref['version'],
            'description': ref['introduction'],
        },
        'servers': [{'url': ref['base_url']}],
        'components': {
            'securitySchemes': {
                'ApiKeyAuth': {
                    'type': 'apiKey', 'in': 'header', 'name': 'Authorization',
                    'description': "Format : « Api-Key <votre_cle> ».",
                },
            },
            'schemas': {_ERROR_SCHEMA_NAME: _ERROR_SCHEMA},
        },
        'security': [{'ApiKeyAuth': []}],
        'paths': paths,
    }


class PublicOpenApiSchemaView(APIView):
    """``GET /api/public/v1/openapi.json`` — document OpenAPI 3.1 public,
    aucune authentification requise (document de découverte, pas de donnée
    de société)."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(build_openapi_schema())
