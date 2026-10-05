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

from datetime import timedelta

__all__ = ['RACINE_API', 'DUREE_URL_IMAGE', 'url_fichier_photo',
           'url_fichier_plan', 'url_fichier_roof_image',
           'reference_calepinage', 'image_apercu']

#: Durée de validité annoncée du rendu (celle du stockage ventes).
DUREE_URL_IMAGE = timedelta(hours=1)

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


def reference_calepinage(calepinage):
    """« CAL-AAMM-0001 » — DÉRIVÉE, jamais un numéro stocké.

    ACAL196 — LA fonction unique : le détail (``views/calepinages.py``) et la
    LISTE (``serializers.py``) publient la même référence, sans que le
    sérialiseur ait à importer une vue (cycle). Le modèle ne porte pas de
    référence (aucune migration) : l'étiquette est déduite de la date de
    création et de l'identifiant, donc stable dans le temps et incapable de
    « rétrécir » comme un ``count()+1``. Le jour où une vraie numérotation
    arrivera, elle passera par ``apps/ventes/utils/references.py``.
    """
    cree = getattr(calepinage, 'created_at', None)
    if cree is None:
        return f'CAL-{calepinage.pk:04d}'
    return f'CAL-{cree.strftime("%y%m")}-{calepinage.pk:04d}'


def image_apercu(calepinage):
    """``{url, genere_le, expire_le}`` du rendu stocké, ou trois ``null``.

    ACAL200 : l'URL est un chemin RELATIF même origine servi par Django
    (``roof-image/fichier/``) — jamais une URL pré-signée vers l'hôte interne
    de MinIO, et aucune signature n'est calculée par ligne (ACAL196). Sans
    rendu enregistré, trois ``null``. ``expire_le`` garde la forme du contrat
    (génération + une heure : la fenêtre pendant laquelle l'aperçu est
    garanti frais).
    """
    from django.utils import timezone

    cle = getattr(calepinage, 'roof_image', '')
    cle = cle.strip() if isinstance(cle, str) else ''
    if not cle:
        return {'url': None, 'genere_le': None, 'expire_le': None}
    maintenant = timezone.now()
    return {
        'url': url_fichier_roof_image(calepinage.pk),
        'genere_le': maintenant.isoformat(),
        'expire_le': (maintenant + DUREE_URL_IMAGE).isoformat(),
    }
