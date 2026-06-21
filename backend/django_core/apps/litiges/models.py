"""Modèles des Réclamations & litiges (module `apps.litiges`).

Registre des réclamations clients et litiges (financier, qualité, délai…),
rattachables à un document source (facture/lead/chantier/ticket) par une
référence souple (type + id) — jamais un import cross-app de modèle.
Multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Entièrement additif.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models


class Reclamation(models.Model):
    """Réclamation ou litige d'une société."""
    class TypeReclamation(models.TextChoices):
        FINANCIER = 'financier', 'Financier'
        QUALITE = 'qualite', 'Qualité'
        DELAI = 'delai', 'Délai'
        COMMERCIAL = 'commercial', 'Commercial'
        AUTRE = 'autre', 'Autre'

    class Gravite(models.TextChoices):
        FAIBLE = 'faible', 'Faible'
        MOYENNE = 'moyenne', 'Moyenne'
        ELEVEE = 'elevee', 'Élevée'

    class Statut(models.TextChoices):
        OUVERTE = 'ouverte', 'Ouverte'
        EN_TRAITEMENT = 'en_traitement', 'En traitement'
        RESOLUE = 'resolue', 'Résolue'
        REJETEE = 'rejetee', 'Rejetée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='litiges_reclamations',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    type_reclamation = models.CharField(
        max_length=20, choices=TypeReclamation.choices,
        default=TypeReclamation.AUTRE, verbose_name='Type de réclamation')
    gravite = models.CharField(
        max_length=10, choices=Gravite.choices,
        default=Gravite.MOYENNE, verbose_name='Gravité')
    objet = models.CharField(max_length=255, verbose_name='Objet')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    # Origine documentaire (facture/lead/chantier/ticket) — string FK souple
    # pour ne jamais importer les modèles d'une autre app.
    source_type = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='Type de document source')
    source_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du document source')
    montant_conteste = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant contesté')
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.OUVERTE, verbose_name='Statut')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reclamations_creees',
        verbose_name='Créée par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Réclamation'
        verbose_name_plural = 'Réclamations'
        ordering = ['-id']

    def __str__(self):
        return self.objet
