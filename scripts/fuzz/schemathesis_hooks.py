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
   (ENF11 : plus de rejeu sur 401 — voir ``_REJOUER_SUR``). Un en-tête
   ``Authorization`` GÉNÉRÉ (alternative ``bearerJWT``) reçoit le même jeton
   (ENF11 — voir ``aligner_bearer``).

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
import io
import re
import struct
import zipfile
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
# ENF11 — règles par chemin (prepare_fuzz_env.REGLES_PAR_CHEMIN) : pour un
# gabarit qui correspond, le champ prend les ids du BON modèle (``lot`` de
# stock = LotEntrepot, pas ventes.LotDevis). Plus tardive = prioritaire.
FK_REGLES = [
    (re.compile(r['motif']), tuple(r['champs']), list(r['ids']),
     set(r['ids']), r.get('max'))
    for r in (_ETAT.get('fk_ids_chemin') or []) if r.get('ids')
]


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
        aligner_bearer(case, data)


# ENF11 — « Missing authentication: 67 operations returned only 401/403 »
# (api-fuzz-full 40986772772 : 1 121 opérations 401-seules sur 16 tranches,
# dont 998 routes ordinaires à cookie ; le nocturne du 23/10, 39924022026, n'en
# avait que 38, toutes SCIM / API publique / refresh). Le schéma déclare deux
# alternatives d'authentification (`[{cookieJWT}, {bearerJWT}]`) : Schemathesis
# 4.28 génère donc, sur les cas POSITIFS, un en-tête `Authorization` OPTIONNEL
# au format `_bearer_auth` = « Bearer » + une valeur d'en-tête QUELCONQUE
# (espaces, ponctuation, chaîne vide). Depuis d4ef375b4 (24/10) le serveur
# refuse, à raison (RFC 6750 token68), tout `Authorization` présent mais mal
# formé par un 401 — même avec un cookie valide. ~71 % des réponses non-2xx de
# la tranche 0 étaient ces 401 : la logique des routes n'était jamais atteinte.
# Le fournisseur pose donc le MÊME jeton valide dans l'alternative Bearer
# quand le cas en porte une — exactement ce que fait l'HttpBearerAuthProvider
# de Schemathesis. Il ne l'AJOUTE jamais (un cas « cookie seul » reste tel
# quel) et ne touche aucun cas négatif visant l'authentification :
# Schemathesis n'appelle pas `set` quand le paramètre muté est un paramètre de
# sécurité (`is_security_param_negated`), et le check `ignored_auth` retire
# toujours lui-même l'authentification déclarée.
def aligner_bearer(case, jeton):
    # CI #1176 — un cas NÉGATIF (phase coverage) porte un Authorization
    # volontairement invalide : le « réparer » rendait la requête valide et le
    # 200 obtenu devenait « API accepted schema-violating request ».
    meta = getattr(case, 'meta', None)
    if meta is not None and meta.generation.mode != GenerationMode.POSITIVE:
        return
    entetes = getattr(case, 'headers', None)
    if not entetes:
        return
    for cle in list(entetes):
        if isinstance(cle, str) and cle.lower() == 'authorization':
            entetes[cle] = f'Bearer {jeton}'


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


# ENF11 (records) — {« app.modele »: ids} : la cible ``{model, id}`` d'une
# activité / pièce jointe / étiquette / abonné désigne une ligne RÉELLE.
CIBLES = {m: list(ids) for m, ids in (_ETAT.get('cibles') or {}).items()
          if ids}


def _cible_reelle(objet):
    """``{model, id}`` → un modèle cible qui a des lignes et l'un de ses ids
    (le modèle tiré reste dans l'énumération du schéma)."""
    modele = objet.get('model')
    if not CIBLES or not isinstance(modele, str) or 'id' not in objet:
        return
    if modele not in CIBLES:
        modele = sorted(CIBLES)[zlib.crc32(modele.encode()) % len(CIBLES)]
        objet['model'] = modele
    ids = CIBLES[modele]
    objet['id'] = _id_connu(objet['id'], ids, set(ids), texte=True)


def _table_fk(chemin):
    """{champ: (ids, ensemble, longueur max)} des règles de ``chemin``."""
    table = {}
    for motif, champs, ids, ensemble, maxi in FK_REGLES:
        if motif.search(chemin or ''):
            for champ in champs:
                table[champ] = (ids, ensemble, maxi)
    return table


def _entree(nom, table):
    if nom in table:
        return table[nom]
    if nom in FK_IDS:
        return FK_IDS[nom], _FK_IDS_SET[nom], None
    return None


def _id_connu(valeur, ids, connus, texte=False):
    # Nocturne 38870650403 (Hook Error) : « ¹ » est isdigit() mais pas un int.
    if (texte and isinstance(valeur, str) and valeur.isascii()
            and valeur.isdigit()):
        choisi = _id_connu(int(valeur), ids, connus)
        return str(choisi)
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        return valeur
    if valeur in connus:
        return valeur
    return ids[valeur % len(ids)]


def _remplacer_valeur(valeur, entree, texte=False):
    ids, connus, maxi = entree
    if isinstance(valeur, list):
        nouvelle = [_id_connu(v, ids, connus, texte) for v in valeur]
        return nouvelle[:maxi] if maxi else nouvelle
    return _id_connu(valeur, ids, connus, texte)


