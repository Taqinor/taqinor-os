"""ENF2 (C2) — le schéma OpenAPI déclare les réponses d'ERREUR réellement servies.

Constat (api-fuzz du 07/10/2026) : drf-spectacular ne documente que la réponse
de succès de chaque opération. Or TOUTE vue peut répondre 400 (validation du
corps ou des paramètres), 404 (``get_object_or_404``, module désactivé…), 429
(débit par société), 500 ; une vue authentifiée répond aussi 401/403, une
écriture 409 (unicité par société ``core.unicite``, suppression protégée).
Schemathesis classait ~10 000 réponses en « Undocumented HTTP status code » :
le contrat publié mentait par omission.

Ce crochet de post-traitement (``SPECTACULAR_SETTINGS['POSTPROCESSING_HOOKS']``)
ajoute, sur chaque opération et SEULEMENT pour les codes qu'elle ne documente
pas déjà, une réponse ``ErreurApi`` — la forme unique produite par
``core.exceptions.taqinor_exception_handler`` :

    {"detail": "...", "error": {"code", "message", "fields", "request_id"}}

Règles (documenté == réel, sans sur-déclarer) :

* 400, 404, 429, 500 — toute opération ;
* 401, 403 — seulement une opération qui déclare au moins un schéma
  d'authentification (une route publique à jeton sans authentificateur ne
  répond jamais 401) ;
* 409 — seulement une écriture (POST/PUT/PATCH/DELETE).

Le schéma ``ErreurApi`` n'exige aucune clé et tolère les clés de champ à la
racine : un 400 de validation DRF garde ses erreurs par champ à la racine
(compatibilité YAPIC3) et quelques vues historiques renvoient encore un simple
``{"detail": …}``.

Le crochet tourne APRÈS la construction du document, donc aussi sur le miroir
``api/v1/`` reconstitué par ``erp_agentique.openapi_check`` — même document.
"""
from __future__ import annotations

import copy

NOM_COMPOSANT = 'ErreurApi'
_REF = {'$ref': f'#/components/schemas/{NOM_COMPOSANT}'}

_METHODES = ('get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace')
_ECRITURES = frozenset({'post', 'put', 'patch', 'delete'})

DESCRIPTIONS = {
    '400': 'Requête invalide (validation du corps ou des paramètres).',
    '401': 'Authentification absente, invalide ou expirée.',
    '403': 'Authentifié mais non autorisé.',
    '404': 'Ressource introuvable.',
    '409': 'Conflit : doublon (unicité par société) ou suppression protégée.',
    '429': 'Trop de requêtes (limitation de débit).',
    '500': 'Erreur inattendue du serveur (identifiant `request_id` journalisé).',
}

SCHEMA_ERREUR = {
    'type': 'object',
    'description': (
        "Enveloppe d'erreur unique (core.exceptions). `error.code` est un "
        "identifiant stable (validation_error, not_authenticated, "
        "permission_denied, not_found, unique_conflict, protected_error, "
        "throttled, server_error…). Un 400 de validation porte aussi ses "
        "erreurs par champ à la racine."
    ),
    'properties': {
        'detail': {'type': 'string'},
        'error': {
            'type': 'object',
            'properties': {
                'code': {'type': 'string'},
                'message': {'type': 'string'},
                'fields': {
                    'type': 'object',
                    'nullable': True,
                    'additionalProperties': {},
                },
                'request_id': {'type': 'string', 'nullable': True},
            },
        },
    },
    'additionalProperties': {},
}


def _authentifiee(operation) -> bool:
    securite = operation.get('security')
    if not securite:
        return False
    return any(bool(exigence) for exigence in securite)


def codes_erreur(methode: str, operation: dict) -> tuple[str, ...]:
    """Codes d'erreur que cette opération peut réellement servir."""
    codes = ['400', '404', '429', '500']
    if _authentifiee(operation):
        codes += ['401', '403']
    if methode in _ECRITURES:
        codes.append('409')
    return tuple(sorted(codes))


def declarer_enveloppe_erreur(result, generator=None, request=None,
                              public=None, **kwargs):
    """Crochet POSTPROCESSING_HOOKS de drf-spectacular (mute et renvoie)."""
    chemins = result.get('paths') or {}
    utilise = False
    for item in chemins.values():
        for methode, operation in (item or {}).items():
            if methode not in _METHODES or not isinstance(operation, dict):
                continue
            reponses = operation.setdefault('responses', {})
            for code in codes_erreur(methode, operation):
                if code in reponses:
                    continue
                reponses[code] = {
                    'content': {'application/json': {'schema': dict(_REF)}},
                    'description': DESCRIPTIONS[code],
                }
                utilise = True
    if utilise:
        composants = result.setdefault('components', {})
        schemas = composants.setdefault('schemas', {})
        schemas.setdefault(NOM_COMPOSANT, copy.deepcopy(SCHEMA_ERREUR))
    return result
