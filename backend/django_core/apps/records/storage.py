"""Stockage des pièces jointes dans MinIO (boto3) — mêmes mécanismes que les
avatars/logos (authentication/avatars.py, parametres). Aucune dépendance
nouvelle. On accepte PDF + images courantes ; pas de traitement d'image (donc
pas besoin d'un nouveau package) — on stocke le fichier tel quel."""
import uuid

from django.conf import settings

from apps.ventes.utils.minio_client import get_minio_client

_MAX_BYTES = 10 * 1024 * 1024  # 10 Mo par fichier

# Octets magiques → mime, pour refuser les binaires non désirés.
_ALLOWED = {
    'application/pdf': ('pdf', lambda h: h[:5] == b'%PDF-'),
    'image/png': ('png', lambda h: h[:8] == b'\x89PNG\r\n\x1a\n'),
    'image/jpeg': ('jpg', lambda h: h[:3] == b'\xff\xd8\xff'),
    'image/webp': ('webp', lambda h: h[:4] == b'RIFF' and h[8:12] == b'WEBP'),
}


def _detect(header: bytes):
    for mime, (ext, test) in _ALLOWED.items():
        if test(header):
            return mime, ext
    return None, None


def store_attachment(file):
    """Valide + téléverse un fichier. Retourne (dict, None) ou (None, message).

    dict = {file_key, filename, size, mime}.
    """
    if file.size > _MAX_BYTES:
        return None, 'Fichier trop volumineux (max 10 Mo).'

    header = file.read(12)
    file.seek(0)
    mime, ext = _detect(header)
    if mime is None:
        return None, 'Format non supporté (PDF, PNG, JPEG ou WebP uniquement).'

    key = f'attachments/{uuid.uuid4().hex}.{ext}'
    client = get_minio_client()
    client.upload_fileobj(
        file, settings.MINIO_BUCKET_UPLOADS, key,
        ExtraArgs={'ContentType': mime})

    raw_name = (getattr(file, 'name', '') or f'fichier.{ext}')
    return {
        'file_key': key,
        'filename': raw_name[:255],
        'size': file.size,
        'mime': mime,
    }, None


def presign_attachment(key):
    """URL présignée (1 h) de téléchargement, ou None."""
    if not key:
        return None
    try:
        client = get_minio_client()
        return client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.MINIO_BUCKET_UPLOADS, 'Key': key},
            ExpiresIn=3600)
    except Exception:
        return None


def delete_attachment(key):
    if not key:
        return
    try:
        client = get_minio_client()
        client.delete_object(Bucket=settings.MINIO_BUCKET_UPLOADS, Key=key)
    except Exception:
        pass
