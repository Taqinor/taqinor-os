"""NTSEC21 — Partage au niveau enregistrement (record-level sharing).

Fondation GÉNÉRIQUE : un ``SharingRule`` élargit la visibilité d'UN objet
métier (via ``contenttypes``) à un principal (utilisateur / rôle / équipe)
au-delà du propriétaire, en LECTURE ou en ÉCRITURE, avec expiration optionnelle.

Purement ADDITIF : sans règle, ``visible_ids`` renvoie un ensemble vide et la
visibilité historique (propriétaire/superviseur) reste STRICTEMENT inchangée —
un viewset compose ``visible_ids`` avec son filtrage société existant (``OR``)
pour n'AJOUTER que des accès, jamais en retirer. Jamais cross-tenant : une règle
n'a d'effet que dans la société qui l'a créée. ``core`` reste fondation : aucun
import d'app métier (seulement ``authentication`` + ``contenttypes``).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class SharingRule(models.Model):
    """Règle de partage d'UN enregistrement vers un principal."""

    class PrincipalType(models.TextChoices):
        USER = 'user', 'Utilisateur'
        ROLE = 'role', 'Rôle'
        TEAM = 'team', 'Équipe'

    class Niveau(models.TextChoices):
        LECTURE = 'lecture', 'Lecture'
        ECRITURE = 'ecriture', 'Écriture'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='sharing_rules', verbose_name='Société')
    content_type = models.ForeignKey(
        'contenttypes.ContentType', on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64)
    principal_type = models.CharField(
        max_length=8, choices=PrincipalType.choices)
    principal_id = models.CharField(max_length=64)
    niveau = models.CharField(
        max_length=8, choices=Niveau.choices, default=Niveau.LECTURE)
    expire_le = models.DateTimeField(null=True, blank=True)
    accorde_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='sharing_rules_accordees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Règle de partage'
        verbose_name_plural = 'Règles de partage'
        indexes = [
            models.Index(fields=['company', 'content_type', 'object_id'],
                         name='core_sharin_company_ct_obj_idx'),
            models.Index(fields=['principal_type', 'principal_id'],
                         name='core_sharin_principal_idx'),
        ]

    def __str__(self):
        return (f'Share({self.content_type_id}:{self.object_id} → '
                f'{self.principal_type}:{self.principal_id}, {self.niveau})')

    @property
    def est_expiree(self):
        return self.expire_le is not None and self.expire_le <= timezone.now()


def _principals_for(user):
    """Paires (principal_type, principal_id) auxquelles ``user`` appartient."""
    pairs = [('user', str(user.pk))]
    role_id = getattr(user, 'role_id', None)
    if role_id:
        pairs.append(('role', str(role_id)))
    return pairs


def _rules_qs(user, model, *, write=False):
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Q

    company_id = getattr(user, 'company_id', None)
    if not company_id:
        return SharingRule.objects.none()
    ct = ContentType.objects.get_for_model(model)
    now = timezone.now()
    principal_q = Q()
    for ptype, pid in _principals_for(user):
        principal_q |= Q(principal_type=ptype, principal_id=pid)
    qs = SharingRule.objects.filter(
        principal_q, company_id=company_id, content_type=ct,
    ).filter(Q(expire_le__isnull=True) | Q(expire_le__gt=now))
    if write:
        qs = qs.filter(niveau=SharingRule.Niveau.ECRITURE)
    return qs


def visible_ids(user, model, *, write=False):
    """Ids des ``model`` PARTAGÉS à ``user`` (au-delà de sa visibilité de base).

    ``write=True`` restreint aux partages en écriture. Company-scopé, expiration
    respectée. Renvoie un ``set`` d'object_ids (chaînes). VIDE si aucune règle :
    le viewvset composant ne gagne alors AUCUNE visibilité supplémentaire.
    """
    if user is None or not getattr(user, 'pk', None):
        return set()
    try:
        return set(
            _rules_qs(user, model, write=write)
            .values_list('object_id', flat=True))
    except Exception:
        return set()


def can_write(user, instance):
    """Vrai si ``user`` a un partage en ÉCRITURE non expiré sur ``instance``."""
    if user is None or instance is None:
        return False
    try:
        return str(instance.pk) in visible_ids(
            user, instance.__class__, write=True)
    except Exception:
        return False


def share_object(instance, *, principal_type, principal_id, niveau='lecture',
                 expire_le=None, accorde_par=None):
    """Crée (ou met à jour) une règle de partage pour ``instance``.

    Company dérivée de l'instance (jamais du corps de requête). Idempotent sur
    (company, content_type, object_id, principal)."""
    from django.contrib.contenttypes.models import ContentType

    company_id = getattr(instance, 'company_id', None)
    ct = ContentType.objects.get_for_model(instance.__class__)
    rule, _ = SharingRule.objects.update_or_create(
        company_id=company_id,
        content_type=ct, object_id=str(instance.pk),
        principal_type=principal_type, principal_id=str(principal_id),
        defaults={'niveau': niveau, 'expire_le': expire_le,
                  'accorde_par': accorde_par},
    )
    return rule
