"""CAL19 — LE stockage du rendu de toiture, pour ventes ET pour calepinage.

``apps/ventes/views/devis.py::roof_image`` fait DÉJÀ tout ce qu'il faut :
validation magic-bytes, clé MinIO scopée société
(``roofs/<company_id>/<reference>.<ext>``) et URL présignée une heure
(``utils/pdf.py::upload_roof_image`` / ``roof_image_signed_url``).

Le module Calepinage a besoin du MÊME stockage — et surtout PAS d'un second
chemin : deux chemins, ce serait deux conventions de clé, deux politiques
d'expiration, et un jour deux buckets dont un seul serait sauvegardé. Ces trois
fonctions MINCES sont donc la porte publique du stockage existant ; elles sont
ré-exportées par ``apps.ventes.services`` (règle QJR68 : la surface cross-app
ne porte aucun corps, l'implémentation vit ici). ``apps.calepinage`` les appelle
et n'importe ni une vue ni un modèle ventes (contrat import-linter).
"""
from __future__ import annotations

#: Signatures des formats admis pour un rendu de toiture -> (extension, MIME).
#: Source UNIQUE : elle reprend mot pour mot la validation de
#: ``views/devis.py`` (PNG ``\x89PNG``, JPEG ``\xff\xd8\xff``).
SIGNATURES_IMAGE_TOITURE = (
    (b'\x89PNG\r\n\x1a\n', 'png', 'image/png'),
    (b'\xff\xd8\xff', 'jpg', 'image/jpeg'),
)


def type_image_toiture(donnees):
    """``(extension, type MIME)`` d'un rendu, ou ``(None, None)``.

    Reconnaissance par les OCTETS, jamais par le nom de fichier ni par le
    ``Content-Type`` annoncé : les deux se falsifient. Un format non reconnu
    rend ``(None, None)`` et l'appelant refuse en le DISANT.
    """
    donnees = donnees or b''
    for signature, extension, mime in SIGNATURES_IMAGE_TOITURE:
        if donnees[:len(signature)] == signature:
            return extension, mime
    return None, None


def stocker_image_toiture(donnees, cle, *, content_type='image/png'):
    """Dépose un rendu dans le bucket EXISTANT, sous ``cle``.

    La clé est fournie par l'appelant et porte sa société
    (``roofs/<company_id>/…``) ; le bucket est celui des PDF, créé au besoin
    par le même helper que le chemin devis. Renvoie la clé stockée.
    """
    from ..quote_engine.builder import _ensure_pdf_bucket
    from ..utils.pdf import upload_roof_image

    _ensure_pdf_bucket()
    upload_roof_image(donnees, cle, content_type=content_type)
    return cle


def lire_fichier_toiture(cle):
    """Les OCTETS de l'objet stocké sous ``cle``, ou ``None`` (CALX5).

    Le pendant en lecture de :func:`stocker_image_toiture`, pour les dépôts
    qu'un SERVEUR doit relire lui-même (la série météo déposée par la société,
    CALX62) : une URL présignée sert un navigateur, pas une tâche de fond.
    Objet absent ou magasin injoignable ⇒ ``None`` : l'appelant DIT alors ce
    qu'il n'a pas pu lire, il ne le remplace pas.
    """
    if not cle:
        return None
    from ..utils.pdf import download_roof_image

    try:
        return download_roof_image(cle)
    except Exception:  # noqa: BLE001 — cf. docstring : absence, pas erreur
        return None


def poser_affiche_depuis(devis, cle_source):
    """ACAL98 (C-ACAL-107) — l'affiche 3D d'un calepinage devient celle du devis.

    COPIE des octets stockés sous ``cle_source`` (le rendu du calepinage,
    ``roofs/<company>/calepinage-<pk>.png``) vers la clé PROPRE du devis
    (``roofs/<company>/<reference>.<ext>``, la convention de
    ``views/devis_calepinage.py::roof_image``), puis ``Devis.roof_image`` est
    posé (écriture ciblée ``update_fields=['roof_image']`` : aucun statut ne
    bouge, règle #4). Jamais une clé PARTAGÉE : réécrire ensuite l'image du
    calepinage ne change pas l'affiche d'un devis (D-ACAL-1 — elle ne change
    que par un geste explicite : génération ou resynchronisation).

    Rend la clé posée, ou ``None`` (rien n'est écrit) quand la source est
    vide, illisible ou n'est pas un PNG/JPEG reconnu par ses octets.
    """
    if devis is None or not cle_source:
        return None
    donnees = lire_fichier_toiture(cle_source)
    if not donnees:
        return None
    extension, mime = type_image_toiture(donnees)
    if extension is None:
        return None
    company_id = getattr(devis, 'company_id', None) or '0'
    cle = f'roofs/{company_id}/{devis.reference}.{extension}'
    stocker_image_toiture(donnees, cle, content_type=mime)
    devis.roof_image = cle
    devis.save(update_fields=['roof_image'])
    return cle


