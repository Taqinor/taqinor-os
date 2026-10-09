"""VEIL13 — Client ``ads_archive`` ISOLÉ, LECTURE SEULE, sans contournement de quota.

Ce client ne partage RIEN avec le client de campagnes : ni jeton, ni code de
réessai, ni connexion. Il ne sait faire que deux choses :

* ``chercher(...)`` — UNE page de ``GET /<version>/ads_archive`` ;
* ``verifier_jeton()`` — ``GET /<version>/debug_token`` (à la demande, VEIL12).

Règles codées (et testées) :

* Liste blanche hôte + chemins : ``graph.facebook.com/<GRAPH_VERSION>/ads_archive``
  et ``/debug_token`` SEULEMENT (version lue dans ``api_version.py``). Toute
  autre URL lève :class:`UrlInterdite` — l'URL de snapshot d'une pub et le site
  de la bibliothèque ne sont JAMAIS lus par le serveur.
* Le jeton part en en-tête ``Authorization`` — jamais dans une URL. Les logs ne
  citent que le chemin ; un filtre retire tout ``access_token=`` /
  ``input_token=`` des messages du journal ``httpx``.
* Quota : codes 4/17/32/613 et HTTP 429 → :class:`QuotaAtteint` SANS nouvel
  essai (l'appelant met la découverte en pause) ; 190 → :class:`AccesInvalide` ;
  5xx / réseau → au plus 2 nouveaux essais. Jamais de rotation de jeton.
* ``X-App-Usage`` est lu à chaque réponse.
* Fin de pagination = ``paging.next`` absent. Une page VIDE avec un ``next``
  est signalée (``page_vide_avec_suivant``) et la pagination continue.
* ``access_token=`` est retiré de tout ``ad_snapshot_url`` reçu.
* Transport de REJEU : si ``META_AD_LIBRARY_FIXTURES_DIR`` est posé ET que
  ``META_AD_LIBRARY_ENABLED`` est faux, le client lit
  ``<mot_cle>_<pays>_<page>.json`` dans ce dossier et n'ouvre AUCUNE connexion
  (démonstrations sans jeton, e2e).
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from django.conf import settings

from . import competitor_intel as ci
from .api_version import GRAPH_VERSION

logger = logging.getLogger(__name__)

HOTE_AUTORISE = 'graph.facebook.com'
CHEMIN_ADS_ARCHIVE = f'/{GRAPH_VERSION}/ads_archive'
CHEMIN_DEBUG_TOKEN = f'/{GRAPH_VERSION}/debug_token'
CHEMINS_AUTORISES = (CHEMIN_ADS_ARCHIVE, CHEMIN_DEBUG_TOKEN)

CODES_QUOTA = frozenset({4, 17, 32, 613})
CODE_ACCES_INVALIDE = 190
HTTP_TROP_DE_REQUETES = 429
MAX_NOUVEAUX_ESSAIS = 2
LONGUEUR_MAX_MOT_CLE = 100

SEARCH_TYPES = ('KEYWORD_UNORDERED', 'KEYWORD_EXACT_PHRASE')
# AACQ37 — ``ad_type=ALL`` sur chaque recherche ``ads_archive`` : parité avec
# la sonde VEIL40 (``tools/adlib_probe/probe.py:244``, référence de parité) —
# sans lui Meta peut ne renvoyer que les pubs politiques/sociales.
AD_TYPE = 'ALL'
AD_ACTIVE_STATUS = ('ACTIVE', 'INACTIVE', 'ALL')

# Champs demandés (seuls ceux que l'API sert pour une pub commerciale UE/UK ;
# jamais impressions ni dépenses).
CHAMPS_DEFAUT = (
    'id', 'page_id', 'page_name', 'ad_creative_bodies',
    'ad_creative_link_captions', 'ad_creative_link_titles',
    'ad_creative_link_descriptions', 'ad_delivery_start_time',
    'ad_delivery_stop_time', 'languages', 'publisher_platforms',
    'ad_snapshot_url', 'beneficiary_payers', 'eu_total_reach',
    'target_locations',
)

_RE_SECRET_URL = re.compile(
    r'((?:access_token|input_token)=)[^&\s"\']+', re.IGNORECASE)


class _FiltreSecretsHttpx(logging.Filter):
    """Retire toute valeur ``access_token=`` / ``input_token=`` d'un message de
    journal (le journal ``httpx`` cite l'URL complète de chaque requête)."""

    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 — message illisible : on le laisse
            return True
        nettoye = _RE_SECRET_URL.sub(r'\1••••', message)
        if nettoye != message:
            record.msg = nettoye
            record.args = ()
        return True


def _installer_filtre_httpx():
    journal = logging.getLogger('httpx')
    if not any(isinstance(f, _FiltreSecretsHttpx) for f in journal.filters):
        journal.addFilter(_FiltreSecretsHttpx())


_installer_filtre_httpx()


# ── Exceptions (messages FR, jamais de secret) ──────────────────────────────
class AdLibraryErreur(Exception):
    def __init__(self, message_fr, *, code=None):
        self.message_fr = message_fr
        self.code = code
        super().__init__(message_fr)


class ParametreInvalide(AdLibraryErreur):
    pass


class UrlInterdite(AdLibraryErreur):
    pass


class QuotaAtteint(AdLibraryErreur):
    def __init__(self, code, usage=None):
        self.usage = usage or {}
        super().__init__(
            "Limite de débit atteinte : la découverte attend avant de "
            "reprendre.", code=code)


class AccesInvalide(AdLibraryErreur):
    def __init__(self, code=CODE_ACCES_INVALIDE):
        super().__init__(
            "Accès invalide : le jeton Ad Library est refusé par Meta.",
            code=code)


class RequeteRefusee(AdLibraryErreur):
    def __init__(self, code, statut_http, detail=''):
        self.statut_http = statut_http
        super().__init__(
            f"Requête refusée par Meta (code {code}, HTTP {statut_http})"
            + (f" : {detail}" if detail else '.'), code=code)


class ErreurReseau(AdLibraryErreur):
    pass


# ── Outils purs ──────────────────────────────────────────────────────────────
def retirer_jeton_url(url):
    """Retire tout paramètre ``access_token`` (toute casse) d'une URL."""
    if not url or not isinstance(url, str):
        return url
    try:
        morceaux = urlsplit(url)
    except ValueError:
        return _RE_SECRET_URL.sub('', url)
    params = [(k, v) for k, v in parse_qsl(morceaux.query,
                                           keep_blank_values=True)
              if k.lower() != 'access_token']
    propre = urlunsplit((morceaux.scheme, morceaux.netloc, morceaux.path,
                         urlencode(params), morceaux.fragment))
    return _RE_SECRET_URL.sub('', propre) if 'token=' in propre.lower() \
        else propre


def nettoyer_pub(pub):
    """Copie d'une pub reçue, ``ad_snapshot_url`` sans jeton."""
    pub = dict(pub or {})
    if 'ad_snapshot_url' in pub:
        pub['ad_snapshot_url'] = retirer_jeton_url(pub['ad_snapshot_url'])
    return pub


def lire_usage(entetes):
    """Lit ``X-App-Usage`` → ``{call_count, total_cputime, total_time}``
    (valeurs entières) ou ``{}`` si absent/illisible."""
    brut = None
    if entetes is not None:
        brut = entetes.get('x-app-usage') or entetes.get('X-App-Usage')
    if not brut:
        return {}
    try:
        donnees = json.loads(brut) if isinstance(brut, str) else dict(brut)
    except (TypeError, ValueError):
        return {}
    usage = {}
    for cle in ('call_count', 'total_cputime', 'total_time'):
        try:
            usage[cle] = int(donnees.get(cle))
        except (TypeError, ValueError):
            continue
    return usage


def pourcentage_usage(usage):
    """Le plus haut des trois pourcentages de ``X-App-Usage`` (0 si vide)."""
    valeurs = [v for v in (usage or {}).values() if isinstance(v, int)]
    return max(valeurs) if valeurs else 0


def nom_fixture(mot_cle, pays, page):
    """Nom de fichier du transport de rejeu : ``<mot_cle>_<pays>_<page>.json``
    (mot-clé en minuscules sans accents, séparateurs remplacés par ``-``)."""
    import unicodedata
    ascii_ = unicodedata.normalize('NFKD', str(mot_cle)).encode(
        'ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-z0-9]+', '-', ascii_.strip().lower()).strip('-')
    return f'{slug}_{ci.normaliser_pays(pays)}_{int(page)}.json'


def valider_mot_cle(mot_cle):
    texte = str(mot_cle or '').strip()
    if not texte:
        raise ParametreInvalide('Le mot-clé est obligatoire.')
    if len(texte) > LONGUEUR_MAX_MOT_CLE:
        raise ParametreInvalide(
            f'Le mot-clé dépasse {LONGUEUR_MAX_MOT_CLE} caractères '
            f'({len(texte)}) : limite de l\'API ads_archive.')
    return texte


def valider_pays(pays):
    """Code pays de la table VEIL10 utilisable par la découverte (couvert ou à
    confirmer). ``UK``/``EL`` et les pays non couverts sont refusés en FR."""
    code = ci.normaliser_pays(pays)
    if code in ci.CODES_REFUSES:
        raise ParametreInvalide(ci.CODES_REFUSES[code])
    statut = ci.statut_couverture(code)
    if statut == ci.NON_COUVERT:
        raise ParametreInvalide(
            f'Pays « {code or "?"} » non couvert par l\'API Ad Library pour '
            'les pubs commerciales (seules les pubs politiques y sont '
            'servies) : découverte refusée.')
    return code


def _verifier_url(url):
    """Lève :class:`UrlInterdite` si ``url`` sort de la liste blanche."""
    try:
        morceaux = urlsplit(str(url))
    except ValueError as exc:
        raise UrlInterdite('URL illisible : refusée.') from exc
    if (morceaux.scheme != 'https' or morceaux.hostname != HOTE_AUTORISE
            or morceaux.path not in CHEMINS_AUTORISES):
        raise UrlInterdite(
            'URL hors liste blanche (seuls ads_archive et debug_token de '
            'graph.facebook.com sont autorisés) : refusée.')
    return url


def _horodatage_vers_iso(valeur):
    import datetime
    try:
        secondes = int(valeur)
    except (TypeError, ValueError):
        return None
    if secondes <= 0:
        return None  # 0 = n'expire jamais
    return datetime.datetime.fromtimestamp(
        secondes, tz=datetime.timezone.utc).isoformat()


# ── Le client ────────────────────────────────────────────────────────────────
class AdLibraryClient:
    """Client lecture seule de ``ads_archive``. ``http_client`` (``httpx``)
    est injectable (tests : ``httpx.MockTransport``)."""

    attente_entre_essais = (1.0, 2.0)

    def __init__(self, jeton, *, app_id='', app_secret='', http_client=None,
                 timeout=30.0, dormir=None):
        self._jeton = jeton or ''
        self._app_id = app_id or ''
        self._app_secret = app_secret or ''
        self._http = http_client
        self._timeout = timeout
        self._dormir = dormir if dormir is not None else time.sleep
        self.dernier_usage = {}

    def __repr__(self):
        return 'AdLibraryClient(jeton=••••••••)'

    # ── rejeu ────────────────────────────────────────────────────────────
    @staticmethod
    def dossier_rejeu():
        """Dossier de rejeu actif, ou ``None``. Actif SEULEMENT si posé ET si
        l'interrupteur réseau ``META_AD_LIBRARY_ENABLED`` est faux."""
        dossier = getattr(settings, 'META_AD_LIBRARY_FIXTURES_DIR', '') or ''
        if not dossier or getattr(settings, 'META_AD_LIBRARY_ENABLED', False):
            return None
        return Path(dossier)

    def _rejouer(self, mot_cle, pays, after):
        dossier = self.dossier_rejeu()
        try:
            page = int(after) if after else 1
        except (TypeError, ValueError):
            page = 1
        chemin = dossier / nom_fixture(mot_cle, pays, page)
        if not chemin.is_file():
            corps, statut, usage = {'data': [], 'paging': {}}, 200, {}
        else:
            corps = json.loads(chemin.read_text(encoding='utf-8'))
            statut = int(corps.pop('_status', 200) or 200)
            usage = lire_usage(
                {'x-app-usage': json.dumps(corps.pop('_x_app_usage', {}))})
        self.dernier_usage = usage
        self._lever_si_erreur(statut, corps, usage)
        pubs = [nettoyer_pub(p) for p in (corps.get('data') or [])]
        a_suivant = bool((corps.get('paging') or {}).get('next'))
        return {
            'pubs': pubs,
            'after_suivant': str(page + 1) if a_suivant else None,
            'a_suivant': a_suivant,
            'usage': usage,
            'page_vide_avec_suivant': a_suivant and not pubs,
        }

    # ── réseau ───────────────────────────────────────────────────────────
    def _envoyer(self, url, params, entetes):
        _verifier_url(url)
        chemin = urlsplit(url).path
        derniere = None
        for essai in range(MAX_NOUVEAUX_ESSAIS + 1):
            if essai:
                pause = self.attente_entre_essais[
                    min(essai - 1, len(self.attente_entre_essais) - 1)]
                self._dormir(pause)
            try:
                if self._http is not None:
                    reponse = self._http.get(url, params=params,
                                             headers=entetes)
                else:
                    with httpx.Client(timeout=self._timeout) as client:
                        reponse = client.get(url, params=params,
                                             headers=entetes)
            except httpx.HTTPError as exc:
                derniere = ErreurReseau(
                    f'Erreur réseau vers Meta ({type(exc).__name__}).')
                logger.warning('ad_library: GET %s erreur réseau (essai %d)',
                               chemin, essai + 1)
                continue
            logger.debug('ad_library: GET %s -> %s (essai %d)', chemin,
                         reponse.status_code, essai + 1)
            if reponse.status_code >= 500:
                derniere = ErreurReseau(
                    f'Meta indisponible (HTTP {reponse.status_code}).')
                continue
            return reponse
        raise derniere

    @staticmethod
    def _lever_si_erreur(statut, corps, usage):
        erreur = corps.get('error') if isinstance(corps, dict) else None
        if statut < 400 and not erreur:
            return
        erreur = erreur or {}
        try:
            code = int(erreur.get('code')) if erreur.get('code') is not None \
                else None
        except (TypeError, ValueError):
            code = None
        if code in CODES_QUOTA or statut == HTTP_TROP_DE_REQUETES:
            raise QuotaAtteint(code or HTTP_TROP_DE_REQUETES, usage)
        if code == CODE_ACCES_INVALIDE:
            raise AccesInvalide(code)
        detail = str(erreur.get('message') or '')[:200]
        raise RequeteRefusee(code, statut, _RE_SECRET_URL.sub(r'\1••••',
                                                              detail))

    def _decoder(self, reponse):
        usage = lire_usage(reponse.headers)
        self.dernier_usage = usage
        try:
            corps = reponse.json()
        except ValueError:
            corps = {}
        self._lever_si_erreur(reponse.status_code, corps, usage)
        return corps, usage

    # ── API publique ─────────────────────────────────────────────────────
    def chercher(self, mot_cle, pays, search_type='KEYWORD_UNORDERED',
                 ad_active_status='ACTIVE', champs=None, limit=None,
                 after=None):
        """UNE page de résultats. Renvoie ``{pubs, after_suivant, a_suivant,
        usage, page_vide_avec_suivant}``. ``after_suivant`` ne vit qu'en
        mémoire de l'appelant (Meta interdit de stocker les curseurs)."""
        mot_cle = valider_mot_cle(mot_cle)
        pays = valider_pays(pays)
        if search_type not in SEARCH_TYPES:
            raise ParametreInvalide(
                f'Mode de recherche inconnu : {search_type}.')
        if ad_active_status not in AD_ACTIVE_STATUS:
            raise ParametreInvalide(
                f'Statut de diffusion inconnu : {ad_active_status}.')
        if self.dossier_rejeu() is not None:
            return self._rejouer(mot_cle, pays, after)
        if not self._jeton:
            raise AccesInvalide()
        params = {
            'search_terms': mot_cle,
            'ad_reached_countries': json.dumps([pays]),
            'search_type': search_type,
            'ad_active_status': ad_active_status,
            'ad_type': AD_TYPE,
            'fields': ','.join(champs or CHAMPS_DEFAUT),
        }
        if limit:
            params['limit'] = int(limit)
        if after:
            params['after'] = after
        reponse = self._envoyer(
            f'https://{HOTE_AUTORISE}{CHEMIN_ADS_ARCHIVE}', params,
            {'Authorization': f'Bearer {self._jeton}'})
        corps, usage = self._decoder(reponse)
        pubs = [nettoyer_pub(p) for p in (corps.get('data') or [])]
        paging = corps.get('paging') or {}
        a_suivant = bool(paging.get('next'))
        after_suivant = ((paging.get('cursors') or {}).get('after')
                         if a_suivant else None)
        return {
            'pubs': pubs,
            'after_suivant': after_suivant,
            'a_suivant': a_suivant,
            'usage': usage,
            'page_vide_avec_suivant': a_suivant and not pubs,
        }

    def verifier_jeton(self):
        """``debug_token`` : ``{valide, expire_le}`` (ISO ou ``None``). Le jeton
        d'application ``app_id|app_secret`` part en en-tête et n'est cité nulle
        part ailleurs."""
        if self.dossier_rejeu() is not None:
            return {'valide': True, 'expire_le': None}
        if not self._jeton:
            raise AccesInvalide()
        if not (self._app_id and self._app_secret):
            raise ParametreInvalide(
                "Identifiant ou secret d'application Ad Library absent : "
                'vérification du jeton impossible.')
        reponse = self._envoyer(
            f'https://{HOTE_AUTORISE}{CHEMIN_DEBUG_TOKEN}',
            {'input_token': self._jeton},
            {'Authorization': f'Bearer {self._app_id}|{self._app_secret}'})
        corps, _usage = self._decoder(reponse)
        donnees = corps.get('data') or {}
        return {
            'valide': bool(donnees.get('is_valid')),
            'expire_le': _horodatage_vers_iso(donnees.get('expires_at')),
        }
