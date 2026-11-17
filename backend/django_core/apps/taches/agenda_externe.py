"""Agendas externes — lecture RÉSEAU sous garde (reference/regles.md « Les agendas externes » ;
donnees.md invariant 33 ; arbitrages A18-M4).

`lire_agenda_externe(agenda, du, au)` rend les rendez-vous (`moteur.ics.RendezVousPur`) d'une adresse
ICS, lue CÔTÉ SERVEUR seulement, dans cet ordre (chaque échec pose son `EtatAgendaExterne` et rien
d'autre — jamais d'exception à l'écran) :

1. schéma `https://` seulement (`pas_https`) ;
2. hôte résolu À CHAQUE lecture, TOUTES les adresses obtenues publiques (validateur de
   `apps/publicapi/validators.py`, appliqué à chaque adresse) — `adresse_privee`, `injoignable` ;
   la connexion est faite VERS l'adresse vérifiée (nom gardé pour le TLS) : pas de seconde
   résolution qu'un DNS changeant pourrait détourner ;
3. 3 redirections au plus, chacune revérifiée (étapes 1-2) ;
4. corps ≤ 2 Mo, délai total ≤ 10 s (`trop_grande`, `delai`) ;
5. `BEGIN:VCALENDAR` présent (`illisible`) ;
6. succès : texte mis en cache 15 minutes par adresse, `dernier_chargement_le`, `ok`.

L'URL vaut une clé : jamais rendue, jamais journalisée (seul `hote` et l'id sont écrits au journal).
Les événements ne vont jamais en base. Un échec efface le cache de l'adresse.
"""
import hashlib
import http.client
import ipaddress
import logging
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit

from django.core.cache import cache
from django.utils import timezone

from apps.publicapi.validators import UnsafeWebhookURL, validate_webhook_target_url
from apps.taches.choix import EtatAgendaExterne
from apps.taches.moteur.ics import IcsIllisible, IcsTropGrand, lire_evenements

logger = logging.getLogger(__name__)

SCHEMA = 'https'
PREFIXE_WEBCAL = 'webcal://'
PORT_HTTPS = 443
CORPS_MAX = 2 * 1024 * 1024  # 2 Mo
DELAI_MAX = 10.0  # secondes, lecture entière
REDIRECTIONS_MAX = 3
CACHE_SECONDES = 15 * 60
MORCEAU = 64 * 1024
AGENDAS_MAX = 3
STATUTS_REDIRECTION = frozenset({301, 302, 303, 307, 308})
ENTETES = {'User-Agent': 'TaqinorOS-Agenda/1', 'Accept': 'text/calendar, */*;q=0.5'}


class Echec(Exception):
    """Une lecture refusée ou manquée : `etat` est l'`EtatAgendaExterne` à poser."""

    def __init__(self, etat):
        super().__init__(etat)
        self.etat = etat


# --- Adresse ---------------------------------------------------------------------------------------

def normaliser_url(url):
    """`webcal://…` → `https://…` (même hôte, même chemin : l'iPhone donne ses liens ainsi)."""
    url = (url or '').strip()
    if url.lower().startswith(PREFIXE_WEBCAL):
        return f'{SCHEMA}://{url[len(PREFIXE_WEBCAL):]}'
    return url


def verifier_adresse(url):
    """Garde d'AJOUT : https et hôte public (validateur de `publicapi`) ; lève `UnsafeWebhookURL`."""
    return validate_webhook_target_url(url)


def _url_de_l_ip(ip):
    return f'{SCHEMA}://[{ip}]/' if ':' in ip else f'{SCHEMA}://{ip}/'


