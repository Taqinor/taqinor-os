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
import re

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


# ── ERR-ENF11-FUZZ-CORE — motif des décimaux « chaîne » ─────────────────────
# drf-spectacular publie un ``DecimalField`` (``coerce_to_string``) avec le
# motif ``^-?\d{0,N}(?:\.\d{0,M})?$`` : il accepte ``""``, ``"-"`` et ``"."``,
# que DRF refuse (« Un nombre valide est requis. »). Constat api-fuzz du 11/10 :
# ``POST core/paiements-en-ligne/ {"montant": ""}`` = requête CONFORME refusée.
# Le motif corrigé exige au moins un chiffre, bornes inchangées.
_MOTIF_DECIMAL = re.compile(
    re.escape(r'^-?\d{0,') + r'(\d+)' + re.escape(r'}(?:\.\d{0,')
    + r'(\d+)' + re.escape(r'})?$') + '$')


def motif_decimal_strict(motif):
    """Motif décimal exigeant au moins un chiffre ; ``None`` si ``motif``
    n'est pas celui de drf-spectacular."""
    trouve = _MOTIF_DECIMAL.match(motif or '')
    if trouve is None:
        return None
    entiers, decimales = trouve.groups()
    if decimales == '0':
        return rf'^-?\d{{1,{entiers}}}\.?$'
    return (rf'^-?(?:\d{{1,{entiers}}}(?:\.\d{{0,{decimales}}})?'
            rf'|\.\d{{1,{decimales}}})$')


# Une chaîne de requête non vide (``minLength`` >= 1, publié par
# drf-spectacular pour un ``CharField`` sans ``allow_blank``) est d'abord
# ROGNÉE par DRF (``trim_whitespace``) : un saut de ligne ou une espace
# insécable seuls deviennent une chaîne vide, refusée (« Ce champ ne peut être
# vide. »). Le motif ``\S`` publie cette règle (constat : ``PATCH
# core/ui-boutons/{id}/`` avec une ``cible`` faite d'un saut de ligne,
# requête conforme refusée).
MOTIF_NON_BLANC = r'\S'


# CI #956 (api-fuzz « Response violates schema », parametres/delete-logo) — un
# ``EmailField``/``URLField`` à blanc autorisé est publié « adresse valide OU
# chaîne vide » (``anyOf``, extension ``apps.crm.champs_api``) ; mais
# drf-spectacular REPOSE ensuite ``format: uri|email`` à la racine depuis les
# validateurs du champ (``_map_field_validators``), et ``""`` violait de
# nouveau le schéma. Le ``format`` racine qu'une branche ``anyOf`` porte déjà
# est redondant : il est retiré, la branche fait foi.
def _format_racine_redondant(noeud):
    forme = noeud.get('format')
    return bool(forme) and any(
        isinstance(b, dict) and b.get('format') == forme
        for b in noeud.get('anyOf') or ())


#: ERR-ENF11-FUZZ-CORE — extension posée sur un ``OpenApiParameter`` de
#: requête qui transporte un objet JSON SÉRIALISÉ (``?filtre={"periode":…}``) :
#: sa valeur est le schéma de l'objet. Publié en ``type: string``, n'importe
#: quelle chaîne était conforme puis refusée (« JSON invalide », 400) ; le
#: crochet le republie en ``content: application/json`` (OpenAPI 3.0, §
#: Parameter Object) — le contrat dit enfin « un objet JSON, encodé ».
EXTENSION_CONTENU_JSON = 'x-contenu-json'


def _parametre_contenu_json(noeud):
    schema = noeud.pop(EXTENSION_CONTENU_JSON, None)
    if schema is None or noeud.get('in') != 'query':
        return
    noeud.pop('schema', None)
    noeud['content'] = {'application/json': {'schema': schema}}


#: ERR-ENF11-FUZZ-CORE — extension d'OPÉRATION (``extend_schema(extensions=
#: {EXTENSION_CORPS_RESSERRE: <schéma>})``) : règle de validation d'une
#: opération que son composant de requête, partagé, ne peut pas porter (ex.
#: ``steps`` obligatoire à la CRÉATION d'une définition de workflow, facultatif
#: à sa mise à jour). Le crochet la combine en ``allOf`` au corps publié de
#: CETTE opération seulement — aucun composant ne change de nom ni de forme.
EXTENSION_CORPS_RESSERRE = 'x-corps-resserre'


def _corps_resserre(noeud):
    regle = noeud.pop(EXTENSION_CORPS_RESSERRE, None)
    corps = noeud.get('requestBody') if regle is not None else None
    for media in (corps or {}).get('content', {}).values():
        media['schema'] = {'allOf': [media['schema'], regle]}


def _chaine_non_blanche(noeud):
    return (noeud.get('type') == 'string' and noeud.get('minLength', 0) >= 1
            and not any(cle in noeud for cle in ('pattern', 'format', 'enum')))


def aligner_motifs_sur_drf(result, generator=None, request=None,
                           public=None, **kwargs):
    """Crochet POSTPROCESSING_HOOKS : les motifs du document disent ce que
    DRF accepte VRAIMENT — décimal « chaîne » avec au moins un chiffre,
    chaîne non vide jamais faite que de blancs. Les composants de RÉPONSE ne
    portent pas de ``minLength`` (drf-spectacular ne le pose qu'en requête)."""
    pile = [result]
    while pile:
        noeud = pile.pop()
        if isinstance(noeud, dict):
            _parametre_contenu_json(noeud)
            _corps_resserre(noeud)
            if noeud.get('format') == 'decimal':
                strict = motif_decimal_strict(noeud.get('pattern'))
                if strict:
                    noeud['pattern'] = strict
            elif _chaine_non_blanche(noeud):
                noeud['pattern'] = MOTIF_NON_BLANC
            if _format_racine_redondant(noeud):
                del noeud['format']
            pile.extend(noeud.values())
        elif isinstance(noeud, list):
            pile.extend(noeud)
    return result