def _remplacer_ids_fk(objet, table=None):
    """Remplace, dans ``objet`` (dict), les FK inconnues par des ids réels.

    ENF11 (achats) — récursif dans les listes d'objets : ``lignes[].produit``
    d'un BCF, ``lignes[].ligne_commande`` d'une réception… sont des FK comme
    les champs de premier niveau, et sans cela chaque création à lignes
    imbriquées partait avec « Clé primaire 0 non valide ». ENF11 (records) —
    récursif aussi dans les objets (``next.activity_type`` de ``done``)."""
    table = table or {}
    for nom, valeur in list(objet.items()):
        entree = _entree(nom, table)
        if entree is not None and not isinstance(valeur, dict):
            nouvelle = _remplacer_valeur(valeur, entree)
            # CI #997 : une clé réécrite — MÊME à l'identique — est revalidée
            # sur sa valeur VIVANTE (chaîne du fil d'un corps formulaire contre
            # ``type: integer``) : le cas positif basculait NÉGATIF et la
            # réponse 201 devenait « API accepted schema-violating request »
            # (POST portail/documents-client-portail/, client_id=0&lead_id=0).
            # On n'écrit donc que lorsque l'id change réellement.
            if nouvelle != valeur:
                objet[nom] = nouvelle
        elif isinstance(valeur, dict):
            _remplacer_ids_fk(valeur, table)
        elif isinstance(valeur, list):
            for element in valeur:
                if isinstance(element, dict):
                    _remplacer_ids_fk(element, table)


def _ids_fk_connus(case):
    meta = case.meta
    if meta is None or meta.generation.mode != GenerationMode.POSITIVE:
        return
    table = _table_fk(case.operation.path)
    corps = case.body
    if isinstance(corps, dict):
        _cible_reelle(corps)
        _remplacer_ids_fk(corps, table)
    # ENF11 — les FK de la QUERY (``?installation=``, ``?client=``, ``?lot=``)
    # aussi : un GET filtré sur un id inexistant répondait 400.
    query = getattr(case, 'query', None)
    if isinstance(query, dict):
        avant = dict(query)
        _cible_reelle(query)
        for nom, valeur in list(query.items()):
            entree = _entree(nom, table)
            if entree is not None:
                query[nom] = _remplacer_valeur(valeur, entree, texte=True)
        _retyper_query(query, avant, _query_typee(meta),
                       _types_query_publies(case.operation))


def _types_query_publies(operation):
    """{nom: type} des paramètres de query PUBLIÉS (``schema.type``)."""
    publies = {}
    for parametre in getattr(operation, 'query', None) or ():
        definition = getattr(parametre, 'definition', None) or {}
        schema = definition.get('schema') if isinstance(
            definition, dict) else None
        if isinstance(schema, dict) and isinstance(schema.get('type'), str):
            publies[getattr(parametre, 'name', None)] = schema['type']
    return publies


def _query_typee(meta):
    """Cliché TYPÉ de la query (``CaseMetadata.raw_containers``) : la phase
    coverage envoie des chaînes (forme fil) mais valide le type du schéma."""
    brutes = getattr(meta, 'raw_containers', None) or {}
    for location, valeur in brutes.items():
        if getattr(location, 'value', location) == 'query' and isinstance(
                valeur, dict):
            return valeur
    return {}


def _au_type(valeur, typee):
    """``'12'`` -> ``12`` quand la valeur générée était un entier (listes
    comprises) ; tout le reste inchangé."""
    if isinstance(typee, bool) or isinstance(valeur, bool):
        return valeur
    if isinstance(typee, int) and isinstance(valeur, str) and valeur.isdigit():
        return int(valeur)
    if isinstance(typee, list) and typee and isinstance(valeur, list):
        return [_au_type(v, typee[0]) for v in valeur]
    return valeur


def _retyper_query(query, avant, typee, publies=None):
    """CI #993 — une FK de query SUBSTITUÉE garde le type de la valeur
    générée. Schemathesis revalide une clé réécrite par un crochet sur sa
    valeur VIVANTE : ``'1'`` (chaîne) contre ``type: integer`` -> invalide ->
    le cas positif basculait NÉGATIF, et la réponse 200 (légitime : id réel)
    devenait « API accepted schema-violating request » sans aucune donnée
    invalide envoyée (17 constats du job PR, run 38505583284 :
    ``?fournisseur=1``, ``?produit=1``, ``?lead=1``…).

    api-fuzz-full 27/10 (ENF11, runs 40462160410 et 40491532345, tranche 13) —
    l'inverse : un paramètre PUBLIÉ ``type: string`` reçoit un ENTIER du lien
    stateful inféré (``tag_id`` <- ``GET /records/tags/`` ``results/*/id``) ;
    substitué (2 -> 1) il restait entier, revalidé ``1`` contre ``string`` ->
    cas « Positive test case » basculé NÉGATIF, 200 légitime signalé. Le type
    PUBLIÉ prime donc sur le cliché typé : ``string`` -> la forme fil.

    api-fuzz-full 28/10 (run 40621439470, tranche 11) — même règle pour un
    entier que le lien inféré pose SANS substitution du crochet
    (``object_id`` <- ``POST records/tagged-items/`` ``id`` sur ``GET
    audit/security/``) : toute query publiée ``string`` part en chaîne."""
    publies = publies or {}
    for nom, valeur in list(query.items()):
        if (publies.get(nom) == 'string' and isinstance(valeur, int)
                and not isinstance(valeur, bool)):
            query[nom] = str(valeur)
        elif valeur != avant.get(nom) and nom in typee:
            query[nom] = _au_type(valeur, typee[nom])


