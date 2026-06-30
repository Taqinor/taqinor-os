"""
FG329 — Planification des livraisons (dépôt → site).

Un objet `Livraison` planifie l'acheminement du matériel d'un dépôt
(`stock.EmplacementStock`) vers le SITE d'un chantier (`Installation`) à une date
donnée, avec un transporteur et la liste des articles. C'est l'objet de
PLANIFICATION/SUIVI ; il est DISTINCT du PDF « bon de livraison » (document) qui
peut en être tiré.

Cross-app : `stock.Produit` / `stock.EmplacementStock` en STRING-FK ;
`Installation` est du MÊME app (FK directe). Additif & multi-tenant : FK
`company` posée côté serveur. Couche de planification — ne décrémente pas le
stock (réservation/sortie pilotées ailleurs).
"""
from django.conf import settings
from django.db import models


class Livraison(models.Model):
    """FG329 — livraison planifiée dépôt → site. Référence ``LIV-YYYYMM-NNNN``
    anti-collision. Cycle : planifiée → en transit → livrée (ou annulée)."""

    class Statut(models.TextChoices):
        PLANIFIEE = 'planifiee', 'Planifiée'
        EN_TRANSIT = 'en_transit', 'En transit'
        LIVREE = 'livree', 'Livrée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_livraisons')
    reference = models.CharField(max_length=50)
    installation = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='livraisons')
    depot = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_livraisons')
    transporteur_nom = models.CharField(max_length=255, blank=True, null=True)
    date_prevue = models.DateField(null=True, blank=True)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.PLANIFIEE)
    adresse_site = models.TextField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_livraisons_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Livraison planifiée'
        verbose_name_plural = 'Livraisons planifiées'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_liv_co_statut'),
            models.Index(fields=['company', 'date_prevue'],
                         name='idx_liv_co_date'),
        ]

    def __str__(self):
        return f'{self.reference} ({self.statut})'


class LivraisonLigne(models.Model):
    """FG329 — article d'une livraison (SKU + quantité)."""

    livraison = models.ForeignKey(
        Livraison, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_livraison_lignes')
    designation = models.CharField(max_length=255, blank=True, null=True)
    quantite = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Ligne de livraison'
        verbose_name_plural = 'Lignes de livraison'
        ordering = ['livraison_id', 'id']
        indexes = [
            models.Index(fields=['livraison'], name='idx_livl_livraison'),
            models.Index(fields=['produit'], name='idx_livl_produit'),
        ]

    def __str__(self):
        return f'{self.designation or self.produit_id} × {self.quantite}'
