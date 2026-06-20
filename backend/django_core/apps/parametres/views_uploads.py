"""Vues d'upload / suppression du logo et de la signature (images du profil).

Domaine « Société & identité ». Extrait de l'ancien ``views.py`` sans aucun
changement d'endpoint, de validation de format/taille ni de comportement
(mêmes contrôles d'octets magiques, même nettoyage MinIO, même audit)."""
import uuid

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    parser_classes,
)
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier
from apps.ventes.utils.minio_client import ensure_uploads_bucket, get_minio_client
from .models import SettingsAuditLog
from .serializers import CompanyProfileSerializer
from .views_common import _audit_company, _profile


@api_view(['POST'])
@permission_classes([IsAdminOrResponsableTier])
@parser_classes([MultiPartParser])
def upload_logo(request):
    return _upload_image(request, field='logo_key', prefix='logos')


@api_view(['POST'])
@permission_classes([IsAdminOrResponsableTier])
@parser_classes([MultiPartParser])
def upload_signature(request):
    return _upload_image(
        request, field='signature_key', prefix='signatures'
    )


_MAGIC_BYTES = {
    b'\x89PNG\r\n\x1a\n': 'image/png',
    b'\xff\xd8\xff': 'image/jpeg',
    b'RIFF': 'image/webp',  # verifie aussi bytes 8-11 == WEBP ci-dessous
}
_ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def _detect_image_type(header: bytes) -> str | None:
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if header[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'image/webp'
    return None


def _upload_image(request, field, prefix):
    file = request.FILES.get('file')
    if not file:
        return Response(
            {'detail': 'Aucun fichier fourni.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if file.size > 2 * 1024 * 1024:
        return Response(
            {'detail': 'Fichier trop volumineux (max 2 Mo).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    header = file.read(12)
    file.seek(0)
    detected = _detect_image_type(header)
    if detected is None:
        return Response(
            {'detail': 'Format non supporté. Utilisez PNG, JPEG ou WebP.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ext = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''
    if ext not in _ALLOWED_EXTENSIONS:
        ext = detected.split('/')[-1].replace('jpeg', 'jpg')
    key = f"{prefix}/{uuid.uuid4().hex}.{ext}"

    client = get_minio_client()
    ensure_uploads_bucket()  # N108 — self-heal a missing bucket before upload
    client.upload_fileobj(
        file,
        settings.MINIO_BUCKET_UPLOADS,
        key,
        ExtraArgs={'ContentType': file.content_type},
    )

    profile = _profile(request)
    old_key = getattr(profile, field)
    if old_key:
        try:
            client.delete_object(
                Bucket=settings.MINIO_BUCKET_UPLOADS, Key=old_key
            )
        except Exception:
            pass

    setattr(profile, field, key)
    profile.save(update_fields=[field])
    SettingsAuditLog.log_change(
        company=_audit_company(request), user=request.user, section='profil',
        field=field,
        field_label='Logo' if field == 'logo_key' else 'Signature',
        old=old_key or '', new='(image téléversée)',
    )

    return Response(
        CompanyProfileSerializer(profile).data,
        status=status.HTTP_200_OK,
    )


@api_view(['DELETE'])
@permission_classes([IsAdminOrResponsableTier])
def delete_logo(request):
    return _delete_image(request, field='logo_key')


@api_view(['DELETE'])
@permission_classes([IsAdminOrResponsableTier])
def delete_signature(request):
    return _delete_image(request, field='signature_key')


def _delete_image(request, field):
    profile = _profile(request)
    key = getattr(profile, field)
    if key:
        try:
            client = get_minio_client()
            client.delete_object(
                Bucket=settings.MINIO_BUCKET_UPLOADS, Key=key
            )
        except Exception:
            pass
        setattr(profile, field, '')
        profile.save(update_fields=[field])
        SettingsAuditLog.log_change(
            company=_audit_company(request), user=request.user,
            section='profil', field=field,
            field_label='Logo' if field == 'logo_key' else 'Signature',
            old=key, new='(supprimé)',
        )
    return Response(CompanyProfileSerializer(profile).data)