# ── 4. Ids RÉELS pour les paramètres de chemin (ENF11) ─────────────────
# Seul le PREMIER paramètre, nommé id/pk, est substitué : `{token}`,
# `{jeton}`, `{slug}`, `{key}`… et les ids imbriqués restent intacts.
_PREMIER_ID = re.compile(r'^(.*?/)\{(id|pk)\}(?:/|$)')
_COUVERTURE = {'reel': set(), 'aleatoire': set(), 'sans_inventaire': set()}
_ENTIER_TEXTE = re.compile(r'^-?[0-9]+$')


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
    # CI #1176 — la phase coverage (seule phase du job PR) rend les paramètres
    # de chemin DÉJÀ en chaîne (Schemathesis 4.28 ``_stringify_value`` : un
    # entier 0 arrive « 0 ») : sans cette forme, aucun id entier n'était
    # jamais posé (« 0 opérations avec id réel »). L'id réel suit la forme.
    if isinstance(choisi, int) and isinstance(valeur, str) and _ENTIER_TEXTE.match(valeur):
        choisi = str(choisi)
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


# ── 5. Fichiers dont le FORMAT n'est pas exprimable au schéma ──────────
# Un gabarit de dossier réglementaire se dépose en PDF SEULEMENT (règle
# métier, « le fichier reçu n'en est pas un » sinon) ; OpenAPI ne dit que
# ``format: binary``. Un cas POSITIF reçoit donc un fichier minimal VALIDE du
# format que l'opération lit (PDF, image, CSV) au lieu d'octets quelconques —
# même nature que les ids réels : l'existence/le format d'une donnée que le
# schéma ne peut pas porter. CI #997 (2) : le dépôt GED accepte PDF/PNG/JPEG/
# WebP (``store_attachment``), assemble ses photos avec Pillow, ouvre ses
# scans comme images et lit un CSV de métadonnées — des octets vides y étaient
# refusés 400 « rejected schema-compliant request ».
_PDF_MINIMAL = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
# CI #997 fuzz (2) — même règle pour l'import d'un tarif fournisseur (un
# classeur xlsx, ``_classeur_lisible``) et d'une fiche constructeur PVsyst
# (``PVObject_=`` module/onduleur, ``parse_pan_ond_bytes``) : un classeur VIDE
# (aucune ligne -> rapport d'erreurs 200, rien d'écrit) et un module sans clé.
_NS_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
_NS_PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
_NS_XLSX = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_TYPE_OOXML = 'application/vnd.openxmlformats-officedocument.spreadsheetml'
_XLSX_PARTIES = {
    '[Content_Types].xml': (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Override PartName="/xl/workbook.xml" ContentType="{_TYPE_OOXML}.sheet.main+xml"/>'
        f'<Override PartName="/xl/worksheets/sheet1.xml" ContentType="{_TYPE_OOXML}.worksheet+xml"/></Types>'),
    '_rels/.rels': (f'<Relationships xmlns="{_NS_PKG}"><Relationship Id="rId1" Type="{_NS_REL}/'
                    'officeDocument" Target="xl/workbook.xml"/></Relationships>'),
    'xl/workbook.xml': (f'<workbook xmlns="{_NS_XLSX}" xmlns:r="{_NS_REL}"><sheets>'
                        '<sheet name="Tarif" sheetId="1" r:id="rId1"/></sheets></workbook>'),
    'xl/_rels/workbook.xml.rels': (f'<Relationships xmlns="{_NS_PKG}"><Relationship Id="rId1" Type="'
                                   f'{_NS_REL}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'),
    'xl/worksheets/sheet1.xml': f'<worksheet xmlns="{_NS_XLSX}"><sheetData/></worksheet>',
}


def _xlsx_minimal():
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, 'w', zipfile.ZIP_DEFLATED) as archive:
        for nom, xml in _XLSX_PARTIES.items():
            archive.writestr(nom, '<?xml version="1.0" encoding="UTF-8"?>' + xml)
    return tampon.getvalue()


def _png_minimal(cote=2):
    """PNG ``cote`` x ``cote`` NOIR décodable par Pillow (une page NON blanche :
    la séparation de lots la prendrait sinon pour une page séparatrice)."""
    def bloc(type_, donnees):
        return (struct.pack('>I', len(donnees)) + type_ + donnees
                + struct.pack('>I', zlib.crc32(type_ + donnees) & 0xffffffff))
    ligne = b'\x00' + b'\x00\x00\x00' * cote
    return (b'\x89PNG\r\n\x1a\n'
            + bloc(b'IHDR', struct.pack('>IIBBBBB', cote, cote, 8, 2, 0, 0, 0))
            + bloc(b'IDAT', zlib.compress(ligne * cote)) + bloc(b'IEND', b''))


