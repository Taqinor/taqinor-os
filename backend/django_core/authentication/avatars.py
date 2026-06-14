"""Photos de profil employé — stockage MinIO via boto3.

Même mécanisme que les logos/signatures d'entreprise (apps.parametres.views) :
clé objet stockée en base, fichier dans le bucket erp-uploads, validation par
octets magiques. Aucune dépendance nouvelle (boto3 déjà présent ; Pillow déjà
fourni par WeasyPrint si une vérification d'image plus poussée devenait utile).
"""
import uuid

from django.conf import settings

from apps.ventes.utils.minio_client import get_minio_client

_ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
_MAX_BYTES = 2 * 1024 * 1024


def _detect_image_type(header: bytes):
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if header[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'image/webp'
    return None


def presign_avatar(key):
    """URL présignée (1 h) de lecture d'une photo, ou None si pas de clé."""
    if not key:
        return None
    try:
        client = get_minio_client()
        return client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.MINIO_BUCKET_UPLOADS, 'Key': key},
            ExpiresIn=3600,
        )
    except Exception:
        return None


def store_avatar(file, old_key=''):
    """Valide + téléverse une photo, supprime l'ancienne.

    Retourne (key, None) en cas de succès, (None, message) en cas d'erreur.
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
    key = f"avatars/{uuid.uuid4().hex}.{ext}"

    client = get_minio_client()
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