def _adresses_publiques(hote, port):
    """Résout `hote` MAINTENANT ; chaque adresse obtenue doit être publique (`adresse_privee`)."""
    try:
        ipaddress.ip_address(hote)
        adresses = [hote]
    except ValueError:
        try:
            infos = socket.getaddrinfo(hote, port, proto=socket.IPPROTO_TCP)
        except (socket.gaierror, UnicodeError, OSError):
            raise Echec(EtatAgendaExterne.INJOIGNABLE)
        adresses = list(dict.fromkeys(info[4][0] for info in infos))
    if not adresses:
        raise Echec(EtatAgendaExterne.INJOIGNABLE)
    for ip in adresses:
        try:
            validate_webhook_target_url(_url_de_l_ip(ip))
        except UnsafeWebhookURL:
            raise Echec(EtatAgendaExterne.ADRESSE_PRIVEE)
    return adresses


def _cible(url):
    """(hôte, port, chemin) d'une adresse https publique, sinon `Echec`."""
    try:
        morceaux = urlsplit(url)
        port = morceaux.port or PORT_HTTPS
    except ValueError:
        raise Echec(EtatAgendaExterne.INJOIGNABLE)
    if morceaux.scheme.lower() != SCHEMA:
        raise Echec(EtatAgendaExterne.PAS_HTTPS)
    if not morceaux.hostname:
        raise Echec(EtatAgendaExterne.INJOIGNABLE)
    chemin = morceaux.path or '/'
    if morceaux.query:
        chemin = f'{chemin}?{morceaux.query}'
    return morceaux.hostname, port, chemin


# --- Connexion épinglée sur l'adresse vérifiée -----------------------------------------------------