_PNG_MINIMAL = _png_minimal()
# CI #997 (w4) — les dépôts d'image du calepinage (rendu de toiture, photo de
# site, fond de plan, carte d'ombrage) lisent les octets magiques ; le dépôt
# d'image-document décode en plus l'image et exige 8 px de côté au moins.
_PNG_CAPTURE = _png_minimal(8)
# Plan importé (calepinage importer-plan) : un DXF R12 minimal dont le calque
# « 0 » porte UN contour fermé (rectangle 10 x 5, unité m), lisible par
# ``analyser_plan`` ; le calque et le rang d'entité du cas restent ceux du
# formulaire.
_DXF_PLAN = ('\n'.join((
    '0', 'SECTION', '2', 'HEADER', '9', '$ACADVER', '1', 'AC1009',
    '9', '$INSUNITS', '70', '6', '0', 'ENDSEC', '0', 'SECTION', '2',
    'ENTITIES', '0', 'POLYLINE', '8', '0', '66', '1', '70', '1',
    '0', 'VERTEX', '8', '0', '10', '0', '20', '0', '30', '0',
    '0', 'VERTEX', '8', '0', '10', '10', '20', '0', '30', '0',
    '0', 'VERTEX', '8', '0', '10', '10', '20', '5', '30', '0',
    '0', 'VERTEX', '8', '0', '10', '0', '20', '5', '30', '0',
    '0', 'SEQEND', '8', '0', '0', 'ENDSEC', '0', 'EOF')) + '\n').encode('ascii')
# Série météo horaire d'un fournisseur (calepinage meteo-fichier) : colonnes
# obligatoires ``horodatage`` (fuseau explicite) et ``gi_w_m2``, deux heures.
_CSV_METEO = (b'horodatage;gi_w_m2\r\n2021-01-15T12:00:00+00:00;100\r\n'
              b'2021-01-15T13:00:00+00:00;120\r\n')
