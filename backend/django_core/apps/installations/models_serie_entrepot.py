"""
FG323 — Suivi du stock par numéro de série en entrepôt.

FG61 (`ComponentSerial`) relève le n° de série SUR SITE pendant l'intervention.
FG323 étend cette traçabilité EN AMONT : un registre série→emplacement→casier
AVANT l'installation, pour savoir où se trouve physiquement un onduleur/une
batterie identifié(e) par son n° de série dès la réception. Le statut suit le
cycle entrepôt : en stock → réservé → sorti.

Cross-app : `stock.Produit` / `stock.EmplacementStock` en STRING-FK. `BinLocation`
et `Installation` sont du MÊME app (FK directe). Additif & multi-tenant : FK
`company` posée côté serveur.
"""
from django.conf import settings
from django.db import models


class SerieEntrepot(models.Model):
    """FG323 — n° de série suivi en entrepôt avant installation.

    Multi-tenant : société posée côté serveur. ``numero_serie`` est unique par
    société+produit (un n° de série n'existe qu'une fois). ``bin`` localise la
    pièce ; ``installation`` est renseignée quand la pièce est affectée/sortie
    pour un chantier."""

    class Statut(models.TextChoices):
        EN_STOCK = 'en_stock', 'En stock'
        RESERVE = 'reserve', 'Réservé'
        SORTI = 'sorti', 'Sorti'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_series_entrepot')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='installations_series_entrepot')
    numero_serie = models.CharField(max_length=120)
    emplacement = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_series_entrepot')
    bin = models.ForeignKey(
        'installations.BinLocation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='series_entrepot')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_STOCK)
    installation = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='series_entrepot')
    reference_reception = models.CharField(max_length=80, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_series_entrepot_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'N° de série en entrepôt'
        verbose_name_plural = 'N° de série en entrepôt'
        ordering = ['-date_creation']
        unique_together = [('company', 'produit', 'numero_serie')]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_serieent_co_statut'),
            models.Index(fields=['company', 'produit'],
                         name='idx_serieent_co_produit'),
        ]

    def __str__(self):
        return f'{self.numero_serie} ({self.statut})'
