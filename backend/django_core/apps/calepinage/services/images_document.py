"""CALX302 — recevoir et retrouver les images PRODUITES PAR LE NAVIGATEUR
(carte de chaleur d'ombrage, diagramme de pertes, rendu 3D) et déposées par
``POST calepinages/<pk>/image-document/``.

LE CONSTAT
----------
La matrice d'ombrage 12×24 et l'accès solaire par module existent déjà dans
le document (``roof_layout.shading12x24``, ``zones[].geometry.solarAccess
.values``), et le rendu SERVEUR n'a AUCUN rasteriseur SVG installé
(``views/sorties.py`` : « Aucun rasteriseur SVG n'est installé » —
weasyprint 62.3 n'a plus de sortie PNG, ni cairosvg ni svglib ne sont des
dépendances). Une carte de chaleur, un diagramme de pertes ou un rendu 3D ne
peuvent donc être imprimés QUE si le NAVIGATEUR les a déjà rendus et les
dépose ici — le même repli que ``sorties/planche_png`` (CAL175).

L'ÉNUMÉRATION FERMÉE DES GENRES — le crochet laissé par CALX291
-----------------------------------------------------------------
``contract_samples/calepinage_documents.json`` (CALX291, PACT10) documentait
déjà la FORME du corps de ``POST image-document/`` sans fixer la liste des
``genre`` admis : « L'énumération EXACTE des `genre` admis … est déclarée
par CALX302 ». C'est ``GENRES_IMAGE`` ci-dessous — trois genres, un par
carte produite dans l'atelier, jamais un quatrième deviné.

STOCKAGE — ``records.Attachment`` RÉUTILISÉ TEL QUEL, AUCUNE MIGRATION
-------------------------------------------------------------------------
Même primitive que les versions de document (CALX322,
``services/documents/versions_document.py``) : le genre est ENCODÉ dans
``filename`` (``image__<genre>__<identifiant>.<ext>``) et RELU depuis lui —
une seule façon de l'écrire, une seule de le lire. Bornée à la société du
calepinage (SCA42, ``store_attachment(..., company=...)``).

VALIDATION DE CONTENU RÉELLE — JAMAIS UNE CONFIANCE AU ``Content-Type``
---------------------------------------------------------------------------
Le format est vérifié PAR SES OCTETS MAGIQUES (``store_attachment``, PDF/
PNG/JPEG/WebP), pas par l'en-tête déclaré par le navigateur ; la TAILLE est
bornée (10 Mo, ``store_attachment``) ; les DIMENSIONS sont vérifiées en
décodant RÉELLEMENT l'image avec Pillow (déjà une dépendance pinnée,
``requirements.txt``) — un fichier illisible, ou hors des bornes
raisonnables d'une capture d'écran, est refusé EN NOMMANT le champ
``fichier``, jamais silencieusement accepté ou silencieusement tronqué.
"""
from __future__ import annotations

import base64
import binascii
import logging
import uuid

logger = logging.getLogger(__name__)

__all__ = [
    'GENRES_IMAGE', 'ImageDocumentRefuse', 'deposer_image_document',
    'images_du_calepinage', 'image_recente', 'octets_et_mime',
    'derniere_image_encodee',
]

#: L'énumération FERMÉE des genres d'image déposables — le crochet laissé
#: par CALX291 (``contract_samples/calepinage_documents.json``). Un genre
#: hors de cette liste est refusé en la citant, jamais deviné.
GENRES_IMAGE = ('ombrage', 'sankey', 'plan3d')

#: Le séparateur du nom de fichier encodé — jamais présent dans un genre de
#: cette liste (même discipline que ``versions_document._SEPARATEUR``).
_SEPARATEUR = '__'
_PREFIXE = 'image' + _SEPARATEUR

#: Bornes RAISONNABLES pour une capture d'écran (jamais un scan, jamais une
#: vignette) — un fichier hors bornes est refusé en NOMMANT le champ.
_TAILLE_MIN_COTE_PX = 8
_TAILLE_MAX_COTE_PX = 8000

#: Extensions retenues du nom REÇU (informatif seulement — le format RÉEL
#: est celui que ``store_attachment`` détecte par octets magiques).
_EXTENSIONS_CONNUES = ('png', 'jpg', 'jpeg', 'webp')