# CSV de métadonnées d'un import en masse : en-têtes + UNE ligne (``nom`` requis).
_CSV_MINIMAL = b'nom,description\r\nFuzz,Import\r\n'
# Fichier d'un import générique (dry-run/commit) : un CSV à en-têtes seuls, lisible
# pour TOUTE cible ; des octets quelconques (NUL…) sont « Lecture impossible ».
_CSV_IMPORT = b'nom,email\r\n'
# Relevé bancaire (dry-run) : en-têtes de relevé seuls — lisible, 0 ligne.
_CSV_RELEVE = b'date,libelle,montant\r\n'
_GED = r'^/api/django/ged/documents/'
_CALEPINAGE = r'^/api/django/calepinage/calepinages/\{[^}]+\}/'
# (chemin, méthodes, {champ du corps: octets d'un fichier valide})
_FICHIERS_VALIDES = (
    (re.compile(r'^/api/django/calepinage/gabarits-dossiers/'),
     {'POST', 'PATCH'}, {'fichier': _PDF_MINIMAL}),
    (re.compile(_GED + r'televerser/$'), {'POST'}, {'file': _PDF_MINIMAL}),
    (re.compile(_GED + r'scan-lot/$'), {'POST'}, {'files': _PDF_MINIMAL}),
    (re.compile(_GED + r'assembler-photos/$'), {'POST'},
     {'photos': _PNG_MINIMAL}),
    (re.compile(_GED + r'deposer-lot-scans-separe/$'), {'POST'},
     {'files': _PNG_MINIMAL}),
    (re.compile(_GED + r'import-masse/$'), {'POST'}, {'csv': _CSV_MINIMAL}),
    # CI #997 (2e passe) — pièce jointe polymorphe de records : un part sans
    # nom ni octets est « Aucun fichier fourni » (400) ; le serveur valide
    # les octets magiques, inexprimable dans le schéma.
    (re.compile(r'^/api/django/records/attachments/$'), {'POST'},
     {'file': _PDF_MINIMAL}),
    # Nocturne 23/10 (run 40000624035) — avatar : le serveur lit les octets
    # magiques (PNG/JPEG/WebP, 2 Mo) → 413/415 hors schéma ; un vrai PNG au
    # cas positif. Import CSV des lignes d'une demande d'achat : un fichier
    # vide ou sans en-tête est un 409 (contenu), un non-UTF-8 un 400.
    (re.compile(r'^/api/django/users/\{[^}]+\}/avatar/$'), {'POST'},
     {'file': _PNG_MINIMAL}),
    (re.compile(r'^/api/django/installations/demandes-achat/\{[^}]+\}/'
                r'importer-lignes-csv/$'), {'POST'},
     {'fichier': b'designation,quantite,prix_estime\r\nFuzz,1,10\r\n'}),
    # CI #997 (3) — dépôt d'un document du portail : le formulaire porte un
    # fichier ``fichier`` (le serveur lit les octets magiques).
    (re.compile(r'^/api/django/portail/documents-client-portail/'),
     {'POST', 'PATCH'}, {'fichier': _PDF_MINIMAL}),
    # ERR-ENF11-FUZZ-CRM — scan d'une carte de visite : une PHOTO (octets
    # magiques PNG/JPEG/WebP lus par ``scan_carte_visite``) ; des octets vides
    # = « Aucune image fournie » (400). Sans clé OCR, le serveur répond 503.
    (re.compile(r'^/api/django/crm/leads/scan-carte/$'), {'POST'},
     {'file': _PNG_MINIMAL}),
    # ERR-ENF11-FUZZ-CRM — note de lead avec pièce jointe (multipart) : le
    # fichier est lu par ``store_attachment`` (octets magiques) ; la règle
    # « texte OU fichier » rend le fichier seul conforme au schéma.
    (re.compile(r'^/api/django/crm/leads/\{[^/]+\}/noter/$'), {'POST'},
     {'file': _PNG_MINIMAL}),
    # ERR-ENF11-FUZZ-CRM — « pièce reçue » en multipart : le fichier facultatif
    # est lu par ``store_attachment`` (octets magiques), jamais des octets vides.
    (re.compile(r'^/api/django/crm/relance-etapes/\{[^/]+\}/piece-recue/$'), {'POST'},
     {'fichier': _PDF_MINIMAL}),
    # ERR-ENF11-FUZZ-VISITES — photo d'un slot de checklist : le serveur lit
    # les octets (``store_attachment`` : image PNG/JPEG/WebP).
    (re.compile(r'^/api/django/visites/visites/\{[^/]+\}/photos/$'), {'POST'},
     {'fichier': _PNG_MINIMAL}),
    # ERR-ENF11-FUZZ-AUTOMATION — pièce jointe d'une demande d'approbation : le
    # part ``file`` nommé mais VIDE est refusé par le stockage (400) alors que
    # le schéma n'exprime que ``format: binary``.
    (re.compile(r'^/api/django/automation/approval-requests/$'), {'POST'},
     {'file': _PDF_MINIMAL}),
    # CI #997 (w4) — les dépôts de fichier d'UN calepinage : image de rendu,
    # photo de site, fond de plan, carte d'ombrage (PNG), plan importé (DXF) et
    # série météo (CSV). Un part vide ou quelconque y est un refus 400.
    (re.compile(_CALEPINAGE + r'(roof-image|photos|fond-plan|image-document)/$'),
     {'POST'}, {'image': _PNG_CAPTURE, 'photo': _PNG_CAPTURE,
                'fichier': _PNG_CAPTURE}),
    (re.compile(_CALEPINAGE + r'importer-plan/$'), {'POST'},
     {'fichier': _DXF_PLAN}),
    (re.compile(_CALEPINAGE + r'meteo-fichier/$'), {'POST'},
     {'fichier': _CSV_METEO}),
    (re.compile(r'^/api/django/imports/(dry-run|commit)/$'), {'POST'},
     {'file': _CSV_IMPORT}),
    # CI #997 (w4, ventes) — affiche 3D d'un DEVIS : le serveur lit les octets
    # magiques (PNG ou JPEG), sinon « Image invalide » (400).
    (re.compile(r'^/api/django/ventes/devis/\{[^}]+\}/roof-image/$'), {'POST'},
     {'image': _PNG_MINIMAL}),
    # CI #1001 fuzz — réimport d'un CSV de traductions / de jours fériés : des
    # octets quelconques sont « Lecture du fichier impossible » (400), le schéma
    # ne dit que ``format: binary``. Un CSV à en-têtes seuls est lisible.
    (re.compile(r'^/api/django/imports/(traductions|feries)/import/$'), {'POST'},
     {'file': _CSV_IMPORT}),
    # CI #1003 fuzz — import de vues enregistrées / de favoris : un fichier non
    # tabulaire (PNG…) est « Lecture du fichier impossible » (400) ; le schéma
    # ne dit que ``format: binary``. Un CSV à en-têtes seuls est lisible.
    (re.compile(r'^/api/django/uxviews/(saved-views|favoris)/importer/$'), {'POST'},
     {'fichier': _CSV_IMPORT}),
    # CI #1176 fuzz (aAVYqi) — aperçu d'un relevé bancaire : un PNG est
    # « Lecture du fichier impossible » (400), le schéma ne dit que
    # ``format: binary``. Un CSV de relevé à en-têtes seuls est lisible.
    (re.compile(r'^/api/django/ventes/paiements/import-releve/dry-run/$'), {'POST'},
     {'file': _CSV_RELEVE}),
    (re.compile(r'^/api/django/(stock|achats)/prix-fournisseurs/import-xlsx/$'), {'POST'},
     {'file': _xlsx_minimal()}),
    (re.compile(r'^/api/django/stock/fiches-techniques/importer-datasheet/$'), {'POST'},
     {'file': b'PVObject_=pvModule\n'}),
    # api-fuzz-full 27/10 — PDF d'une fiche technique : le serveur lit les
    # octets magiques (PDF, PNG, JPEG, WebP), inexprimable dans le schéma ;
    # des octets quelconques sont « Format non supporté » (400).
    (re.compile(r'^/api/django/stock/fiches-techniques/(\{[^}]+\}/)?$'),
     {'POST', 'PUT', 'PATCH'}, {'pdf': _PDF_MINIMAL}),
    # Relevé de toiture / drone d'un chantier : ``store_attachment`` lit les
    # octets magiques (PDF, PNG, JPEG, WebP), inexprimables dans le schéma.
    (re.compile(r'^/api/django/installations/chantiers/\{[^}]+\}/ajouter-releve/$'), {'POST'},
     {'file': _PDF_MINIMAL}),
    # CI #997 (4) - photo d'un produit : le serveur valide les octets magiques
    # (PDF, PNG, JPEG, WebP) ; un part sans octets valides est « Format non supporté ».
    (re.compile(r'^/api/django/stock/produits/\{[^}]+\}/photo/$'), {'POST'},
     {'file': _PNG_MINIMAL}),
    # ENF11 (parametres) — logo et signature de la société : le serveur lit les
    # octets magiques (PNG, JPEG ou WebP), inexprimable dans le schéma ; sans
    # image lisible, un part « conforme » répond « Format non supporté » (400).
    (re.compile(r'^/api/django/parametres/upload-(logo|signature)/$'), {'POST'},
     {'file': _PNG_MINIMAL}),
)


