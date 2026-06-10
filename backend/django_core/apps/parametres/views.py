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
from authentication.permissions import IsAdminRole, IsAnyRole
from apps.ventes.utils.minio_client import get_minio_client
from .models import CompanyProfile
from .serializers import CompanyProfileSerializer


def _profile(request):
    """Return the CompanyProfile for the current user's company."""
    return CompanyProfile.get(
        company=request.user.company if request.user.company_id else None
    )


@api_view(['GET'])
@permission_classes([IsAnyRole])
def get_profile(request):
    profile = _profile(request)
    return Response(CompanyProfileSerializer(profile).data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAdminRole])
def update_profile(request):
    profile = _profile(request)
    partial = request.method == 'PATCH'
    serializer = CompanyProfileSerializer(
        profile, data=request.data, partial=partial
    )
    serializer.is_valid(raise_exception=True)
    updated = serializer.save()
    return Response(CompanyProfileSerializer(updated).data)


@api_view(['POST'])
@permission_classes([IsAdminRole])
@parser_classes([MultiPartParser])
def upload_logo(request):
    return _upload_image(request, field='logo_key', prefix='logos')


@api_view(['POST'])
@permission_classes([IsAdminRole])
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

    return Response(
        CompanyProfileSerializer(profile).data,
        status=status.HTTP_200_OK,
    )


@api_view(['DELETE'])
@permission_classes([IsAdminRole])
def delete_logo(request):
    return _delete_image(request, field='logo_key')


@api_view(['DELETE'])
@permission_classes([IsAdminRole])
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
    return Response(CompanyProfileSerializer(profile).data)
