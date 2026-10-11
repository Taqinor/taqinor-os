"""ENF1 — crochets Schemathesis du job `api-fuzz` (release-verify.yml).

Chargé via la variable d'environnement ``SCHEMATHESIS_HOOKS`` (chemin de ce
fichier). Trois responsabilités, toutes du HARNAIS (aucun code produit) :

1. **Authentification qui n'expire jamais** (cluster C1 du 09/10). Avant, le
   workflow passait un JWT figé ``-H "Authorization: Bearer …"`` : il vivait
   30 min (``SIMPLE_JWT.ACCESS_TOKEN_LIFETIME``) pour un run de 30 min + et,
   étant un en-tête HORS schéma, le check ``ignored_auth`` ne savait pas le
   retirer (il retire le paramètre de sécurité DÉCLARÉ — le cookie
   ``access_token`` du schéma ``cookieJWT``) : la requête « sans auth »
   repartait avec le Bearer et passait. Ici un fournisseur
   ``@schemathesis.auth`` se connecte avec le compte dédié ``fuzz_admin`` et
   pose le jeton dans le cookie DÉCLARÉ ; il se reconnecte toutes les 10 min
   (ENF11 : plus de rejeu sur 401 — voir ``_REJOUER_SUR``).

2. **Désérialiseurs** ``text/csv``, ``text/html`` et binaires : sans eux,
   Schemathesis sautait la validation de ces réponses (avertissement
   « Schema validation skipped », 8 opérations le 09/10).

3. **Garde anti-auto-sabotage + ids FK connus** (``before_call``) :
   - une écriture ciblant le compte ``fuzz_admin`` lui-même
     (``/users/{id}/``) ou sa société (``/companies/{id}/`` : suppression,
     reset-demo…) est redirigée vers un id inexistant — l'opération reste
     fuzzée, mais le fuzzeur ne scie pas la branche sur laquelle il est
     assis ;
   - un cas POSITIF (conforme au schéma) dont un champ clé étrangère porte
     un id inexistant (« Clé primaire 0 non valide », cluster C12) reçoit un
     id RÉEL de la société de fuzz : le schéma OpenAPI ne peut pas exprimer
     l'existence d'une ligne, donc sans cela ``positive_data_acceptance``
     signalait des rejets légitimes. Les cas NÉGATIFS ne sont jamais
     touchés ;
   - ENF1b (run 37897343514) : une écriture qui passerait la politique
     réseau de la société de fuzz en ``enforce`` est ramenée à ``monitor``.
     Le fuzzeur créait une ``NetworkPolicy`` puis la passait en
     ``enforce`` sans aucune plage couvrant 127.0.0.1 : le middleware
     NTSEC11 refusait ensuite TOUTE requête authentifiée (403 « Adresse IP
     non autorisée par la politique réseau de votre société »), 1 760
     opérations n'ont reçu que des 403 et Schemathesis a conclu
     « Authentication stopped working mid-run ». Le comportement serveur
     est correct (c'est exactement ce qu'``enforce`` doit faire) : c'est le
     harnais qui ne doit pas se verrouiller dehors. L'endpoint reste fuzzé
     (``monitor`` journalise sans bloquer) ;
   - le rôle du compte ``fuzz_admin`` est protégé comme son compte : un
     PATCH ``permissions: []`` sur ce rôle retirerait au fuzzeur toutes ses
     permissions (403 partout pour le reste du run).
"""
from __future__ import annotations

import json
import os
import atexit
import re
import zlib

import requests
import schemathesis
from schemathesis import GenerationMode

BASE_URL = os.environ.get('FUZZ_BASE_URL', 'http://127.0.0.1:8000')
BASE_URL = BASE_URL.rstrip('/')
USERNAME = os.environ.get('FUZZ_USERNAME', 'fuzz_admin')
PASSWORD = os.environ.get('FUZZ_PASSWORD', '')
STATE_FILE = os.environ.get('FUZZ_STATE_FILE', '')

# ENF11 — inventaire d'ids de chemin ({préfixe de collection: [ids]}), écrit
# par inventorier_ids_chemin.py ; fichier absent => aucune substitution.
IDS_FILE = os.environ.get('FUZZ_IDS_FILE', '')
IDS_SEED = os.environ.get('FUZZ_IDS_SEED', 'enf11')
# 1 cas positif sur N garde son id aléatoire : la classe « 404 » reste fuzzée.
PART_INVALIDE = 4

# Id garanti inexistant (borne haute d'un entier PostgreSQL).
ID_INEXISTANT = 2147483647