def _meta_sans_revalidation(case):
    """Métadonnées SANS déclencher la revalidation de ``case.meta`` : lire
    ``case.meta`` après une substitution de FK revalide le corps (et, avec des
    octets, le déclare invalide) avant que ``_rester_positif`` ait pu agir."""
    meta = getattr(case, '_meta', None)
    return meta if meta is not None else case.meta


def _octets_valides(valeur, octets):
    """``valeur`` portant ``octets``. Schemathesis range un binaire dans
    ``Binary`` (sous-classe de str portant ``.data``) : on change ses OCTETS en
    place et on rend le MÊME objet — la clé du corps n'est alors pas réécrite
    (voir ``_rester_positif``)."""
    if isinstance(getattr(valeur, 'data', None), bytes):
        valeur.data = octets
        return valeur
    if isinstance(valeur, bytes):
        return octets
    if isinstance(valeur, str):
        return octets.decode('latin-1')
    return valeur


def _fichiers_valides(case):
    meta = _meta_sans_revalidation(case)
    if meta is None or meta.generation.mode != GenerationMode.POSITIVE:
        return
    corps = case.body
    if not isinstance(corps, dict):
        return
    for chemin, methodes, champs in _FICHIERS_VALIDES:
        if (case.operation.method.upper() not in methodes
                or not chemin.match(case.operation.path)):
            continue
        for champ, octets in champs.items():
            origine = corps.get(champ)
            if isinstance(origine, list):
                # Liste de fichiers (``scan-lot``…) : chaque élément en porte un.
                for rang, element in enumerate(origine):
                    nouveau = _octets_valides(element, octets)
                    if nouveau is not element:
                        origine[rang] = nouveau
            elif origine is not None:
                nouveau = _octets_valides(origine, octets)
                if nouveau is not origine:
                    corps[champ] = nouveau


# ── 5b. Un fichier de formulaire porte TOUJOURS un nom de fichier ───────
# CI #997 (3) — Schemathesis 4.28 (``prepare_multipart_v3``) ne joint le nom de
# fichier d'un champ ``format: binary`` que si le schéma du corps est EN LIGNE.
# Dès que ce schéma référence un composant (``$ref`` vers une énumération :
# ``model`` de records/attachments, ``type_document`` du portail), le
# regroupeur le range sous ``x-bundled`` et le corps devient ``{'$ref': …}`` :
# plus de ``properties`` lues, le fichier part SANS nom — Django le lit alors
# comme un champ texte (« Aucun fichier fourni » / « n'est pas un fichier »)
# alors que la requête est conforme au schéma. Le nom manquait donc au HARNAIS,
# pas au serveur : on rend au dépôt le nom (= celui du champ) que le transport
# aurait posé pour un schéma en ligne, après avoir résolu ce ``$ref`` racine.
def _schema_corps_resolu(schema):
    reference = schema.get('$ref') if isinstance(schema, dict) else None
    if isinstance(reference, str):
        return (schema.get('x-bundled') or {}).get(
            reference.rsplit('/', 1)[-1], schema)
    # Règle de racine (``x-corps-resserre``, ``core.openapi_erreurs``) : le
    # corps devient ``{'allOf': [<corps>, <règle>]}`` — les champs binaires
    # vivent dans le membre ``$ref`` ; sans cette fusion, un fichier de
    # formulaire partait SANS nom (champ texte pour Django : « Note vide. »
    # sur ``POST crm/leads/{id}/noter/``, requête pourtant conforme).
    membres = schema.get('allOf') if isinstance(schema, dict) else None
    if isinstance(membres, list):
        regroupe = schema.get('x-bundled')
        proprietes = {}
        for membre in membres:
            if regroupe is not None and isinstance(membre, dict):
                membre = {**membre, 'x-bundled': regroupe}
            membre = _schema_corps_resolu(membre)
            if isinstance(membre, dict) and isinstance(
                    membre.get('properties'), dict):
                proprietes.update(membre['properties'])
        if proprietes:
            return {'type': 'object', 'properties': proprietes}
    return schema


