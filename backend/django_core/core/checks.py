"""QJR423 / DR8 — les contrôles système des réglages de PRODUCTION.

CE QUI N'ÉTAIT PAS GARANTI. ``erp_agentique/settings/prod.py`` porte DÉJÀ
``DEBUG = False`` en dur — il n'y a donc rien à « couper » dans le code. Ce
qui n'était garanti nulle part, c'est que la production CHARGE bien ce module :
``wsgi.py`` ne retient ``erp_agentique.settings.prod`` que si
``DJANGO_SETTINGS_MODULE`` n'est pas déjà posé dans l'environnement, et le
``.env.example`` du dépôt pose ``erp_agentique.settings.dev`` **et**
``DJANGO_DEBUG=True``. Le ``.env`` réel du serveur n'est pas dans le dépôt :
depuis ce dépôt, « DEBUG est allumé en production » ne pouvait être ni
confirmé ni infirmé. C'est ce trou que ces contrôles ferment.

LA RÈGLE. Dès que l'environnement SE DÉCLARE production — module de réglages
``…settings.prod`` / ``…settings.production``, ou variable d'environnement
``DJANGO_ENV``/``ENVIRONMENT``/``APP_ENV``/``ENV`` valant ``prod``/
``production`` — deux réglages deviennent des ERREURS bloquantes :

  · ``DEBUG`` vrai — le mode debug expose la trace complète, les requêtes SQL
    et les réglages ; il ne peut plus démarrer en production, quel que soit le
    module qui l'a posé ;
  · ``ALLOWED_HOSTS`` laissé au défaut PERMISSIF de ``base.py``
    (``localhost,127.0.0.1``), vide, ou ouvert au joker ``*``.

Un contrôle système de niveau ``Error`` fait ÉCHOUER toute commande
``manage.py`` (``migrate``, ``collectstatic``, ``runserver``…) : le démarrage
est donc refusé, avec un message qui NOMME le réglage fautif.

HORS PRODUCTION, C'EST UN NO-OP TOTAL : le développement (``settings.dev``,
``DEBUG = True``, ``ALLOWED_HOSTS`` au défaut) et la CI (qui tourne sur
``erp_agentique.settings.dev``) sont strictement inchangés.
"""
import os

from django.conf import settings
from django.core.checks import Error, Tags, register

#: Suffixes d'un module de réglages qui se déclare « production ».
MODULES_PRODUCTION = ('.prod', '.production')

#: Variables d'environnement consultées pour la même déclaration.
VARIABLES_ENVIRONNEMENT = ('DJANGO_ENV', 'ENVIRONMENT', 'APP_ENV', 'ENV')

#: Valeurs de ces variables qui signifient « production ».
VALEURS_PRODUCTION = frozenset({'prod', 'production'})

#: Le défaut PERMISSIF hérité de ``base.py`` : il n'autorise que la machine
#: locale, donc il n'a jamais été choisi pour une production.
ALLOWED_HOSTS_DEFAUT_PERMISSIF = frozenset({'localhost', '127.0.0.1'})

#: Les jokers qui ouvrent l'application à n'importe quel en-tête ``Host``.
ALLOWED_HOSTS_JOKERS = frozenset({'*', '.*'})

ID_DEBUG = 'core.E_QJR423_DEBUG'
ID_ALLOWED_HOSTS = 'core.E_QJR423_ALLOWED_HOSTS'


def environnement_de_production(settings_module=None, environ=None):
    """Vrai quand l'environnement SE DÉCLARE production.

    Deux sources, l'une ou l'autre suffit :
      · le module de réglages chargé (``settings.SETTINGS_MODULE``, ou à
        défaut ``DJANGO_SETTINGS_MODULE``) se termine par ``.prod`` /
        ``.production`` ;
      · une variable d'environnement d'usage courant le dit explicitement.

    Aucun effet de bord, aucune I/O : la fonction est pure et testable seule.
    """
    environ = os.environ if environ is None else environ
    if settings_module is None:
        settings_module = (
            getattr(settings, 'SETTINGS_MODULE', None)
            or environ.get('DJANGO_SETTINGS_MODULE', ''))
    nom = (settings_module or '').strip().lower()
    if nom.endswith(MODULES_PRODUCTION):
        return True
    for variable in VARIABLES_ENVIRONNEMENT:
        valeur = (environ.get(variable) or '').strip().lower()
        if valeur in VALEURS_PRODUCTION:
            return True
    return False


def allowed_hosts_permissif(hotes):
    """Vrai quand ``ALLOWED_HOSTS`` n'a manifestement pas été choisi pour une
    production : liste vide, joker ``*``, ou strictement le défaut local de
    ``base.py``. Un hôte réel ajouté à côté de ``localhost`` reste accepté."""
    valeurs = {
        str(h).strip().lower() for h in (hotes or []) if str(h).strip()}
    if not valeurs:
        return True
    if valeurs & ALLOWED_HOSTS_JOKERS:
        return True
    return valeurs <= ALLOWED_HOSTS_DEFAUT_PERMISSIF


@register(Tags.security)
def verifier_reglages_production(app_configs=None, **kwargs):
    """QJR423 — refuse le démarrage d'une production mal réglée."""
    if not environnement_de_production():
        return []

    erreurs = []
    if getattr(settings, 'DEBUG', False):
        erreurs.append(Error(
            'DEBUG est VRAI alors que cet environnement se déclare '
            'production : la trace complète, les requêtes SQL et les réglages '
            'seraient exposés au premier visiteur.',
            hint="Posez DJANGO_DEBUG=0 et DJANGO_SETTINGS_MODULE="
                 "erp_agentique.settings.prod dans le .env du serveur "
                 '(erp_agentique/settings/prod.py porte déjà DEBUG = False ; '
                 "c'est le module chargé qu'il faut corriger).",
            id=ID_DEBUG))

    if allowed_hosts_permissif(getattr(settings, 'ALLOWED_HOSTS', None)):
        erreurs.append(Error(
            "ALLOWED_HOSTS est laissé au défaut permissif de base.py "
            "(localhost,127.0.0.1), vide, ou ouvert au joker « * » : une "
            'production doit nommer EXPLICITEMENT ses domaines.',
            hint='Posez DJANGO_ALLOWED_HOSTS=api.taqinor.ma,<autres domaines> '
                 'dans le .env du serveur.',
            id=ID_ALLOWED_HOSTS))
    return erreurs
