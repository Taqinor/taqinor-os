"""Photos de profil employé — stockage MinIO via boto3.

Même mécanisme que les logos/signatures d'entreprise (apps.parametres.views) :
clé objet stockée en base, fichier dans le bucket erp-uploads, validation par
octets magiques. Aucune dépendance nouvelle (boto3 déjà présent ; Pillow déjà
fourni par WeasyPrint si une vérification d'image plus poussée devenait utile).
"""
import uuid
from urllib.parse import quote

from django.conf import settings

from apps.ventes.utils.minio_client import ensure_uploads_bucket, get_minio_client

_ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
_MAX_BYTES = 2 * 1024 * 1024

# Préfixe d'objet réservé aux photos de profil dans le bucket erp-uploads. Le
# proxy de lecture (UserViewSet.avatar_image) n'accepte QUE des clés sous ce
# préfixe, pour ne jamais relayer un objet arbitraire du bucket.
_AVATAR_PREFIX = 'avatars/'

_AVATAR_MIME_BY_EXT = {
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'webp': 'image/webp',
}


def _detect_image_type(header: bytes):
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if header[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'image/webp'
    return None


def avatar_mime_for_key(key):
    """Type MIME déduit de l'extension de la clé (défaut image/png)."""
    ext = key.rsplit('.', 1)[-1].lower() if key and '.' in key else ''
    return _AVATAR_MIME_BY_EXT.get(ext, 'image/png')


def is_avatar_key(key):
    """La clé désigne-t-elle bien une photo de profil (préfixe attendu) ?"""
    return bool(key) and str(key).startswith(_AVATAR_PREFIX) \
        and '..' not in str(key)


def presign_avatar(key):
    """URL de lecture d'une photo de profil, ou None si pas de clé.

    BUG HISTORIQUE (T-U13) : on renvoyait ici une URL présignée MinIO qui pointe
    sur l'hôte INTERNE du conteneur (``settings.MINIO_ENDPOINT`` = ``minio:9000``),
    INJOIGNABLE depuis le navigateur — l'``<img>`` tombait en 404 et seules les
    initiales s'affichaient. Même classe de bug déjà corrigée pour les pièces
    jointes (apps.records.storage) : on relaie le fichier via Django (MÊME
    ORIGINE), authentifié par le cookie, au lieu d'une URL présignée interne.

    On renvoie donc un chemin RELATIF de même origine vers le proxy de lecture
    (``GET /api/django/users/avatar-image/?key=...``). nginx route ce chemin vers
    Django, qui streame les octets depuis MinIO côté serveur. Le navigateur n'a
    jamais à joindre MinIO directement."""
    if not is_avatar_key(key):
        return None
    return f'/api/django/users/avatar-image/?key={quote(key, safe="")}'


def fetch_avatar(key):
    """Octets de la photo stockée, ou (None) en cas d'absence/erreur.

    Source du proxy de lecture de même origine (UserViewSet.avatar_image)."""
    if not is_avatar_key(key):
        return None
    try:
        client = get_minio_client()
        obj = client.get_object(
            Bucket=settings.MINIO_BUCKET_UPLOADS, Key=key)
        return obj['Body'].read()
    except Exception:
        return None


def _company_id(company):
    """Identifiant de société pour le préfixe de clé, ou None (instance ou int)."""
    if company is None:
        return None
    cid = getattr(company, 'id', company)
    return cid or None


def store_avatar(file, old_key='', *, company=None):
    """Valide + téléverse une photo, supprime l'ancienne.

    Retourne (key, None) en cas de succès, (None, message) en cas d'erreur.

    SCA42 — isolation par société : quand ``company`` est fourni, la clé du
    NOUVEL objet est préfixée par la société (``avatars/{company_id}/{uuid}.ext``)
    — motif ERR75 généralisé. La clé reste sous le préfixe ``avatars/`` (donc
    ``is_avatar_key``/le proxy de lecture continuent de l'accepter). Sans
    ``company`` (appel historique) on retombe sur ``avatars/{uuid}.ext``. Les
    objets DÉJÀ stockés ne bougent pas : la lecture utilise la clé STOCKÉE, donc
    les anciennes photos restent servies quelle que soit la forme de la clé.
    """
    if file.size > _MAX_BYTES:
        return None, 'Fichier trop volumineux (max 2 Mo).'

    header = file.read(12)
    file.seek(0)
    detected = _detect_image_type(header)
    if detected is None:
        return None, 'Format non supporté. Utilisez PNG, JPEG ou WebP.'

    ext = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''
    if ext not in _ALLOWED_EXTENSIONS:
        ext = detected.split('/')[-1].replace('jpeg', 'jpg')
    cid = _company_id(company)
    if cid is not None:
        key = f"avatars/{cid}/{uuid.uuid4().hex}.{ext}"
    else:
        key = f"avatars/{uuid.uuid4().hex}.{ext}"

    client = get_minio_client()
    ensure_uploads_bucket()  # N108 — self-heal a missing bucket before upload
    client.upload_fileobj(
        file,
        settings.MINIO_BUCKET_UPLOADS,
        key,
        ExtraArgs={'ContentType': file.content_type},
    )

    if old_key:
        try:
            client.delete_object(
                Bucket=settings.MINIO_BUCKET_UPLOADS, Key=old_key
            )
        except Exception:
            pass

    return key, None