class ConnexionEpinglee(http.client.HTTPSConnection):
    """HTTPS vers `ip` (déjà vérifiée), le nom `hote` servant au TLS (SNI et certificat)."""

    def __init__(self, hote, ip, port, timeout):
        super().__init__(hote, port, timeout=timeout, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        brut = socket.create_connection((self.ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(brut, server_hostname=self.host)


def _ouvrir(hote, ip, port, timeout):
    return ConnexionEpinglee(hote, ip, port, timeout)


def _reste(fin):
    reste = fin - time.monotonic()
    if reste <= 0:
        raise Echec(EtatAgendaExterne.DELAI)
    return reste


def _lire_corps(reponse, connexion, fin):
    """Le corps, borné à 2 Mo et au délai total."""
    longueur = reponse.getheader('Content-Length')
    if longueur and longueur.isdigit() and int(longueur) > CORPS_MAX:
        raise Echec(EtatAgendaExterne.TROP_GRANDE)
    morceaux, total = [], 0
    while True:
        if connexion.sock is not None:
            connexion.sock.settimeout(_reste(fin))
        morceau = reponse.read(MORCEAU)
        if not morceau:
            return b''.join(morceaux)
        total += len(morceau)
        if total > CORPS_MAX:
            raise Echec(EtatAgendaExterne.TROP_GRANDE)
        morceaux.append(morceau)


def _une_requete(url, fin):
    """(statut, adresse de redirection, corps) d'UN saut, garde complète avant la connexion."""
    hote, port, chemin = _cible(url)
    ip = _adresses_publiques(hote, port)[0]
    connexion = _ouvrir(hote, ip, port, _reste(fin))
    try:
        connexion.request('GET', chemin, headers=ENTETES)
        reponse = connexion.getresponse()
        if reponse.status in STATUTS_REDIRECTION:
            return reponse.status, reponse.getheader('Location'), b''
        return reponse.status, None, _lire_corps(reponse, connexion, fin)
    finally:
        connexion.close()


def telecharger(url, *, delai=DELAI_MAX):
    """Le texte ICS d'une adresse, sous la garde de l'invariant 33 ; lève `Echec(etat)`."""
    fin = time.monotonic() + delai
    try:
        for _saut in range(REDIRECTIONS_MAX + 1):
            statut, suivante, corps = _une_requete(url, fin)
            if suivante is None:
                break
            url = urljoin(url, suivante)
        else:
            raise Echec(EtatAgendaExterne.INJOIGNABLE)
    except (socket.timeout, TimeoutError):
        raise Echec(EtatAgendaExterne.DELAI)
    except (ssl.SSLError, ConnectionError, http.client.HTTPException, OSError):
        raise Echec(EtatAgendaExterne.INJOIGNABLE)
    if statut != 200 or suivante is not None:
        raise Echec(EtatAgendaExterne.INJOIGNABLE)
    return corps.decode('utf-8', errors='replace')


def evenements_du_texte(texte, agenda_id, du, au):
    """Les rendez-vous de [du, au] (`moteur.ics.lire_evenements`) ; lève `Echec`."""
    try:
        return lire_evenements(texte, du, au, agenda_id=agenda_id)
    except IcsIllisible:
        raise Echec(EtatAgendaExterne.ILLISIBLE)
    except IcsTropGrand:
        raise Echec(EtatAgendaExterne.TROP_GRANDE)


# --- Lecture d'un agenda (cache, état) ----------------------------------------------------------

def cle_cache(agenda):
    """Clé du cache d'une adresse : l'id et une empreinte de l'URL (jamais l'URL elle-même)."""
    empreinte = hashlib.sha256((agenda.url or '').encode('utf-8')).hexdigest()[:24]
    return f'taches:agext:{agenda.company_id}:{agenda.pk}:{empreinte}'


def _poser_etat(agenda, etat, maintenant=None):
    agenda.dernier_etat = etat
    champs = ['dernier_etat', 'updated_at']
    if etat == EtatAgendaExterne.OK:
        agenda.dernier_chargement_le = maintenant or timezone.now()
        champs.append('dernier_chargement_le')
    agenda.save(update_fields=champs)


def lire_agenda_externe(agenda, du, au, *, rafraichir=False):
    """Rendez-vous de l'agenda pour [du, au] (tuple, vide sur un échec) ; `dernier_etat` dit
    l'issue. Le texte est relu du cache (15 min) sauf `rafraichir` ; rien n'est écrit en base sur
    un cache trouvé."""
    cle = cle_cache(agenda)
    texte = None if rafraichir else cache.get(cle)
    lu_du_reseau = texte is None
    try:
        if lu_du_reseau:
            texte = telecharger(agenda.url)
        evenements = evenements_du_texte(texte, agenda.pk, du, au)
    except Echec as echec:
        cache.delete(cle)
        logger.info('taches : agenda externe %s (%s) en échec : %s', agenda.pk, agenda.hote, echec.etat)
        _poser_etat(agenda, echec.etat)
        return ()
    if lu_du_reseau:
        cache.set(cle, texte, CACHE_SECONDES)
        _poser_etat(agenda, EtatAgendaExterne.OK)
    return evenements


def oublier(agenda):
    """Efface le texte en cache d'une adresse (suppression, désactivation)."""
    cache.delete(cle_cache(agenda))


# --- Les agendas d'un compte (index en cache : 0 requête de plus sur la journée) -----------------

def cle_index(user):
    return f'taches:agext:index:{user.company_id}:{user.pk}'


def agendas_actifs(user):
    """Les agendas ACTIFS de `user` (objets non enregistrés reconstruits depuis le cache, sinon une
    requête) — l'index est effacé à chaque écriture d'un agenda (`oublier_index`)."""
    from apps.taches.models.agenda import AgendaExterne
    if getattr(user, 'company_id', None) is None or getattr(user, 'pk', None) is None:
        return []
    index = cache.get(cle_index(user))
    if index is None:
        index = list(AgendaExterne.objects.filter(company_id=user.company_id, proprietaire=user, actif=True)
                     .order_by('rang', 'pk').values('pk', 'url', 'hote', 'libelle'))
        cache.set(cle_index(user), index, CACHE_SECONDES)
    return [AgendaExterne(pk=ligne['pk'], company_id=user.company_id, proprietaire_id=user.pk, url=ligne['url'],
                          hote=ligne['hote'], libelle=ligne['libelle'], actif=True) for ligne in index]


def oublier_index(user):
    cache.delete(cle_index(user))
