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