def _noms_de_fichiers(operation):
    """Champs ``format: binary`` (ou listes de) du corps multipart déclaré."""
    for corps in getattr(operation, 'body', None) or ():
        if not str(getattr(corps, 'media_type', '')).lower().startswith(
                'multipart/'):
            continue
        schema = _schema_corps_resolu(corps.definition.get('schema'))
        proprietes = schema.get('properties') if isinstance(schema, dict) else None
        noms = set()
        for nom, propriete in (proprietes or {}).items():
            cible = propriete.get('items') if (
                isinstance(propriete, dict)
                and isinstance(propriete.get('items'), dict)) else propriete
            if isinstance(cible, dict) and cible.get('format') in (
                    'binary', 'base64'):
                noms.add(nom)
        return noms
    return set()


def _avec_noms_de_fichier(preparer):
    """``prepare_multipart`` de Schemathesis, dont les parts d'OCTETS d'un champ
    binaire déclaré reçoivent leur nom de fichier (``(None, octets)`` →
    ``(champ, octets)``). Les autres parts sont rendues telles quelles."""
    if getattr(preparer, '_noms_de_fichier', False):
        return preparer

    def preparation(operation, form_data, selected_content_types=None):
        fichiers, donnees = preparer(
            operation, form_data, selected_content_types)
        noms = _noms_de_fichiers(operation) if fichiers else set()
        if not noms:
            return fichiers, donnees
        corriges = []
        for nom, partie in fichiers:
            if (nom in noms and isinstance(partie, tuple) and len(partie) >= 2
                    and partie[0] is None and isinstance(partie[1], bytes)):
                partie = (nom,) + partie[1:]
            corriges.append((nom, partie))
        return corriges, donnees

    preparation._noms_de_fichier = True
    return preparation


def _installer_noms_de_fichier():
    """Pose le correctif sur chaque adaptateur OpenAPI 3.x ; rend le nombre
    d'adaptateurs corrigés (0 sans Schemathesis réel : tests du harnais)."""
    try:
        import importlib
        formdata = importlib.import_module(
            'schemathesis.specs.openapi.adapter.formdata')
    except ImportError:
        return 0
    installes = 0
    for version in ('v3_0', 'v3_1', 'v3_2'):
        try:
            adaptateur = importlib.import_module(
                f'schemathesis.specs.openapi.adapter.{version}')
        except ImportError:
            continue
        courant = getattr(adaptateur, 'prepare_multipart', None)
        if courant is getattr(formdata, 'prepare_multipart_v3', None):
            adaptateur.prepare_multipart = _avec_noms_de_fichier(courant)
            installes += 1
    return installes


_ADAPTATEURS_CORRIGES = _installer_noms_de_fichier()


# ── 5c. Une part structurée (tableau / objet) part en JSON, jamais en fichier ─
# CI #997 (4) — même cause racine que 5b : ``_collect_encoded_fields`` (transport
# requests de Schemathesis 4.28) ne pose « ``application/json`` par défaut » sur
# une propriété tableau/objet que si le schéma du corps est EN LIGNE. Un corps
# regroupé (``{'$ref': '#/x-bundled/…'}``) n'a plus de ``properties`` à lire : le
# tableau ``champs`` de POST calepinage/gabarits-dossiers partait alors en une
# part PAR ÉLÉMENT, chacune la ``repr`` Python de l'objet, sans type — et
# ``requests`` pose le nom du champ comme nom de FICHIER à toute part nue : le
# serveur recevait un fichier là où le formulaire de l'ERP envoie UN texte JSON
# (``corps.append('champs', JSON.stringify(liste))``, ReglagesGabarits.jsx) et
# répondait 400 « se donnent en liste ordonnée (reçu : InMemoryUploadedFile) ».
# Ici, après avoir résolu le ``$ref`` racine puis celui de chaque propriété, tout
# champ structuré que Schemathesis n'a pas vu est lui aussi sérialisé en JSON :
# une seule part de texte, comme le client réel. Aucun nom de fichier n'est posé
# (c'est 5b qui ne le pose QUE sur les champs ``format: binary``).
def _resoudre_propriete(propriete, schema_racine):
    reference = propriete.get('$ref') if isinstance(propriete, dict) else None
    if isinstance(reference, str):
        regroupe = (schema_racine.get('x-bundled') or {}) if isinstance(
            schema_racine, dict) else {}
        return regroupe.get(reference.rsplit('/', 1)[-1], propriete)
    return propriete


def _est_structure(propriete):
    if not isinstance(propriete, dict):
        return False
    elements = propriete.get('items')
    if isinstance(elements, dict) and elements.get('format') in (
            'binary', 'base64'):
        return False        # liste de fichiers : des fichiers, pas du JSON
    declare = propriete.get('type')
    if isinstance(declare, str):
        declare = [declare]
    if isinstance(declare, list):
        return any(t in ('object', 'array') for t in declare)
    return any(cle in propriete
               for cle in ('properties', 'items', 'additionalProperties'))


def _champs_structures(operation):
    """Champs tableau / objet du corps multipart déclaré, ``$ref`` résolus."""
    for corps in getattr(operation, 'body', None) or ():
        if not str(getattr(corps, 'media_type', '')).lower().startswith(
                'multipart/'):
            continue
        racine = corps.definition.get('schema')
        schema = _schema_corps_resolu(racine)
        proprietes = schema.get('properties') if isinstance(schema, dict) else None
        # Le regroupement vit sur la racine (``x-bundled``) : les ``$ref`` de
        # propriété se résolvent contre elle.
        return {
            nom for nom, propriete in (proprietes or {}).items()
            if _est_structure(_resoudre_propriete(propriete, racine))}
    return set()