def _charger_etat():
    if not STATE_FILE:
        return {}
    with open(STATE_FILE, encoding='utf-8') as fh:
        return json.load(fh)


_ETAT = _charger_etat()
FUZZ_USER_ID = _ETAT.get('user_id')
FUZZ_COMPANY_ID = _ETAT.get('company_id')
FUZZ_ROLE_ID = _ETAT.get('role_id')
# nom de champ -> liste d'ids existants dans la société de fuzz.
FK_IDS = {
    nom: list(ids)
    for nom, ids in (_ETAT.get('fk_ids') or {}).items() if ids
}
_FK_IDS_SET = {nom: set(ids) for nom, ids in FK_IDS.items()}


def _charger_ids_chemin():
    if not IDS_FILE or not os.path.exists(IDS_FILE):
        return {}
    with open(IDS_FILE, encoding='utf-8') as fh:
        brut = json.load(fh)
    return {p: list(ids) for p, ids in brut.items() if ids}


IDS_CHEMIN = _charger_ids_chemin()


# ── 1. Authentification ────────────────────────────────────────────────
# ENF11 — `retry_on=[]` : AUCUN rejeu « re-login puis renvoi » sur 401. Le run
# 38129616897 (11/10) l'a mesuré : `reauth_count: 0` (aucun rejeu n'a jamais
# rendu un 2xx) et `reauth_broke: true` (« Authentication stopped working
# mid-run »). Ces 401 sont SÉMANTIQUES, pas une expiration : jeton SCIM
# (`identity/scim/`), signature de webhook, lien public à jeton, refresh sans
# cookie de rafraîchissement. L'expiration, elle, est couverte par le
# rafraîchissement PROACTIF (600 s < 30 min de durée de vie du JWT) ; la
# révocation par le fuzzeur lui-même est exclue (schemathesis.toml, 1a).
_RAFRAICHISSEMENT_S = 600
_REJOUER_SUR = []


@schemathesis.auth(refresh_interval=_RAFRAICHISSEMENT_S, retry_on=_REJOUER_SUR)
class FuzzAdminCookieAuth:
    """Connexion ``fuzz_admin`` → cookie ``access_token`` (cookieJWT)."""

    def get(self, case, ctx):
        if not PASSWORD:
            raise RuntimeError('FUZZ_PASSWORD absent : compte non préparé')
        reponse = requests.post(
            f'{BASE_URL}/api/django/token/',
            json={'username': USERNAME, 'password': PASSWORD},
            timeout=120,
        )
        jeton = reponse.cookies.get('access_token')
        if reponse.status_code != 200 or not jeton:
            raise RuntimeError(
                f'connexion {USERNAME} refusée : HTTP {reponse.status_code}')
        return jeton

    def set(self, case, data, ctx):
        case.cookies = dict(case.cookies or {})
        case.cookies['access_token'] = data


# ── 2. Désérialiseurs ──────────────────────────────────────────────────
@schemathesis.deserializer('text/csv', 'text/html', 'text/calendar')
def deserialiser_texte(ctx, response):
    """Corps texte → chaîne (validée contre un schéma ``type: string``)."""
    encodage = response.encoding or 'utf-8'
    return response.content.decode(encodage, errors='replace')


@schemathesis.deserializer(
    'application/pdf',
    'application/octet-stream',
    'application/zip',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/png',
    'image/jpeg',
    'image/svg+xml',
)
def deserialiser_binaire(ctx, response):
    """Binaire → chaîne latin-1 SANS perte (``format: binary``)."""
    return response.content.decode('latin-1')


# ── 3. Garde anti-auto-sabotage + ids FK connus ────────────────────────
_METHODES_ECRITURE = {'POST', 'PUT', 'PATCH', 'DELETE'}
# (gabarit de chemin, id protégé)
_CIBLES_PROTEGEES = (
    (re.compile(r'^/api/django/users/\{[^}]+\}/'),
     lambda: FUZZ_USER_ID),
    (re.compile(r'^/api/django/companies/\{[^}]+\}/'),
     lambda: FUZZ_COMPANY_ID),
    (re.compile(r'^/api/django/roles/\{[^}]+\}/'),
     lambda: FUZZ_ROLE_ID),
)
# ENF1b — politique réseau de la société de fuzz (NTSEC11).
_POLITIQUE_RESEAU = re.compile(r'^/api/django/identity/network-policies/')
_MODE_BLOQUANT = 'enforce'
_MODE_SUR = 'monitor'


