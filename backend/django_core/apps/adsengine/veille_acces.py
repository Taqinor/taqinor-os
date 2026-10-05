"""VEIL12 — Accès Meta Ad Library du pilote de veille, SÉPARÉ des campagnes.

Les réglages sont lus UNIQUEMENT depuis l'environnement (``settings``) :
``META_AD_LIBRARY_ENABLED``, ``META_AD_LIBRARY_ACCESS_TOKEN``,
``META_AD_LIBRARY_APP_ID``, ``META_AD_LIBRARY_APP_SECRET`` et
``VEILLE_SOCIETES_AUTORISEES`` (D-VEIL-12 : défaut vide = personne). Ce module
ne lit JAMAIS la connexion de campagne de la société ni les jetons de campagne
ou de formulaires de prospects : l'accès de test de la veille ne peut servir à
rien d'autre, et rien d'autre ne peut le servir.

``etat(company)`` renvoie l'un de ``non_configure`` | ``desactive`` |
``non_autorise`` | ``pret`` | ``expire_bientot`` | ``invalide`` (contrat
``veille_couverture.json``, clé ``acces``). La date d'expiration vient de
``debug_token``, appelé À LA DEMANDE seulement (``verifier``) et mis en cache —
jamais en boucle, jamais par une tâche planifiée.

Le jeton et le secret d'application ne sortent JAMAIS de ce module ni du client
``ad_library_client`` : ni dans un log, ni dans une réponse d'API, ni dans un
message d'erreur (``masquer`` / ``masquer_secrets``).
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

NON_CONFIGURE = 'non_configure'
DESACTIVE = 'desactive'
NON_AUTORISE = 'non_autorise'
PRET = 'pret'
EXPIRE_BIENTOT = 'expire_bientot'
INVALIDE = 'invalide'
ETATS = (NON_CONFIGURE, DESACTIVE, NON_AUTORISE, PRET, EXPIRE_BIENTOT,
         INVALIDE)
# États qui permettent un appel réseau.
ETATS_UTILISABLES = (PRET, EXPIRE_BIENTOT)

# Alerte « expire bientôt » à J-10 de ``expires_at`` (debug_token).
ALERTE_EXPIRATION_JOURS = 10

# Dernière vérification du jeton (globale : un seul jeton pour l'instance).
CLE_CACHE_VERIFICATION = 'adsengine:veille:verification_jeton'
DUREE_CACHE_VERIFICATION = 6 * 3600

MASQUE = '••••••••'

MESSAGES_FR = {
    NON_CONFIGURE: "Accès Ad Library non configuré : aucun jeton n'est posé.",
    DESACTIVE: "Accès Ad Library désactivé par l'interrupteur du serveur.",
    NON_AUTORISE: ("Cette société n'est pas autorisée à utiliser l'accès Ad "
                   "Library de la veille."),
    PRET: "Accès Ad Library prêt.",
    EXPIRE_BIENTOT: "Accès Ad Library prêt, mais le jeton expire bientôt.",
    INVALIDE: "Accès Ad Library invalide : le jeton est refusé par Meta.",
}


class AccesRefuse(Exception):
    """L'accès ne permet pas d'appeler l'API. ``etat`` dit pourquoi ;
    ``message_fr`` ne contient jamais de secret."""

    def __init__(self, etat_acces):
        self.etat = etat_acces
        self.message_fr = MESSAGES_FR.get(etat_acces, MESSAGES_FR[INVALIDE])
        super().__init__(self.message_fr)


@dataclass(frozen=True)
class Configuration:
    enabled: bool
    jeton: str
    app_id: str
    app_secret: str

    def __repr__(self):  # jamais un secret dans un repr/log
        return (f'Configuration(enabled={self.enabled}, '
                f'jeton={masquer(self.jeton)!r}, app_id={self.app_id!r}, '
                f'app_secret={masquer(self.app_secret)!r})')

    __str__ = __repr__


def configuration():
    """Lit les réglages À CHAQUE appel (``override_settings`` en test)."""
    return Configuration(
        enabled=bool(getattr(settings, 'META_AD_LIBRARY_ENABLED', False)),
        jeton=str(getattr(settings, 'META_AD_LIBRARY_ACCESS_TOKEN', '') or ''),
        app_id=str(getattr(settings, 'META_AD_LIBRARY_APP_ID', '') or ''),
        app_secret=str(
            getattr(settings, 'META_AD_LIBRARY_APP_SECRET', '') or ''),
    )


def masquer(valeur):
    """Masque TOTAL d'un secret (jeton, secret d'application) : aucune lettre
    n'est montrée. Vide → ``''`` (pour dire « absent »)."""
    return MASQUE if valeur else ''


