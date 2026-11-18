"""
WSGI config for erp_agentique project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.prod')

application = get_wsgi_application()


def charger_routes():
    """Importe ``ROOT_URLCONF`` (donc toutes les vues) et le gestionnaire 500
    AU DÉMARRAGE du processus serveur, plus à la première requête de chaque worker.

    Incident du 18/11/2026 : sous ``gunicorn --preload``, le maître gardait le
    code de son démarrage mais chaque worker importait les routes à sa première
    requête. Fichiers montés avancés sans redémarrage ⇒ tout worker né ensuite
    importait des vues neuves contre des modules anciens : ``ImportError`` à
    chaque requête, levée aussi par ``resolve_error_handler(500)``, donc page
    nue « Internal Server Error » de gunicorn (47 % des appels). Chargées ici,
    les routes sont dans la mémoire du maître, partagée par fork avec tous les
    workers (ils ne relisent plus le disque) ; un code incohérent fait échouer
    le démarrage du conteneur, que le deploy voit, au lieu de chaque requête.
    """
    from django.db import connections
    from django.urls import get_resolver
    resolveur = get_resolver()
    _ = resolveur.url_patterns  # l'accès importe l'urlconf et ses include()
    resolveur.resolve_error_handler(500)
    # Une connexion ouverte par un import ne passe jamais aux workers forkés
    # (jamais une connexion dans une transaction en cours : celle d'un test).
    for connexion in connections.all(initialized_only=True):
        if not connexion.in_atomic_block:
            connexion.close()
    return resolveur


charger_routes()
