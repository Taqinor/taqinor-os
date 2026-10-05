"""ACAL200 — UN constructeur d'URL de fichier servi par Django (même origine).

Le navigateur ne lit JAMAIS MinIO : l'hôte interne ``minio:9000`` d'une URL
pré-signée lui est injoignable. Toute pièce visible d'un calepinage (photo de
site, plan importé, aperçu de toiture) est donc servie par un proxy Django, et
ce module est l'UNIQUE endroit qui fabrique son chemin — jamais une URL
pré-signée recopiée trois fois (``photos``, ``plan-importe``, ``roof-image``).

Le chemin est RELATIF (``/api/django/…``) : il se résout sur l'origine de la
page, derrière nginx comme en développement.
"""
from __future__ import annotations

__all__ = ['RACINE_API', 'url_fichier_photo',
           'url_fichier_plan', 'url_fichier_roof_image']

#: La racine de l'API du module, telle que ``urls.py`` la monte.
RACINE_API = '/api/django/calepinage/calepinages'


def _url_fichier(calepinage_id, ressource, ressource_id=None):
    """``/api/django/calepinage/calepinages/<id>/<ressource>[/<rid>]/fichier/``.

    ``ressource`` : ``photos`` (avec ``ressource_id`` = id de la photo),
    ``plan-importe`` ou ``roof-image`` (sans identifiant).
    """
    milieu = f'{ressource}/{ressource_id}' if ressource_id is not None \
        else ressource
    return f'{RACINE_API}/{calepinage_id}/{milieu}/fichier/'


def url_fichier_photo(calepinage_id, photo_id):
    return _url_fichier(calepinage_id, 'photos', photo_id)


def url_fichier_plan(calepinage_id):
    return _url_fichier(calepinage_id, 'plan-importe')


def url_fichier_roof_image(calepinage_id):
    return _url_fichier(calepinage_id, 'roof-image')
