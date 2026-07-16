"""Stockage des pièces jointes dans MinIO (boto3) — mêmes mécanismes que les
avatars/logos (authentication/avatars.py, parametres). Aucune dépendance
nouvelle. On accepte PDF + images courantes ; pas de traitement d'image (donc
pas besoin d'un nouveau package) — on stocke le fichier tel quel."""
import io
import os
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


def _company_id(company):
    """Identifiant de société pour le préfixe de clé, ou None.

    Accepte une instance ``Company`` (on lit ``.id``) ou un entier directement.
    None/0 → pas de préfixe (repli sur l'ancien chemin, cf. ``store_attachment``)."""
    if company is None:
        return None
    cid = getattr(company, 'id', company)
    return cid or None


def store_attachment(file, *, audio=False, company=None):
    """Valide + téléverse un fichier. Retourne (dict, None) ou (None, message).

    dict = {file_key, filename, size, mime}.

    `audio=True` (F13 — mémos vocaux) accepte les formats audio courants au lieu
    des documents/images : même pipeline MinIO, même limite de taille.

    SCA42 — isolation par société des clés de stockage : quand ``company`` est
    fourni, la clé du NOUVEL objet est préfixée par la société
    (``attachments/{company_id}/{uuid}.ext``) — motif ERR75 généralisé
    (``ventes/utils/pdf.py`` : ``devis/{company_id}/…``). Sans ``company`` (appel
    historique), on retombe sur l'ancien chemin plat ``attachments/{uuid}.ext``
    (rétro-compatible). Les objets DÉJÀ stockés ne bougent pas : la lecture
    utilise la clé STOCKÉE (``fetch_attachment``/``presign_attachment``), donc
    les anciens fichiers restent servis quelle que soit la forme de la clé.
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

    cid = _company_id(company)
    if cid is not None:
        key = f'attachments/{cid}/{uuid.uuid4().hex}.{ext}'
    else:
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


# --- NTPLT30 — Exports lourds asynchrones (brique de stockage) --------------
# Au-delà d'un seuil de lignes (env ``NTPLT30_EXPORT_ROW_THRESHOLD``, défaut
# 5 000), un export doit basculer en ``BackgroundJob`` (``core.jobs.submit``,
# NTPLT29) : réponse 202 + job id, génération en queue ``bulk``, livrable déposé
# ICI dans MinIO, puis notification « votre export est prêt » avec une URL
# présignée courte durée. SOUS le seuil, l'export reste synchrone (comportement
# inchangé). Ce module fournit la DÉCISION + le STOCKAGE/PRÉSIGNÉ du livrable ;
# le déclenchement 202 et la notification vivent côté vue/tâche qui adopte ce
# helper (adoption incrémentale, comme les autres primitives NTPLT).

DEFAULT_EXPORT_ROW_THRESHOLD = 5000


def export_row_threshold():
    """Seuil de lignes au-delà duquel un export bascule en asynchrone.

    Piloté par ``NTPLT30_EXPORT_ROW_THRESHOLD`` (défaut 5 000). Une valeur
    ``<= 0`` désactive le basculement (exports toujours synchrones — off-switch,
    convention 0=off des primitives NTPLT). Une valeur illisible retombe sur le
    défaut."""
    raw = os.environ.get('NTPLT30_EXPORT_ROW_THRESHOLD')
    if raw is None or raw == '':
        return DEFAULT_EXPORT_ROW_THRESHOLD
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_EXPORT_ROW_THRESHOLD


def should_async_export(row_count, threshold=None):
    """Vrai si l'export de ``row_count`` lignes doit basculer en asynchrone.

    ``threshold`` ``None`` → ``export_row_threshold()`` ; un seuil ``<= 0``
    signifie « jamais asynchrone » (feature off)."""
    if threshold is None:
        threshold = export_row_threshold()
    try:
        threshold = int(threshold)
        row_count = int(row_count)
    except (TypeError, ValueError):
        return False
    if threshold <= 0:
        return False
    return row_count > threshold


def export_result_key(company_id, job_id, *, ext='xlsx'):
    """Clé MinIO du livrable d'export d'un job, isolée par société.

    ``exports/{company_id}/{job_id}.{ext}`` — même motif d'isolation par société
    que ``store_attachment`` (SCA42). ``company_id`` accepte une instance
    ``Company`` ou un entier."""
    cid = _company_id(company_id) or 0
    safe_ext = (ext or 'bin').lstrip('.') or 'bin'
    return f'exports/{cid}/{job_id}.{safe_ext}'


def store_export_result(data, *, company_id, job_id, ext='xlsx',
                        content_type=None):
    """Dépose les octets du livrable d'export dans MinIO et renvoie la clé.

    Réutilise le bucket uploads + le client MinIO existants (aucune dépendance
    nouvelle). ``data`` = octets (``bytes``) OU objet fichier lisible. Renvoie
    la clé stockée (à poser dans ``BackgroundJob.result_file_key``)."""
    key = export_result_key(company_id, job_id, ext=ext)
    client = get_minio_client()
    ensure_uploads_bucket()  # self-heal du bucket, comme store_attachment
    buf = data if hasattr(data, 'read') else io.BytesIO(data)
    extra = {'ContentType': content_type} if content_type else {}
    client.upload_fileobj(
        buf, settings.MINIO_BUCKET_UPLOADS, key, ExtraArgs=extra)
    return key


def presign_export_result(key, *, expires=900):
    """URL présignée COURTE durée (défaut 15 min) du livrable d'export, ou None.

    Le job vient de se terminer : une URL de courte durée suffit pour la
    notification bell « votre export est prêt ». Comme ``presign_attachment``,
    l'URL pointe l'hôte MinIO (usage serveur / notification signée)."""
    if not key:
        return None
    try:
        client = get_minio_client()
        return client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.MINIO_BUCKET_UPLOADS, 'Key': key},
            ExpiresIn=int(expires))
    except Exception:
        return None
