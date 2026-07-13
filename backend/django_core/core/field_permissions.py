"""NTSEC23 — Permissions au niveau champ (field-level read/write masking).

Fondation GÉNÉRIQUE : ``FieldPermissionRule`` déclare, par (société, modèle,
champ, rôle), un niveau d'accès — ``masque`` (champ retiré de la réponse),
``lecture`` (visible mais non modifiable) ou ``ecriture`` (accès complet). Le
mixin sérialiseur ``FieldPermissionMixin`` applique ces règles selon le rôle de
l'appelant.

Purement ADDITIF : sans règle, AUCUN champ n'est masqué ni verrouillé (la
sérialisation reste STRICTEMENT inchangée). Jamais cross-tenant : une règle n'a
d'effet que dans sa société. ``core`` reste fondation : aucun import d'app métier
(``contenttypes`` + ``authentication`` par référence string uniquement).
"""
from __future__ import annotations

from django.db import models


class FieldPermissionRule(models.Model):
    """Règle d'accès à UN champ d'un modèle pour UN rôle d'une société."""

    class Acces(models.TextChoices):
        MASQUE = 'masque', 'Masqué'
        LECTURE = 'lecture', 'Lecture seule'
        ECRITURE = 'ecriture', 'Écriture'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='field_permission_rules', verbose_name='Société')
    content_type = models.ForeignKey(
        'contenttypes.ContentType', on_delete=models.CASCADE)
    field_name = models.CharField(max_length=100)
    # Rôle ciblé (STRING-FK roles.Role) ; jamais d'import de roles.models ici.
    role_id = models.CharField(max_length=64)
    acces = models.CharField(
        max_length=8, choices=Acces.choices, default=Acces.LECTURE)

    class Meta:
        verbose_name = 'Règle de permission champ'
        verbose_name_plural = 'Règles de permission champ'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'content_type', 'field_name', 'role_id'],
                name='uniq_fieldperm_par_societe_modele_champ_role'),
        ]
        indexes = [
            models.Index(fields=['company', 'content_type', 'role_id'],
                         name='core_fieldperm_comp_role_idx'),
        ]

    def __str__(self):
        return (f'FieldPerm({self.content_type_id}.{self.field_name} '
                f'role={self.role_id}: {self.acces})')


def field_rules_for(user, model):
    """Dict ``{field_name: acces}`` applicable à ``user`` pour ``model``.

    Vide si l'utilisateur n'a pas de rôle, pas de société, ou qu'aucune règle
    n'existe — la sérialisation reste alors inchangée. Company-scopé."""
    if user is None or not getattr(user, 'pk', None):
        return {}
    role_id = getattr(user, 'role_id', None)
    company_id = getattr(user, 'company_id', None)
    if not role_id or not company_id:
        return {}
    try:
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(model)
        rules = FieldPermissionRule.objects.filter(
            company_id=company_id, content_type=ct, role_id=str(role_id))
        return {r.field_name: r.acces for r in rules}
    except Exception:
        return {}


class FieldPermissionMixin:
    """Mixin sérialiseur DRF : masque/verrouille les champs selon le rôle.

    À poser sur un ``ModelSerializer`` : ``masque`` retire le champ de la
    réponse, ``lecture`` empêche son écriture (retiré du ``validated_data``),
    ``ecriture`` (ou absence de règle) = comportement inchangé. Le rôle est lu
    depuis ``context['request'].user`` ; sans requête/utilisateur, no-op.
    """

    def _fp_rules(self):
        request = self.context.get('request') if hasattr(self, 'context') \
            else None
        user = getattr(request, 'user', None) if request else None
        model = getattr(getattr(self, 'Meta', None), 'model', None)
        if user is None or model is None:
            return {}
        # Super-admin : jamais restreint.
        if getattr(user, 'is_superuser', False):
            return {}
        return field_rules_for(user, model)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for field_name, acces in self._fp_rules().items():
            if acces == FieldPermissionRule.Acces.MASQUE:
                data.pop(field_name, None)
        return data

    def to_internal_value(self, data):
        validated = super().to_internal_value(data)
        for field_name, acces in self._fp_rules().items():
            if acces in (FieldPermissionRule.Acces.MASQUE,
                         FieldPermissionRule.Acces.LECTURE):
                # « lecture »/« masque » interdisent l'écriture : on retire le
                # champ du payload validé (jamais persisté par cet appelant).
                validated.pop(field_name, None)
        return validated
