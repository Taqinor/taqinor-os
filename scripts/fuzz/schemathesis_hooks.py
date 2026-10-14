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
    if texte and isinstance(valeur, str) and valeur.isdigit():
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
        _retyper_query(query, avant, _query_typee(meta))


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


def _retyper_query(query, avant, typee):
    """CI #993 — une FK de query SUBSTITUÉE garde le type de la valeur
    générée. Schemathesis revalide une clé réécrite par un crochet sur sa
    valeur VIVANTE : ``'1'`` (chaîne) contre ``type: integer`` -> invalide ->
    le cas positif basculait NÉGATIF, et la réponse 200 (légitime : id réel)
    devenait « API accepted schema-violating request » sans aucune donnée
    invalide envoyée (17 constats du job PR, run 38505583284 :
    ``?fournisseur=1``, ``?produit=1``, ``?lead=1``…)."""
    for nom, valeur in list(query.items()):
        if nom in typee and valeur != avant.get(nom):
            query[nom] = _au_type(valeur, typee[nom])


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


def _png_minimal():
    """PNG 2x2 NOIR décodable par Pillow (une page NON blanche : la séparation
    de lots la prendrait sinon pour une page séparatrice)."""
    def bloc(type_, donnees):
        return (struct.pack('>I', len(donnees)) + type_ + donnees
                + struct.pack('>I', zlib.crc32(type_ + donnees) & 0xffffffff))
    ligne = b'\x00' + b'\x00\x00\x00' * 2
    return (b'\x89PNG\r\n\x1a\n'
            + bloc(b'IHDR', struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0))
            + bloc(b'IDAT', zlib.compress(ligne * 2)) + bloc(b'IEND', b''))


_PNG_MINIMAL = _png_minimal()
# CSV de métadonnées d'un import en masse : en-têtes + UNE ligne (``nom`` requis).
_CSV_MINIMAL = b'nom,description\r\nFuzz,Import\r\n'
_GED = r'^/api/django/ged/documents/'
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
    (re.compile(r'^/api/django/(stock|achats)/prix-fournisseurs/import-xlsx/$'), {'POST'},
     {'file': _xlsx_minimal()}),
    (re.compile(r'^/api/django/stock/fiches-techniques/importer-datasheet/$'), {'POST'},
     {'file': b'PVObject_=pvModule\n'}),
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
    _fichiers_valides(case)
    _rester_positif(case, etait_positif)
