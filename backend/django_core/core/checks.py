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
#: AUD410 — secrets restés au placeholder publié par ``.env.example``.
ID_SECRET_KEY = 'core.E_AUD410_SECRET_KEY'
ID_MINIO = 'core.E_AUD410_MINIO'
#: AUD411 — la couche de durcissement de ``prod.py``, absente ou désarmée.
ID_DURCISSEMENT = 'core.E_AUD411_DURCISSEMENT'
#: AUD411 — l'environnement se DÉCLARE production mais charge un autre module.
ID_MODULE_NON_PROD = 'core.W_AUD411_MODULE_NON_PROD'

#: AUD411 — CE QUE ``prod.py`` POSE ET QUE ``dev.py`` NE POSE PAS.
#:
#: QJR423 ne couvrait que ``DEBUG`` : le re-scope AUD411 est que le périmètre
#: réel n'est pas « DEBUG résiduel » mais TOUTE la couche ``prod.py``. Si
#: ``settings.dev`` est chargé en production, ``SESSION/CSRF_COOKIE_SECURE``,
#: ``SECURE_SSL_REDIRECT``, HSTS, le CORS restrictif ET le garde ``RuntimeError``
#: sur ``SECRET_KEY`` sont TOUS morts — pas seulement les traces DEBUG. Chaque
#: entrée : (réglage, valeur attendue, ce qui se passe sans elle).
REGLAGES_DURCISSEMENT = (
    ('SESSION_COOKIE_SECURE', True,
     'le cookie de session voyagerait en clair sur une requête HTTP'),
    ('CSRF_COOKIE_SECURE', True,
     'le cookie CSRF voyagerait en clair sur une requête HTTP'),
    ('SECURE_SSL_REDIRECT', True,
     "une requête HTTP ne serait jamais redirigée vers HTTPS"),
    ('SECURE_CONTENT_TYPE_NOSNIFF', True,
     'le navigateur devinerait le type de contenu servi'),
    ('CORS_ALLOW_ALL_ORIGINS', False,
     "n'importe quelle origine pourrait appeler l'API depuis un navigateur"),
)

#: AUD410 — les secrets d'une production, et le réglage qui les porte. Le
#: prédicat de placeholder vit dans ``erp_agentique/settings/placeholders.py``
#: (module sans Django, partagé avec le garde de démarrage de ``base.py``).
SECRETS_DE_PRODUCTION = (
    ('SECRET_KEY', 'DJANGO_SECRET_KEY', ID_SECRET_KEY,
     'la clé de signature des sessions ET des jetons JWT'),
    ('MINIO_SECRET_KEY', 'MINIO_ROOT_PASSWORD', ID_MINIO,
     "le mot de passe du stockage d'objets (PDF, pièces jointes, sauvegardes)"),
)


def secret_est_placeholder(valeur):
    """Vrai quand ``valeur`` est vide ou un placeholder publié du dépôt.

    Simple ré-export du prédicat pur de la couche réglages : le contrôle
    système et le garde de démarrage de ``base.py`` doivent partager UNE seule
    définition, sinon l'une des deux dérive au premier placeholder ajouté.
    """
    from erp_agentique.settings import placeholders
    return placeholders.est_placeholder(valeur)


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


def module_de_production(settings_module=None, environ=None):
    """AUD411 — vrai quand le module de réglages CHARGÉ est celui de prod.

    Distinct de :func:`environnement_de_production`, qui accepte AUSSI une
    simple variable d'environnement. La différence est tout l'objet d'AUD411 :
    ``DJANGO_ENV=prod`` déclare une intention, mais c'est le MODULE chargé qui
    décide si la couche de durcissement (cookies Secure, HSTS, redirection
    SSL, CORS restrictif, garde SECRET_KEY) existe réellement.
    """
    environ = os.environ if environ is None else environ
    if settings_module is None:
        settings_module = (
            getattr(settings, 'SETTINGS_MODULE', None)
            or environ.get('DJANGO_SETTINGS_MODULE', ''))
    return (settings_module or '').strip().lower().endswith(MODULES_PRODUCTION)


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

    erreurs.extend(verifier_secrets_publies())
    erreurs.extend(verifier_couche_durcissement())
    return erreurs


