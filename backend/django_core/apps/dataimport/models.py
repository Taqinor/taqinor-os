"""XPLT1 — rapprochement générique par identifiant externe pour l'import T9.

``ExternalRef`` mémorise le lien (company, external_system, external_id) →
objet TAQINOR (via ContentType/object_id), pour TOUTE cible d'import
(leads/clients/produits/fournisseurs/équipements/véhicules), contrairement au
couple ``external_system``/``external_id`` posé directement sur ``crm.Lead``
(N107, import Odoo one-shot) qui ne couvre que les leads. Un ré-import du même
fichier en mode ``maj``/``upsert`` retrouve l'enregistrement déjà créé via
cette table plutôt que d'en créer un second.
"""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class ExternalRef(models.Model):
    """Lien technique stable entre un système externe et un objet TAQINOR."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='dataimport_external_refs')
    external_system = models.CharField(max_length=50)
    external_id = models.CharField(max_length=150)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'external_system', 'external_id'],
                name='uniq_dataimport_external_ref'),
        ]
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f'{self.external_system}:{self.external_id} -> {self.content_type.model}:{self.object_id}'


class ImportMapping(models.Model):
    """XPLT2 — mapping colonne→champ sauvegardé, proposé au dry-run suivant."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='dataimport_mappings')
    nom = models.CharField(max_length=150)
    entity = models.CharField(max_length=50)
    mapping = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'entity', 'nom'],
                name='uniq_dataimport_mapping_nom'),
        ]
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.entity}:{self.nom}'


class ImportJob(models.Model):
    """XPLT2 — journal d'un commit d'import (une ligne par commit)."""

    class Statut(models.TextChoices):
        OK = 'ok', 'Terminé'
        PARTIEL = 'partiel', 'Terminé avec erreurs'
        ECHEC = 'echec', 'Échoué (rollback)'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='dataimport_jobs')
    target = models.CharField(max_length=50)
    fichier_nom = models.CharField(max_length=255, blank=True, null=True)
    mode = models.CharField(max_length=20, default='creer')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.OK)
    total_lignes = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='dataimport_jobs')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'target']),
        ]

    def __str__(self):
        return f'Import {self.target} #{self.pk} ({self.statut})'


class ImportJobRow(models.Model):
    """XPLT2 — statut ligne à ligne d'un ``ImportJob`` (échecs ré-exploitables)."""

    class Statut(models.TextChoices):
        OK = 'ok', 'Importée'
        ERREUR = 'erreur', 'Erreur'

    job = models.ForeignKey(
        ImportJob, on_delete=models.CASCADE, related_name='rows')
    ligne = models.PositiveIntegerField()
    statut = models.CharField(max_length=10, choices=Statut.choices)
    motif = models.CharField(max_length=255, blank=True, null=True)
    # Contenu brut de la ligne (utile pour régénérer un CSV de ré-import).
    donnees = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['ligne']
        indexes = [
            models.Index(fields=['job', 'statut']),
        ]

    def __str__(self):
        return f'Job {self.job_id} ligne {self.ligne} ({self.statut})'
