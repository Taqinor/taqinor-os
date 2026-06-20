"""Stockage des pièces jointes dans MinIO (boto3) — mêmes mécanismes que les
avatars/logos (authentication/avatars.py, parametres). Aucune dépendance
nouvelle. On accepte PDF + images courantes ; pas de traitement d'image (donc
pas besoin d'un nouveau package) — on stocke le fichier tel quel."""
import uuid

from django.conf import settings

from apps.ventes.utils.minio_client import ensure_uploads_bucket, get_minio_client

_MAX_BYTES = 10 * 1024 * 1024  # 10 Mo par fichier

# Octets magiques → mime, pour refuser les binaires non désirés.
_ALLOWED = {
    'application/pdf': ('pdf', lambda h: h[:5] == b'%PDF-'),
    'image/png': ('png', lambda h: h[:8] == b'\x89PNG\r\n\x1a\n'),
    'image/jpeg': ('jpg', lambda h: h[:3] == b'\xff\xd8\xff'),
    'image/webp': ('webp', lambda h: h[:4] == b'RIFF' and h[8:12] == b'WEBP'),
}

# F13 — mémos vocaux : formats audio enregistrés par le navigateur sur le
# terrain (WebM/Opus, Ogg, MP4/AAC, WAV, MP3). Stockés tels quels via le même
# pipeline MinIO — aucune nouvelle dépendance, aucun traitement audio.
_ALLOWED_AUDIO = {
    'audio/webm': ('webm', lambda h: h[:4] == b'\x1aE\xdf\xa3'),
    'audio/ogg': ('ogg', lambda h: h[:4] == b'OggS'),
    'audio/mp4': ('m4a', lambda h: h[4:8] == b'ftyp'),
    'audio/wav': ('wav', lambda h: h[:4] == b'RIFF' and h[8:12] == b'WAVE'),
    'audio/mpeg': ('mp3', lambda h: h[:3] == b'ID3' or h[:2] == b'\xff\xfb'),
}


def _detect(header: bytes, table=None):
    for mime, (ext, test) in (table or _ALLOWED).items():
        if test(header):
            return mime, ext
    return None, None


def store_attachment(file, *, audio=False):
    """Valide + téléverse un fichier. Retourne (dict, None) ou (None, message).

    dict = {file_key, filename, size, mime}.

    `audio=True` (F13 — mémos vocaux) accepte les formats audio courants au lieu
    des documents/images : même pipeline MinIO, même limite de taille.
    """
    if file.size > _MAX_BYTES:
        return None, 'Fichier trop volumineux (max 10 Mo).'

    header = file.read(12)
    file.seek(0)
    table = _ALLOWED_AUDIO if audio else _ALLOWED
    mime, ext = _detect(header, table)
    if mime is None:
        if audio:
            return None, ('Format audio non supporté '
                          '(WebM, Ogg, MP4/M4A, WAV ou MP3 uniquement).')
        return None, 'Format non supporté (PDF, PNG, JPEG ou WebP uniquement).'

    key = f'attachments/{uuid.uuid4().hex}.{ext}'
    client = get_minio_client()
    ensure_uploads_bucket()  # N108 — self-heal a missing bucket before upload
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


def fetch_attachment(key):
    """Récupère les octets de l'objet stocké. (data, None) ou (None, message).

    B1 — sert de source au proxy de téléchargement Django (même origine) : le
    navigateur ne peut pas joindre l'hôte INTERNE d'une URL présignée MinIO, on
    relaie donc le contenu via Django.
    """
    if not key:
        return None, 'Fichier introuvable.'
    try:
        client = get_minio_client()
        obj = client.get_object(Bucket=settings.MINIO_BUCKET_UPLOADS, Key=key)
        return obj['Body'].read(), None
    except Exception:
        return None, 'Fichier introuvable.'


def presign_attachment(key):
    """URL présignée (1 h) de téléchargement, ou None.

    NOTE : pointe vers l'hôte INTERNE MinIO — injoignable depuis le navigateur.
    Conservé pour un usage interne/serveur uniquement ; les clients passent par
    le proxy Django (voir fetch_attachment + AttachmentViewSet.download)."""
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
