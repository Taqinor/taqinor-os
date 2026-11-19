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
4. corps ≤ 2 Mo, délai total ≤ 10 s (`trop_grande`, `delai`) — une ÉCHÉANCE ABSOLUE, revérifiée
   avant chaque envoi et chaque `recv` (connexion, TLS, en-têtes, corps et redirections compris :
   `SocketBorne`), jamais un délai par appel qu'un serveur au goutte-à-goutte prolongerait ;
5. `BEGIN:VCALENDAR` présent (`illisible`) ;
6. succès : texte mis en cache 15 minutes par adresse, `dernier_chargement_le`, `ok`.

L'URL vaut une clé : jamais rendue, jamais journalisée (seul `hote` et l'id sont écrits au journal).
Les événements ne vont jamais en base. Un échec est RETENU dans le cache de l'adresse 15 minutes,
comme un succès (regles.md §11) : l'adresse n'est pas relue pendant ce temps, ses rendez-vous sont
absents et son état reste dit ; `rafraichir` (Réessayer, nouvel enregistrement) relit aussitôt.
"""
import hashlib
import http.client
import io
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
#: Budget réseau d'UNE requête d'écran pour tous les agendas du compte (3 au plus, lus en série).
DELAI_ECRAN = DELAI_MAX
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
    """`webcal://…` → `https://…` (même hôte, même chemin : l'iPhone donne ses liens ainsi) ; `HTTPS://` → `https://`
    (un même agenda collé en majuscules n'est pas un second agenda)."""
    url = (url or '').strip()
    if url.lower().startswith(PREFIXE_WEBCAL):
        return f'{SCHEMA}://{url[len(PREFIXE_WEBCAL):]}'
    if url.lower().startswith(f'{SCHEMA}://'):
        return f'{SCHEMA}://{url[len(SCHEMA) + 3:]}'
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

#: L'horloge des échéances (remplacée dans les tests, avec le transport `_connecter`).
horloge = time.monotonic


def _reste(fin):
    reste = fin - horloge()
    if reste <= 0:
        raise Echec(EtatAgendaExterne.DELAI)
    return reste


def _connecter(ip, port, hote, contexte, fin):
    """Le socket TLS vers `ip`, connexion puis poignée TLS bornées chacune par ce qui reste."""
    brut = socket.create_connection((ip, port), _reste(fin))
    try:
        brut.settimeout(_reste(fin))
        return contexte.wrap_socket(brut, server_hostname=hote)
    except BaseException:
        brut.close()
        raise


class SocketBorne:
    """Le socket d'une lecture : AVANT chaque envoi et chaque `recv`, son délai devient ce qui reste
    jusqu'à l'échéance ABSOLUE `fin` ; échéance passée → `TimeoutError` (état `delai`). Le délai
    d'un socket ne vaut que pour UN appel : sans cela, un octet toutes les 9 s tiendrait sans fin.
    `makefile` (en-têtes et corps de `http.client`) lit par ce même `recv_into`."""

    def __init__(self, sock, fin):
        self._sock, self._fin, self._fichiers, self._ferme = sock, fin, 0, False

    def _borner(self):
        reste = self._fin - horloge()
        if reste <= 0:
            raise TimeoutError('délai total de lecture épuisé')
        self._sock.settimeout(reste)

    def sendall(self, donnees, *args):
        self._borner()
        return self._sock.sendall(donnees, *args)

    def recv_into(self, tampon):
        self._borner()
        return self._sock.recv_into(tampon)

    def makefile(self, mode='rb', *args, **kwargs):
        self._fichiers += 1
        return io.BufferedReader(_LectureBornee(self))

    def _fichier_ferme(self):
        self._fichiers -= 1
        if self._ferme and self._fichiers <= 0:
            self._sock.close()

    def close(self):
        # Comme un vrai socket : fermé pour de bon quand le dernier fichier ouvert dessus l'est.
        self._ferme = True
        if self._fichiers <= 0:
            self._sock.close()


class _LectureBornee(io.RawIOBase):
    def __init__(self, sock):
        super().__init__()
        self._borne = sock

    def readable(self):
        return True

    def readinto(self, tampon):
        return self._borne.recv_into(tampon)

    def close(self):
        if not self.closed:
            super().close()
            self._borne._fichier_ferme()


class ConnexionEpinglee(http.client.HTTPSConnection):
    """HTTPS vers `ip` (déjà vérifiée), le nom `hote` servant au TLS (SNI et certificat) ; tout
    échange est borné par l'échéance absolue `fin` (`SocketBorne`)."""

    def __init__(self, hote, ip, port, timeout, fin=None):
        super().__init__(hote, port, timeout=timeout, context=ssl.create_default_context())
        self.ip = ip
        self.fin = horloge() + timeout if fin is None else fin

    def connect(self):
        self.sock = SocketBorne(_connecter(self.ip, self.port, self.host, self._context, self.fin), self.fin)


def _ouvrir(hote, ip, port, fin):
    return ConnexionEpinglee(hote, ip, port, _reste(fin), fin=fin)


def _lire_corps(reponse, connexion, fin):
    """Le corps, borné à 2 Mo et au délai total (chaque `recv` est borné par `SocketBorne`)."""
    longueur = reponse.getheader('Content-Length')
    if longueur and longueur.isdigit() and int(longueur) > CORPS_MAX:
        raise Echec(EtatAgendaExterne.TROP_GRANDE)
    morceaux, total = [], 0
    while True:
        _reste(fin)
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
    _reste(fin)
    connexion = _ouvrir(hote, ip, port, fin)
    try:
        connexion.request('GET', chemin, headers=ENTETES)
        reponse = connexion.getresponse()
        if reponse.status in STATUTS_REDIRECTION:
            return reponse.status, reponse.getheader('Location'), b''
        return reponse.status, None, _lire_corps(reponse, connexion, fin)
    finally:
        connexion.close()


def telecharger(url, *, delai=DELAI_MAX, fin=None):
    """Le texte ICS d'une adresse, sous la garde de l'invariant 33 ; lève `Echec(etat)`. `fin` :
    échéance absolue imposée par l'appelant (budget d'un écran), jamais plus loin que `delai`."""
    fin = min(horloge() + delai, fin if fin is not None else float('inf'))
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


#: Clé de la valeur mise en cache à la place du texte quand une lecture a échoué.
CLE_ECHEC = 'echec'


def lire_agenda_externe(agenda, du, au, *, rafraichir=False, fin=None, cache_seul=False):
    """Rendez-vous de l'agenda pour [du, au] (tuple, vide sur un échec) ; `dernier_etat` dit
    l'issue. Le texte — ou l'échec — est relu du cache (15 min) sauf `rafraichir` ; rien n'est écrit
    en base ni lu du réseau sur un cache trouvé. `fin` : échéance absolue de l'écran appelant ;
    passée, l'agenda non encore en cache n'est pas lu (rien de retenu : la prochaine requête le lira).
    `cache_seul` (le balayage de chaque minute) : JAMAIS de réseau ; cache froid → aucun rendez-vous,
    rien de retenu ni d'écrit."""
    cle = cle_cache(agenda)
    texte = None if rafraichir else cache.get(cle)
    if isinstance(texte, dict):  # échec retenu : pas de réseau, aucun ancien rendez-vous
        return ()
    lu_du_reseau = texte is None
    if lu_du_reseau and cache_seul:
        return ()
    # L'écran coupe plus d'une seconde sur les 10 de l'agenda : un `delai` ne dit alors rien de lui.
    ecran_plus_court = fin is not None and fin < horloge() + DELAI_MAX - 1.0
    if lu_du_reseau and fin is not None and fin - horloge() <= 0:
        return ()
    try:
        if lu_du_reseau:
            texte = telecharger(agenda.url, fin=fin)
        evenements = evenements_du_texte(texte, agenda.pk, du, au)
    except Echec as echec:
        if ecran_plus_court and echec.etat == EtatAgendaExterne.DELAI:
            return ()
        cache.set(cle, {CLE_ECHEC: echec.etat}, CACHE_SECONDES)
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