#: ACAL299 — le SEUL préfixe que :func:`supprimer_fichier_toiture` accepte : le
#: bucket des PDF porte aussi les devis rendus, jamais effaçables par ici.
PREFIXE_TOITURE = 'roofs/'


def supprimer_fichier_toiture(cle):
    """Supprime l'objet stocké sous ``cle`` dans le magasin des rendus (ACAL299).

    Le pendant en effacement de :func:`stocker_image_toiture` — pour les
    photos de site d'un calepinage (effacement loi 09-08). Clé vide ou
    ``None`` : no-op silencieux. Une clé qui ne commence pas par ``roofs/``
    (ou qui remonte d'un segment par ``..``) est REFUSÉE par ``ValueError`` :
    jamais une suppression arbitraire dans le bucket des PDF. Un objet déjà
    absent n'est pas une erreur (la suppression S3 est idempotente).
    """
    if not cle:
        return None
    if (not isinstance(cle, str) or not cle.startswith(PREFIXE_TOITURE)
            or '..' in cle.split('/')):
        raise ValueError(
            "Suppression refusée : la clé %r n'est pas un rendu de toiture "
            "(préfixe %r attendu)." % (cle, PREFIXE_TOITURE))
    from django.conf import settings

    from ..utils.minio_client import get_minio_client

    get_minio_client().delete_object(Bucket=settings.MINIO_BUCKET_PDF,
                                     Key=cle)
    return None


def url_image_toiture(cle, *, expires=3600):
    """L'URL PRÉSIGNÉE (lecture seule, 1 h) d'un rendu stocké, ou ``None``.

    Jamais d'accès public direct au bucket : la lecture passe toujours par une
    URL signée à durée courte, exactement comme le chemin devis.
    """
    # Le refus AVANT l'import : une clé vide ne doit même pas faire charger le
    # client de stockage (et, sur un poste sans les bibliothèques de rendu,
    # l'import échouerait pour rien).
    if not cle:
        return None
    from ..utils.pdf import roof_image_signed_url

    return roof_image_signed_url(cle, expires=expires)


# ── ACAL314 (C-ACAL-019 / C-ACAL-107) — l'affiche servie MÊME ORIGINE ───────
#
# Une URL pré-signée porte l'hôte INTERNE du magasin (``MINIO_ENDPOINT`` =
# ``minio:9000``) : le navigateur du client ne l'atteint jamais. L'affiche
# destinée à un navigateur est donc servie par Django, sous un chemin RELATIF
# que ce module est le SEUL à fabriquer (jumeau assumé du constructeur
# calepinage ``apps/calepinage/services/presentation.py`` — frontière
# inter-apps). ``url_image_toiture`` / ``roof_image_signed_url`` restent pour
# d'éventuelles lectures serveur, plus jamais pour un navigateur.

#: La racine de l'API ventes, telle que ``config/urls.py`` la monte.
RACINE_API_VENTES = '/api/django/ventes'


def url_fichier_toiture_devis(devis_id):
    """Chemin AUTHENTIFIÉ (cookie httpOnly) de l'affiche d'un devis."""
    return f'{RACINE_API_VENTES}/devis/{devis_id}/roof-image/fichier/'


def url_fichier_toiture_proposition(token):
    """Chemin PUBLIC (borné par le jeton de proposition) de l'affiche."""
    return f'{RACINE_API_VENTES}/proposal/{token}/roof-image/'


def lire_image_toiture(cle):
    """``(octets, type MIME)`` de l'affiche stockée sous ``cle``, ou
    ``(None, None)`` — clé vide, objet absent, magasin injoignable ou octets
    qui ne sont pas un PNG/JPEG reconnu. Le MIME vient des OCTETS
    (:func:`type_image_toiture`), jamais de l'extension de la clé."""
    donnees = lire_fichier_toiture(cle)
    if not donnees:
        return None, None
    _extension, mime = type_image_toiture(donnees)
    if mime is None:
        return None, None
    return donnees, mime
