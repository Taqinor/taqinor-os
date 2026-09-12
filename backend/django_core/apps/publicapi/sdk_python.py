"""NTAPI28 — générateur de SDK Python, dérivé de l'OpenAPI (NTAPI20).

Produit un client Python MINIMAL et sans dépendance externe (``urllib`` de la
stdlib) : authentification par clé d'API, pagination automatique, gestion du
429 avec respect de ``Retry-After``, et une méthode typée par ressource.

POURQUOI UN GÉNÉRATEUR MAISON PLUTÔT QU'``openapi-generator``. Celui-ci
produirait des milliers de lignes, exigerait Java, et sortirait un client dont
plus personne dans ce dépôt ne saurait expliquer le comportement sur un 429.
Le besoin réel tient en cinquante lignes : lire, paginer, réessayer. Et
surtout, le code émis est DÉRIVÉ de ``openapi.build_openapi_schema()`` — donc
de ``docs.public_api_reference()``, la source de vérité unique (FG105) : un
endpoint ajouté sans être documenté n'apparaît pas dans le SDK, et la garde
NTAPI42 rougit avant.

Le générateur ÉMET DU TEXTE ; il n'écrit nulle part de lui-même. C'est
l'appelant (commande ``gen_sdk_python``, ou un test) qui choisit la
destination — l'artefact versionné visé par le plan est ``docs/sdk/python/``.
"""
from __future__ import annotations

import re

NOM_MODULE = 'taqinor_client.py'

# `/api/public/v1/leads/` → `leads` ; ignore tout chemin paramétré (`{id}`) et
# les sous-chemins (`scm/politiques-stock`), qui ne sont pas des collections
# listables au sens « pagination simple ».
_COLLECTION_RE = re.compile(r'^/api/public/v1/([a-z0-9\-]+)/$')

# Chemins qui ressemblent à une collection mais n'en sont pas : documents de
# découverte, endpoints utilitaires, ou flux à curseur (qui a sa PROPRE
# méthode, `iter_events`, parce que sa pagination n'est pas `?page=`).
_NON_COLLECTIONS = {'errors', 'changelog', 'events', 'exports', 'imports',
                    'oauth', 'sandbox'}


def collections(schema):
    """Noms des collections paginées listables, depuis le document OpenAPI."""
    trouvees = []
    for chemin, operations in sorted((schema.get('paths') or {}).items()):
        if 'get' not in operations:
            continue
        match = _COLLECTION_RE.match(chemin)
        if not match:
            continue
        nom = match.group(1)
        if nom in _NON_COLLECTIONS or nom in trouvees:
            continue
        trouvees.append(nom)
    return trouvees


def _methode_collection(nom):
    """Méthode Python d'une collection. Le nom est un identifiant sûr : il
    vient d'un chemin déjà contraint par `_COLLECTION_RE` ([a-z0-9-]+)."""
    attribut = nom.replace('-', '_')
    return f'''
    def list_{attribut}(self, **filtres):
        """Page unique de « {nom} » (dict de la réponse paginée)."""
        return self._get("{nom}/", filtres)

    def iter_{attribut}(self, **filtres):
        """Itère TOUTES les pages de « {nom} », objet par objet."""
        return self._iter_pages("{nom}/", filtres)
'''