def _proteger_soi(case):
    if case.operation.method.upper() not in _METHODES_ECRITURE:
        return
    for gabarit, id_protege in _CIBLES_PROTEGEES:
        protege = id_protege()
        if protege is None or not gabarit.match(case.operation.path):
            continue
        for nom, valeur in list((case.path_parameters or {}).items()):
            if str(valeur) == str(protege):
                case.path_parameters[nom] = ID_INEXISTANT


def _neutraliser_politique_reseau(case):
    """``mode: enforce`` → ``monitor`` sur une écriture de la politique
    réseau : le fuzzeur (127.0.0.1) ne doit jamais se refuser l'accès."""
    if case.operation.method.upper() not in _METHODES_ECRITURE:
        return
    if not _POLITIQUE_RESEAU.match(case.operation.path):
        return
    corps = case.body
    if isinstance(corps, dict) and corps.get('mode') == _MODE_BLOQUANT:
        corps['mode'] = _MODE_SUR


def _id_connu(nom, valeur):
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        return valeur
    if valeur in _FK_IDS_SET[nom]:
        return valeur
    ids = FK_IDS[nom]
    return ids[valeur % len(ids)]


def _remplacer_ids_fk(objet):
    """Remplace, dans ``objet`` (dict), les FK inconnues par des ids réels.

    ENF11 (achats) — récursif dans les listes d'objets : ``lignes[].produit``
    d'un BCF, ``lignes[].ligne_commande`` d'une réception… sont des FK comme
    les champs de premier niveau, et sans cela chaque création à lignes
    imbriquées partait avec « Clé primaire 0 non valide »."""
    for nom, valeur in list(objet.items()):
        if nom in FK_IDS and not isinstance(valeur, dict):
            if isinstance(valeur, list):
                objet[nom] = [_id_connu(nom, v) for v in valeur]
            else:
                objet[nom] = _id_connu(nom, valeur)
        elif isinstance(valeur, list):
            for element in valeur:
                if isinstance(element, dict):
                    _remplacer_ids_fk(element)


def _ids_fk_connus(case):
    meta = case.meta
    if meta is None or meta.generation.mode != GenerationMode.POSITIVE:
        return
    corps = case.body
    if not isinstance(corps, dict):
        return
    _remplacer_ids_fk(corps)


# ── 4. Ids RÉELS pour les paramètres de chemin (ENF11) ─────────────────
# Seul le PREMIER paramètre, nommé id/pk, est substitué : `{token}`,
# `{jeton}`, `{slug}`, `{key}`… et les ids imbriqués restent intacts.
_PREMIER_ID = re.compile(r'^(.*?/)\{(id|pk)\}(?:/|$)')
_COUVERTURE = {'reel': set(), 'aleatoire': set(), 'sans_inventaire': set()}


def _bucket(cle, ids):
    return ids[zlib.crc32(f'{IDS_SEED}|{cle}'.encode()) % len(ids)]


def _ids_chemin_reels(case):
    meta = case.meta
    if meta is None or meta.generation.mode != GenerationMode.POSITIVE:
        return
    gabarit = case.operation.path
    m = _PREMIER_ID.match(gabarit)
    if not m or m.group(2) not in (case.path_parameters or {}):
        return
    ops = f'{case.operation.method.upper()} {gabarit}'
    ids = IDS_CHEMIN.get(m.group(1))
    if not ids:
        _COUVERTURE['sans_inventaire'].add(ops)
        return
    nom = m.group(2)
    valeur = case.path_parameters[nom]
    cle = f'{ops}|{valeur}'
    if zlib.crc32(f'{IDS_SEED}#{cle}'.encode()) % PART_INVALIDE == 0:
        _COUVERTURE['aleatoire'].add(ops)
        return
    choisi = _bucket(cle, ids)
    if isinstance(choisi, int) != isinstance(valeur, int):
        _COUVERTURE['aleatoire'].add(ops)
        return
    case.path_parameters[nom] = choisi
    _COUVERTURE['reel'].add(ops)


def _journal_couverture():
    if not IDS_CHEMIN and not any(_COUVERTURE.values()):
        return
    reel, sans = _COUVERTURE['reel'], _COUVERTURE['sans_inventaire']
    print(f'ENF11 ids de chemin : {len(reel)} opérations avec id réel, '
          f'{len(sans)} sans inventaire, '
          f'{len(_COUVERTURE["aleatoire"])} avec id aléatoire conservé')


atexit.register(_journal_couverture)


@schemathesis.hook
def before_call(context, case, kwargs):
    _ids_chemin_reels(case)
    _proteger_soi(case)
    _neutraliser_politique_reseau(case)
    _ids_fk_connus(case)
