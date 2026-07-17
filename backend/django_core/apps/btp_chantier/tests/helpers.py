"""Aides de test partagées du vertical BTP/EPC (Groupe NTCON)."""
import itertools

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'ntcon-co-{n}', defaults={'nom': nom or f'NTCON Co {n}'})
    return company


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'ntcon-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_chantier(company, **kwargs):
    from apps.installations.models import Installation
    n = next(_seq)
    kwargs.setdefault('reference', f'CH-{company.id}-{n}')
    return Installation.objects.create(company=company, **kwargs)


def attach(company, user, instance, phase, name='photo.png'):
    """Crée un ``records.Attachment`` ciblant ``instance`` (générique)."""
    from apps.records.models import Attachment
    ct = ContentType.objects.get_for_model(instance.__class__)
    return Attachment.objects.create(
        company=company, content_type=ct, object_id=instance.id,
        uploaded_by=user, phase=phase,
        file_key=f'attachments/{name}', filename=name,
        size=1, mime='image/png')