def verifier_couche_durcissement():
    """AUD411 — la couche ``prod.py`` est-elle RÉELLEMENT en place ?

    QJR423 ne regardait que ``DEBUG``. Le re-scope AUD411 : si la production
    charge ``settings.dev``, ce n'est pas seulement DEBUG qui manque —
    ``SESSION/CSRF_COOKIE_SECURE``, ``SECURE_SSL_REDIRECT``, HSTS, le CORS
    restrictif ET le garde ``RuntimeError`` sur ``SECRET_KEY`` sont TOUS morts.

    DEUX NIVEAUX, DÉLIBÉRÉMENT :

    * **Erreur bloquante** quand le module de production EST chargé mais qu'un
      réglage de durcissement a été désarmé — un ``prod.py`` amputé ne doit
      jamais démarrer en se faisant passer pour durci.
    * **Avertissement** (jamais bloquant) quand l'environnement se DÉCLARE
      production mais charge un autre module de réglages : c'est l'état que
      AUD411 soupçonne en production aujourd'hui. Le rendre bloquant
      COUPERAIT le service au premier redémarrage, avant que la bascule
      ``DJANGO_SETTINGS_MODULE=erp_agentique.settings.prod`` n'ait eu lieu.
      L'avertissement apparaît dans ``manage.py check`` et dans les journaux
      de déploiement : il NOMME l'écart au lieu de le laisser invisible.
    """
    from django.core.checks import Warning as CheckWarning

    if not module_de_production():
        module = (getattr(settings, 'SETTINGS_MODULE', None)
                  or os.environ.get('DJANGO_SETTINGS_MODULE') or '(inconnu)')
        return [CheckWarning(
            f'Cet environnement se déclare production mais charge « {module} » '
            f'— pas un module de production. TOUTE la couche de durcissement '
            f'de erp_agentique/settings/prod.py est alors inerte : cookies de '
            f'session/CSRF non Secure, aucune redirection HTTPS, aucun HSTS, '
            f'CORS ouvert, et le garde RuntimeError sur SECRET_KEY jamais '
            f'évalué.',
            hint='Posez DJANGO_SETTINGS_MODULE=erp_agentique.settings.prod '
                 'dans le .env du serveur, puis vérifiez la santé complète '
                 '(racine 200 / api 401, cookies Secure+HttpOnly sur une '
                 'connexion réelle).',
            id=ID_MODULE_NON_PROD)]

    erreurs = []
    for reglage, attendu, consequence in REGLAGES_DURCISSEMENT:
        if getattr(settings, reglage, None) is not attendu:
            erreurs.append(Error(
                f'{reglage} n\'est pas {attendu!r} alors que le module de '
                f'production est chargé : {consequence}.',
                hint=f'{reglage} vit dans erp_agentique/settings/prod.py — '
                     f'ne le surchargez pas depuis l\'environnement.',
                id=ID_DURCISSEMENT))
    if not (getattr(settings, 'SECURE_HSTS_SECONDS', 0) or 0) > 0:
        erreurs.append(Error(
            'SECURE_HSTS_SECONDS est nul alors que le module de production '
            'est chargé : le navigateur accepterait une première visite en '
            'HTTP clair.',
            hint='SECURE_HSTS_SECONDS vit dans '
                 'erp_agentique/settings/prod.py (31536000).',
            id=ID_DURCISSEMENT))
    return erreurs


def verifier_secrets_publies():
    """AUD410 — refuse une production dont un secret est resté au placeholder.

    Le garde de ``base.py`` ne se déclenche que lorsque ``DJANGO_DEBUG`` est
    faux ; une production qui se déclare telle par ``DJANGO_ENV`` mais tourne
    encore avec ``DJANGO_DEBUG=True`` (l'état réel constaté par AUD411) lui
    échappe entièrement. Ce contrôle referme ce trou, et étend la couverture à
    ``MINIO_ROOT_PASSWORD``, publié lui aussi en clair par ``.env.example`` et
    protégé par aucun garde.

    Ni le message ni l'indice ne citent JAMAIS la valeur du secret : seulement
    le nom du réglage et celui de la variable d'environnement.
    """
    erreurs = []
    for reglage, variable, identifiant, role in SECRETS_DE_PRODUCTION:
        valeur = getattr(settings, reglage, None)
        if not secret_est_placeholder(valeur):
            continue
        erreurs.append(Error(
            f'{reglage} est vide ou resté à un placeholder publié dans le '
            f'dépôt (.env.example) alors que cet environnement se déclare '
            f'production : {role} serait connu de quiconque lit le dépôt.',
            hint=f'Posez {variable}=<valeur générée> dans le .env du serveur '
                 '(clé Django : python -c "from django.core.management.utils '
                 'import get_random_secret_key; print(get_random_secret_key())'
                 '").',
            id=identifiant))
    return erreurs