_ENTETE = '''"""Client Python de l\'API publique Taqinor — GÉNÉRÉ, NE PAS ÉDITER.

Généré depuis le document OpenAPI de l\'API (NTAPI20/NTAPI28). Toute
modification sera écrasée : corrigez le générateur
(`apps/publicapi/sdk_python.py`), puis régénérez.

Sans dépendance externe (stdlib seulement).

    from taqinor_client import TaqinorClient
    client = TaqinorClient("tqk_live_…")
    for lead in client.iter_leads(stage="nouveau"):
        print(lead["nom"])
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION_API = "{version}"
BASE_URL_DEFAUT = "{base_url}"
# Nombre maximum de reprises sur 429. Au-delà, l\'erreur remonte : un client qui
# réessaierait indéfiniment masquerait un quota réellement épuisé.
MAX_REPRISES_429 = {max_reprises}
# Attente de repli quand la réponse 429 ne porte pas de `Retry-After`.
ATTENTE_429_DEFAUT = 5


class TaqinorApiError(Exception):
    """Erreur renvoyée par l\'API (enveloppe NTAPI3).

    ``code`` est le slug stable (`validation_error`, `permission_denied`…) —
    jamais le message, qui peut changer ou être traduit. Son explication
    complète est lisible sur `/api/public/v1/errors/#<code>`.
    """

    def __init__(self, statut, corps):
        erreur = (corps or {{}}).get("error") or {{}}
        self.statut = statut
        self.code = erreur.get("code") or "server_error"
        self.message = erreur.get("message") or "Erreur inconnue."
        self.param = erreur.get("param")
        self.request_id = erreur.get("request_id")
        self.doc_url = erreur.get("doc_url")
        super().__init__(f"[{{statut}}] {{self.code}} — {{self.message}}")


class TaqinorClient:
    """Client de l\'API publique Taqinor.

    Authentification par clé d\'API (`Authorization: Api-Key <clé>`). Un jeton
    OAuth2 `client_credentials` s\'utilise via `TaqinorClient(token=…)`, qui
    envoie `Authorization: Bearer <jeton>`.
    """

    def __init__(self, cle=None, *, token=None, base_url=BASE_URL_DEFAUT,
                 timeout=30):
        if not cle and not token:
            raise ValueError("Fournissez une clé d\'API ou un jeton OAuth2.")
        self._cle = cle
        self._token = token
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        # Dernier état de quota lu dans les en-têtes `X-RateLimit-*` (NTAPI6) :
        # un intégrateur peut ralentir AVANT de se faire throttler.
        self.rate_limit = {{}}

    # ── Transport ────────────────────────────────────────────────────────
    def _entetes(self):
        valeur = (f"Bearer {{self._token}}" if self._token
                  else f"Api-Key {{self._cle}}")
        return {{"Authorization": valeur, "Accept": "application/json"}}

    def _ouvrir(self, url):
        """Un aller-retour HTTP. Isolé pour être remplaçable en test."""
        requete = urllib.request.Request(url, headers=self._entetes())
        return urllib.request.urlopen(requete, timeout=self.timeout)

    def _lire_rate_limit(self, entetes):
        for cle_http, nom in (("X-RateLimit-Limit", "limit"),
                              ("X-RateLimit-Remaining", "remaining"),
                              ("X-RateLimit-Reset", "reset")):
            brut = entetes.get(cle_http)
            if brut is not None:
                try:
                    self.rate_limit[nom] = int(brut)
                except (TypeError, ValueError):
                    pass

    def _get(self, chemin, params=None):
        url = self.base_url + chemin
        params = {{k: v for k, v in (params or {{}}).items() if v is not None}}
        if params:
            url += "?" + urllib.parse.urlencode(params)
        for tentative in range(MAX_REPRISES_429 + 1):
            try:
                reponse = self._ouvrir(url)
            except urllib.error.HTTPError as exc:
                corps = _charger_json(exc)
                self._lire_rate_limit(dict(exc.headers or {{}}))
                # 429 : on RESPECTE `Retry-After` plutôt qu\'un backoff inventé
                # — le serveur sait quand la fenêtre se rouvre, pas nous.
                if exc.code == 429 and tentative < MAX_REPRISES_429:
                    time.sleep(_attente_429(exc.headers))
                    continue
                raise TaqinorApiError(exc.code, corps) from None
            with reponse:
                self._lire_rate_limit(dict(reponse.headers or {{}}))
                return _charger_json(reponse)
        raise TaqinorApiError(429, {{"error": {{
            "code": "throttled",
            "message": "Quota toujours dépassé après plusieurs reprises."}}}})

    def _iter_pages(self, chemin, params=None):
        """Itère les objets de TOUTES les pages (`?page=`), sans jamais boucler.

        S\'arrête sur une page vide OU sur l\'absence de `next` : une API qui
        renverrait éternellement la même page ne doit pas figer l\'appelant.
        """
        params = dict(params or {{}})
        page = 1
        vues = 0
        while True:
            params["page"] = page
            charge = self._get(chemin, params)
            resultats = charge.get("results")
            if resultats is None:  # réponse non paginée : un seul lot
                resultats = charge if isinstance(charge, list) else [charge]
            if not resultats:
                return
            for objet in resultats:
                vues += 1
                yield objet
            total = charge.get("count")
            if not charge.get("next") or (total is not None and vues >= total):
                return
            page += 1

    # ── Flux d\'évènements (curseur, NTAPI17) ─────────────────────────────
    def iter_events(self, after=0, limit=100):
        """Itère le flux d\'évènements par CURSEUR jusqu\'à épuisement.

        Distinct de `iter_*` : la pagination du flux n\'est pas `?page=` mais
        `?after=<sequence>` — c\'est ce qui garantit qu\'une insertion
        concurrente ne fait jamais sauter une ligne.
        """
        curseur = after
        while True:
            charge = self._get("events/", {{"after": curseur, "limit": limit}})
            resultats = charge.get("results") or []
            if not resultats:
                return
            for evenement in resultats:
                yield evenement
            suivant = charge.get("next_after")
            if suivant is None or suivant == curseur:
                return
            curseur = suivant
{methodes}

def _charger_json(reponse):
    try:
        brut = reponse.read()
    except Exception:  # noqa: BLE001
        return {{}}
    if not brut:
        return {{}}
    try:
        return json.loads(brut.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {{}}


def _attente_429(entetes):
    brut = (entetes or {{}}).get("Retry-After")
    try:
        return max(1, int(brut))
    except (TypeError, ValueError):
        return ATTENTE_429_DEFAUT
'''


def generer(schema, *, max_reprises=3):
    """Renvoie le CODE SOURCE du client Python, dérivé de ``schema``."""
    methodes = ''.join(_methode_collection(nom) for nom in collections(schema))
    servers = schema.get('servers') or [{}]
    return _ENTETE.format(
        version=(schema.get('info') or {}).get('version', '1'),
        base_url=servers[0].get('url', '/api/public/v1/'),
        max_reprises=int(max_reprises),
        methodes=methodes,
    )


def generer_depuis_le_schema_courant(**kwargs):
    """Confort : génère depuis l'OpenAPI RÉEL de ce déploiement."""
    from .openapi import build_openapi_schema

    return generer(build_openapi_schema(), **kwargs)


def ecrire(dossier, *, max_reprises=3):
    """Écrit le SDK dans ``dossier`` (créé au besoin). Renvoie le chemin."""
    import pathlib

    cible = pathlib.Path(dossier)
    cible.mkdir(parents=True, exist_ok=True)
    fichier = cible / NOM_MODULE
    fichier.write_text(
        generer_depuis_le_schema_courant(max_reprises=max_reprises),
        encoding='utf-8')
    return fichier