class ImageDocumentRefuse(ValueError):
    """Refus métier — le CHAMP fautif est nommé (règle fondateur 08/09)."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _content_type_calepinage():
    from django.contrib.contenttypes.models import ContentType

    from ..models import Calepinage

    return ContentType.objects.get_for_model(Calepinage)


def _decoder_fichier(fichier):
    """Octets + nom REÇU depuis un ``UploadedFile`` (multipart) OU une
    data-URL base64 (``data:image/png;base64,…`` — CALX291 : « le PNG vient
    du navigateur »). Refuse TOUJOURS en NOMMANT ``fichier``, jamais une
    exception non attrapée qui remonterait en 500."""
    if fichier is None or fichier == '':
        raise ImageDocumentRefuse(
            'Fichier requis : aucune image reçue.', champ='fichier')
    if hasattr(fichier, 'read'):
        octets = fichier.read()
        try:
            fichier.seek(0)
        except Exception:  # noqa: BLE001 — flux non rembobinable, lu une fois
            pass
        return bytes(octets), (getattr(fichier, 'name', '') or '')
    if isinstance(fichier, (bytes, bytearray)):
        return bytes(fichier), ''
    if isinstance(fichier, str):
        brut = fichier.strip()
        if not brut:
            raise ImageDocumentRefuse(
                'Fichier requis : aucune image reçue.', champ='fichier')
        if brut.startswith('data:'):
            _entete, _virgule, brut = brut.partition(',')
            if not brut:
                raise ImageDocumentRefuse(
                    'Image illisible : la donnée « data: » ne porte aucun '
                    'contenu encodé.', champ='fichier')
        try:
            return base64.b64decode(brut, validate=True), ''
        except (binascii.Error, ValueError) as erreur:
            raise ImageDocumentRefuse(
                'Image illisible : le contenu base64 est invalide.',
                champ='fichier') from erreur
    raise ImageDocumentRefuse(
        'Fichier illisible : format de corps non reconnu.', champ='fichier')


def _valider_dimensions(octets):
    """Décode RÉELLEMENT l'image (Pillow) — jamais une confiance au nom ou
    au ``Content-Type`` déclarés par le navigateur. Refuse un fichier
    illisible ou hors bornes RAISONNABLES pour une capture d'écran, en
    NOMMANT le champ ``fichier``."""
    import io

    from PIL import Image, UnidentifiedImageError

    try:
        controle = Image.open(io.BytesIO(octets))
        controle.verify()
    except (UnidentifiedImageError, OSError, ValueError) as erreur:
        raise ImageDocumentRefuse(
            'Image illisible : le fichier déposé n’est pas une image '
            'décodable.', champ='fichier') from erreur
    # ``verify()`` consomme le lecteur : rouvrir pour lire les dimensions.
    image = Image.open(io.BytesIO(octets))
    largeur, hauteur = image.size
    if largeur < _TAILLE_MIN_COTE_PX or hauteur < _TAILLE_MIN_COTE_PX:
        raise ImageDocumentRefuse(
            'Image trop petite (%sx%s px, minimum %spx de côté) : ce '
            'n’est pas une capture exploitable.'
            % (largeur, hauteur, _TAILLE_MIN_COTE_PX), champ='fichier')
    if largeur > _TAILLE_MAX_COTE_PX or hauteur > _TAILLE_MAX_COTE_PX:
        raise ImageDocumentRefuse(
            'Image trop grande (%sx%s px, maximum %spx de côté) : ce '
            'n’est pas une capture d’écran.'
            % (largeur, hauteur, _TAILLE_MAX_COTE_PX), champ='fichier')


def deposer_image_document(calepinage, *, genre, fichier, user=None):
    """Dépose ``fichier`` comme image ``genre`` de ``calepinage``.

    Returns:
        dict: ``{genre, attachment (l'objet Attachment créé), depose_le}``.

    Raises:
        ImageDocumentRefuse: calepinage non enregistré, genre inconnu,
            fichier absent/illisible, ou refus du stockage (format/taille).
    """
    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise ImageDocumentRefuse(
            'Calepinage non enregistré : aucune image ne peut être '
            'déposée.', champ='calepinage')
    genre_propre = (genre or '').strip()
    if genre_propre not in GENRES_IMAGE:
        raise ImageDocumentRefuse(
            'Genre d’image inconnu : « %s ». Genres admis : %s.'
            % (genre or '', ', '.join(GENRES_IMAGE)), champ='genre')

    octets, nom_recu = _decoder_fichier(fichier)
    if not octets:
        raise ImageDocumentRefuse('Image vide : rien n’est déposé.',
                                  champ='fichier')
    _valider_dimensions(octets)

    from django.core.files.base import ContentFile

    from apps.records.models import Attachment
    from apps.records.storage import store_attachment

    extension = (nom_recu.rsplit('.', 1)[-1].lower()
                 if '.' in nom_recu else 'png')
    if extension not in _EXTENSIONS_CONNUES:
        extension = 'png'
    nom = '%s%s%s%s.%s' % (
        _PREFIXE, genre_propre, _SEPARATEUR, uuid.uuid4().hex[:12],
        extension)
    enveloppe = ContentFile(octets, name=nom)
    donnees, erreur = store_attachment(enveloppe, company=calepinage.company)
    if erreur:
        raise ImageDocumentRefuse(erreur, champ='fichier')

    utilisateur = user if getattr(user, 'pk', None) else None
    piece = Attachment.objects.create(
        company=calepinage.company,
        content_type=_content_type_calepinage(), object_id=calepinage.pk,
        uploaded_by=utilisateur, **donnees)

    return {'genre': genre_propre, 'attachment': piece,
            'depose_le': piece.created_at}


def _attachments_images(calepinage, *, genre=None):
    from apps.records.models import Attachment

    qs = (Attachment.objects
          .filter(content_type=_content_type_calepinage(),
                  object_id=calepinage.pk, company=calepinage.company,
                  filename__startswith=_PREFIXE)
          .order_by('-id'))
    if genre:
        qs = qs.filter(filename__startswith='%s%s%s' % (
            _PREFIXE, genre, _SEPARATEUR))
    return qs


def _genre_depuis_nom(filename):
    """``image__<genre>__<id>.<ext>`` → ``<genre>`` — ``''`` si illisible
    (ligne défensive : ne doit jamais lever pour un nom hors schéma)."""
    morceaux = (filename or '').split(_SEPARATEUR)
    return morceaux[1] if len(morceaux) > 2 else ''


def images_du_calepinage(calepinage):
    """Les images déposées de CE calepinage, la PLUS RÉCENTE d'abord —
    forme ``{genre, attachment, depose_le}`` (contrat
    ``calepinage_documents.json::exemple.images``). Bornées à SA société."""
    if calepinage is None or not getattr(calepinage, 'pk', None):
        return []
    return [{'genre': _genre_depuis_nom(a.filename), 'attachment': a.pk,
             'depose_le': a.created_at}
            for a in _attachments_images(calepinage)]


def image_recente(calepinage, *, genre):
    """Le dernier ``Attachment`` déposé pour ``genre``, ou ``None``."""
    if calepinage is None or not getattr(calepinage, 'pk', None):
        return None
    return _attachments_images(calepinage, genre=genre).first()


def octets_et_mime(attachment):
    """``(octets, mime)`` de la pièce déposée, ou ``(None, None)`` — une
    lecture MinIO impossible ne lève jamais (best-effort, même discipline
    que ``versions_document`` : un incident de relecture ne doit jamais
    faire tomber tout le document qui l'embarque)."""
    if attachment is None:
        return None, None
    from apps.records.storage import fetch_attachment

    octets, erreur = fetch_attachment(attachment.file_key)
    if erreur:
        logger.warning('CALX302 : image %s illisible (%s)', attachment.pk,
                       erreur)
        return None, None
    return octets, (attachment.mime or 'image/png')


def derniere_image_encodee(calepinage, *, genre):
    """La dernière image ``genre`` de ``calepinage``, en data-URI base64
    prête à embarquer dans un ``<img src=…>`` de pièce PDF — ``None`` si
    aucune image n'est déposée ou si sa relecture échoue."""
    piece = image_recente(calepinage, genre=genre)
    if piece is None:
        return None
    octets, mime = octets_et_mime(piece)
    if not octets:
        return None
    return 'data:%s;base64,%s' % (mime, base64.b64encode(octets)
                                  .decode('ascii'))