def masquer_secrets(texte, config=None):
    """Retire de ``texte`` toute occurrence du jeton, du secret d'application et
    du jeton d'application ``app_id|app_secret``."""
    config = config or configuration()
    texte = str(texte or '')
    secrets = [config.jeton, config.app_secret]
    if config.app_id and config.app_secret:
        secrets.insert(0, f'{config.app_id}|{config.app_secret}')
    for secret in secrets:
        if secret:
            texte = texte.replace(secret, MASQUE)
    return texte


def config_publique():
    """Vue SANS secret de la configuration (écran santé, logs)."""
    config = configuration()
    return {
        'enabled': config.enabled,
        'jeton': masquer(config.jeton),
        'app_id': config.app_id,
        'app_secret': masquer(config.app_secret),
    }


def societes_autorisees():
    brut = getattr(settings, 'VEILLE_SOCIETES_AUTORISEES', None) or []
    if isinstance(brut, str):
        brut = brut.split(',')
    ids = set()
    for valeur in brut:
        try:
            ids.add(int(str(valeur).strip()))
        except (TypeError, ValueError):
            continue
    return ids


def societe_autorisee(company):
    """D-VEIL-12 — la société figure-t-elle dans ``VEILLE_SOCIETES_AUTORISEES`` ?
    Défaut vide = personne (même avec ``adsengine_manage``)."""
    company_id = getattr(company, 'id', company)
    if company_id is None:
        return False
    return int(company_id) in societes_autorisees()


def derniere_verification():
    """Résultat mis en cache du dernier ``debug_token`` (ou ``None``)."""
    try:
        return cache.get(CLE_CACHE_VERIFICATION)
    except Exception:  # noqa: BLE001 — cache indisponible : pas de verdict
        return None


def _etat_de_base(company, config):
    if not config.jeton:
        return NON_CONFIGURE
    if not config.enabled:
        return DESACTIVE
    if not societe_autorisee(company):
        return NON_AUTORISE
    return PRET


def etat(company, *, verification=None, now=None):
    """État de l'accès pour ``company`` : ``{'etat', 'expire_le'}``.

    N'ouvre AUCUNE connexion : la date d'expiration est celle de la dernière
    vérification à la demande (``verifier``), si elle existe."""
    config = configuration()
    base = _etat_de_base(company, config)
    if base != PRET:
        logger.info('veille_acces: etat=%s config=%s', base, config_publique())
        return {'etat': base, 'expire_le': None}
    verification = verification if verification is not None \
        else derniere_verification()
    expire_le = None
    resultat = PRET
    if verification:
        if not verification.get('valide', False):
            resultat = INVALIDE
        expire_le = verification.get('expire_le')
        if resultat == PRET and expire_le:
            now = now or timezone.now()
            try:
                echeance = datetime.datetime.fromisoformat(expire_le)
            except (TypeError, ValueError):
                echeance = None
            if echeance is not None:
                if timezone.is_naive(echeance):
                    echeance = timezone.make_aware(
                        echeance, datetime.timezone.utc)
                if echeance - now <= datetime.timedelta(
                        days=ALERTE_EXPIRATION_JOURS):
                    resultat = EXPIRE_BIENTOT
    logger.info('veille_acces: etat=%s config=%s', resultat, config_publique())
    return {'etat': resultat, 'expire_le': expire_le}


def exiger_utilisable(company):
    """Lève :class:`AccesRefuse` si l'accès ne permet pas d'appeler l'API ;
    sinon renvoie la configuration. Ne fait AUCUN appel réseau."""
    courant = etat(company)
    if courant['etat'] not in ETATS_UTILISABLES:
        raise AccesRefuse(courant['etat'])
    return configuration()


def verifier(company, *, http_client=None):
    """Vérifie le jeton par ``debug_token`` (VEIL13), À LA DEMANDE seulement.

    Si l'accès n'est pas configuré, désactivé ou non autorisé pour cette
    société : AUCUNE requête n'est émise. Sinon UN appel, résultat mis en cache
    (``CLE_CACHE_VERIFICATION``) et état recalculé."""
    config = configuration()
    base = _etat_de_base(company, config)
    if base != PRET:
        return {'etat': base, 'expire_le': None}
    from .ad_library_client import AccesInvalide, AdLibraryClient, \
        AdLibraryErreur

    client = AdLibraryClient(
        config.jeton, app_id=config.app_id, app_secret=config.app_secret,
        http_client=http_client)
    try:
        resultat = client.verifier_jeton()
    except AccesInvalide:
        resultat = {'valide': False, 'expire_le': None}
    except AdLibraryErreur as exc:
        logger.warning('veille_acces: vérification impossible (%s)',
                       masquer_secrets(exc, config))
        return etat(company)
    try:
        cache.set(CLE_CACHE_VERIFICATION, resultat, DUREE_CACHE_VERIFICATION)
    except Exception:  # noqa: BLE001 — cache indisponible : état immédiat
        pass
    return etat(company, verification=resultat)
