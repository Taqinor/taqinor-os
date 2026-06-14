"""Activités planifiées (style Odoo) et pièces jointes — génériques.

Les deux modèles se rattachent à N'IMPORTE quel enregistrement métier via
contenttypes (Lead, Client, Chantier, Ticket SAV…), sans coupler les apps.
Tout est company-stampé côté serveur et filtré par société, comme le reste.

ALLOWED_TARGETS borne explicitement les modèles que l'on peut cibler : on ne
laisse jamais le navigateur attacher une activité/un fichier à un modèle
arbitraire.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

# (app_label, model) autorisés comme cibles d'activité / pièce jointe.
ALLOWED_TARGETS = {
    ('crm', 'lead'),
    ('crm', 'client'),
    ('installations', 'installation'),
    ('sav', 'ticket'),
}


class ActivityType(models.Model):
    """Type d'activité configurable (Appel, Email, Réunion, Relance, À faire)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='activity_types')
    nom = models.CharField(max_length=80)
    icone = models.CharField(max_length=8, blank=True, default='')
    ordre = models.PositiveIntegerField(default=0)
    # Décalage par défaut (jours) proposé quand on planifie la suite.
    delai_defaut_jours = models.PositiveIntegerField(default=0)
    est_systeme = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = "Type d'activité"

    def __str__(self):
        return self.nom


class Activity(models.Model):
    """Activité planifiée rattachée à un enregistrement (générique)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='activities')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    activity_type = models.ForeignKey(
        ActivityType, on_delete=models.PROTECT, related_name='activities')
    summary = models.CharField(max_length=255, blank=True, default='')
    note = models.TextField(blank=True, default='')
    due_date = models.DateField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='activities_assignees')

    done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    done_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='activities_faites')

    # Marqueur pour l'activité « Relance » auto-gérée depuis Lead.relance_date :
    # une seule activité de ce genre par lead, synchronisée, jamais dupliquée.
    auto_relance = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='activities_creees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['done', 'due_date', 'id']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['assigned_to', 'done']),
        ]
        verbose_name = 'Activité'

    def __str__(self):
        return f'{self.activity_type} — {self.summary or self.due_date}'


class Attachment(models.Model):
    """Pièce jointe rattachée à un enregistrement (générique), stockée MinIO."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='attachments')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Clé objet MinIO (bucket erp-uploads) — le fichier ne quitte jamais le
    # stockage objet ; rien n'est commité dans le dépôt.
    file_key = models.CharField(max_length=500)
    filename = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    mime = models.CharField(max_length=120, blank=True, default='')

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='attachments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', 'id']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
        verbose_name = 'Pièce jointe'

    def __str__(self):
        return self.filename
