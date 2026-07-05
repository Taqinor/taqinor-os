"""ZSTK8 — Retour / transfert inverse depuis une Livraison validée (returns).

Odoo génère un « return picking » depuis une livraison ou une réception
validée. Les retours FOURNISSEUR existent (`stock.RetourFournisseur`, N19)
mais rien ne permettait de générer un retour CLIENT depuis une `Livraison`
livrée (matériel refusé/erroné remonté du chantier au dépôt) — il fallait un
ajustement manuel.

``RetourLivraison`` (entête) + ``RetourLivraisonLigne`` (une par SKU, pré-
remplie depuis les lignes livrées, quantité retournée éditable ≤ livrée) :
à la validation, ré-incrémente le stock du dépôt SOURCE de la livraison via
``apps.stock.services.record_stock_movement`` (ENTREE, idempotent).

Additif, multi-tenant (société posée côté serveur)."""
from django.conf import settings
from django.db import models

from .models_livraison import Livraison


class RetourLivraison(models.Model):
    """ZSTK8 — retour client généré depuis une `Livraison` livrée."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDE = 'valide', 'Validé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='retours_livraison')
    livraison = models.ForeignKey(
        Livraison, on_delete=models.CASCADE, related_name='retours')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    motif = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    valide_le = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Retour de livraison'
        verbose_name_plural = 'Retours de livraison'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'livraison'],
                         name='idx_retliv_co_livraison'),
        ]

    def __str__(self):
        return f'Retour · livraison {self.livraison_id} ({self.statut})'


class RetourLivraisonLigne(models.Model):
    """ZSTK8 — ligne d'un retour de livraison : produit + quantité retournée
    (plafonnée ≤ quantité livrée à la création, vérifié au service)."""

    retour = models.ForeignKey(
        RetourLivraison, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    designation = models.CharField(max_length=255, blank=True, null=True)
    quantite_livree = models.PositiveIntegerField(default=0)
    quantite_retournee = models.PositiveIntegerField(default=0)
    # True une fois le mouvement ENTREE posté (idempotence par ligne).
    stock_applique = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Ligne de retour de livraison'
        verbose_name_plural = 'Lignes de retour de livraison'
        ordering = ['retour_id', 'id']
        indexes = [
            models.Index(fields=['retour'], name='idx_retlivl_retour'),
        ]

    def __str__(self):
        return f'{self.designation or self.produit_id} × {self.quantite_retournee}'