def _avec_parts_json(collecter):
    """``_collect_encoded_fields`` de Schemathesis, complété des champs
    structurés d'un corps regroupé (``nom -> application/json``)."""
    if getattr(collecter, '_parts_json', False):
        return collecter

    def collecte(ctx):
        trouves = collecter(ctx)
        for nom in _champs_structures(ctx.case.operation):
            trouves.setdefault(nom, 'application/json')
        return trouves

    collecte._parts_json = True
    return collecte


def _installer_parts_json():
    """Pose le correctif sur le transport requests ; rend 1 si posé."""
    try:
        import importlib
        transport = importlib.import_module('schemathesis.transport.requests')
    except ImportError:
        return 0
    courant = getattr(transport, '_collect_encoded_fields', None)
    if courant is None:
        return 0
    transport._collect_encoded_fields = _avec_parts_json(courant)
    return 1


_PARTS_JSON_CORRIGEES = _installer_parts_json()


# ── 6. Un corps à fichier reste POSITIF après nos substitutions ─────────
# Schemathesis revalide tout conteneur modifié par un crochet, et déclare
# INVALIDE tout corps qui porte des octets (``_contains_bytes`` : ``Binary``
# d'un champ ``format: binary``) : un cas positif dont une FK a été remplacée
# par un id réel basculait donc NÉGATIF, et la réponse 201 devenait « API
# accepted schema-violating request » sans aucune donnée invalide envoyée
# (POST portail/documents-client-portail/). Le corps n'a reçu que des
# substitutions voulues par ce fichier : on retire son drapeau « à revalider »
# ET on réaligne son empreinte validée (Schemathesis détecte aussi une
# modification en comparant les empreintes) ; les autres conteneurs — query,
# chemin — restent revalidés.
def _contient_binaire(valeur):
    if isinstance(valeur, bytes) or isinstance(getattr(valeur, 'data', None),
                                               bytes):
        return True
    if isinstance(valeur, dict):
        return any(_contient_binaire(v) for v in valeur.values())
    if isinstance(valeur, list):
        return any(_contient_binaire(v) for v in valeur)
    return False


def _rester_positif(case, etait_positif):
    meta = getattr(case, '_meta', None)
    if not etait_positif or meta is None or not hasattr(meta, '_dirty'):
        return
    if not _contient_binaire(getattr(case, 'body', None)):
        return
    lieux = list(getattr(meta, 'components', None) or ()) + list(meta._dirty)
    for lieu in lieux:
        if getattr(lieu, 'value', lieu) != 'body':
            continue
        meta.clear_dirty(lieu)
        empreinte = getattr(case, '_hash_container', None)
        if empreinte is not None:
            meta.update_validated_hash(lieu, empreinte(case.body))


def _est_multipart(operation):
    """Le corps déclaré de l'opération est-il multipart ?"""
    return any(str(getattr(corps, 'media_type', '')).lower().startswith('multipart/')
               for corps in getattr(operation, 'body', None) or ())


def _parts_nuls_absents(case):
    """CI #1021 fuzz — un champ ``nullable`` d'un corps MULTIPART tiré à ``null``
    part sur le fil comme la chaîne « None » (``prepare_multipart``), que le
    serveur refuse (400 « « None » n'est pas un choix valide », « JSON valide »,
    « boolean ») : POST /stock/fiches-techniques/. En multipart, la seule forme
    d'un null est l'ABSENCE du part : ces clés sont retirées du corps avant
    l'envoi (le cas reste schéma-conforme, le champ est facultatif)."""
    corps = getattr(case, 'body', None)
    if not isinstance(corps, dict) or not _est_multipart(case.operation):
        return
    # Cas NÉGATIF (CI #1021 fuzz (5)) : un ``null`` tiré POUR violer le schéma
    # (« champs: Incorrect type ») doit atteindre le serveur — le retirer
    # rendait la requête conforme et l'oracle « accepted schema-violating »
    # rouge à tort ; le part « None » part alors tel quel (400 nommé attendu).
    # api-fuzz-full 25/10 — SANS revalidation : ``case.meta`` lu après la
    # substitution de FK (``_ids_fk_connus``) revalidait le corps à octets et le
    # déclarait NÉGATIF (series-lot : 23 cas positifs sur 79 basculaient).
    meta = _meta_sans_revalidation(case)
    if meta is None or meta.generation.mode != GenerationMode.POSITIVE:
        return
    for cle in [k for k, v in corps.items() if v is None]:
        corps.pop(cle)


def _est_positif(case):
    meta = case.meta
    return meta is not None and meta.generation.mode == GenerationMode.POSITIVE


@schemathesis.hook
def before_call(context, case, kwargs):
    etait_positif = _est_positif(case)
    _ids_chemin_reels(case)
    _proteger_soi(case)
    _neutraliser_politique_reseau(case)
    _ids_fk_connus(case)
    _parts_nuls_absents(case)
    _fichiers_valides(case)
    _rester_positif(case, etait_positif)
