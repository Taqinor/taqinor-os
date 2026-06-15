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
from .models import (
    CompanyProfile, MessageTemplate, MESSAGE_TEMPLATE_DEFAULTS,
)
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
        profile, data=request.data, partial=partial,
        context={'request': request},
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


# ── Modèles de message WhatsApp (Paramètres → Messages) ──────────────────────

# Placeholders proposés par clé (aide à la saisie côté UI).
_MESSAGE_PLACEHOLDERS = {
    'devis_unique': ['{civilite}', '{nom}', '{reference}', '{lien}'],
    'devis_multi_entete': ['{civilite}', '{nom}', '{n}'],
    'devis_multi_ligne': ['{reference}', '{lien}'],
    'facture': ['{civilite}', '{nom}', '{reference}', '{lien}'],
    'relance': ['{civilite}', '{nom}', '{reference}', '{lien}'],
}


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAnyRole])
def messages_endpoint(request):
    """GET : lecture (tout rôle). PUT/PATCH : enregistrement (admin only)."""
    if request.method == 'GET':
        return _messages_list(request)
    if not IsAdminRole().has_permission(request, None):
        return Response(
            {'detail': "Réservé à l'administrateur."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return _messages_save(request)


def _messages_list(request):
    """Tous les modèles de message (FR + Darija), défaut si non personnalisé."""
    company = request.user.company if request.user.company_id else None
    rows = {
        r.cle: r for r in MessageTemplate.objects.filter(company=company)
    } if company else {}
    out = []
    for cle, label in MessageTemplate.Cle.choices:
        row = rows.get(cle)
        default = MESSAGE_TEMPLATE_DEFAULTS.get(cle, '')
        out.append({
            'cle': cle,
            'label': label,
            'corps_fr': (row.corps_fr if row and row.corps_fr else default),
            'corps_darija': (row.corps_darija if row else ''),
            'default_fr': default,
            'placeholders': _MESSAGE_PLACEHOLDERS.get(cle, []),
        })
    return Response(out)


def _messages_save(request):
    """Enregistre un modèle de message pour la société (upsert par clé)."""
    company = request.user.company if request.user.company_id else None
    if company is None:
        return Response(
            {'detail': 'Société requise.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    cle = request.data.get('cle')
    valid = {c for c, _ in MessageTemplate.Cle.choices}
    if cle not in valid:
        return Response(
            {'detail': 'Clé de message inconnue.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    obj, _ = MessageTemplate.objects.get_or_create(company=company, cle=cle)
    if 'corps_fr' in request.data:
        obj.corps_fr = request.data.get('corps_fr') or ''
    if 'corps_darija' in request.data:
        obj.corps_darija = request.data.get('corps_darija') or ''
    obj.save()
    return Response({
        'cle': obj.cle, 'corps_fr': obj.corps_fr,
        'corps_darija': obj.corps_darija,
    })


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
