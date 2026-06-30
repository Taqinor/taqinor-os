"""
FG322 — Colisage / préparation (pack).

Après le prélèvement (FG321), les articles sont EMBALLÉS et CONTRÔLÉS avant le
départ vers le site : un colis (`Colis`) regroupe des lignes (`ColisLigne`)
liées au chantier, avec une étape de contrôle (qui / quand) qui passe le colis
en CONTRÔLÉ puis EXPÉDIÉ. Trace purement organisationnelle : ne décrémente pas
le stock (la consommation reste pilotée par la réservation N14).

Cross-app : `stock.Produit` en STRING-FK. `Installation` est du MÊME app (FK
directe). Additif & multi-tenant : FK `company` posée côté serveur.
"""
from django.conf import settings
from django.db import models


class Colis(models.Model):
    """FG322 — colis de préparation d'un chantier. Référence ``COL-YYYYMM-NNNN``
    anti-collision. Statut : préparation → contrôlé → expédié."""

    class Statut(models.TextChoices):
        PREPARATION = 'preparation', 'En préparation'
        CONTROLE = 'controle', 'Contrôlé'
        EXPEDIE = 'expedie', 'Expédié'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_colis')
    reference = models.CharField(max_length=50)
    installation = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='colis')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.PREPARATION)
    poids_kg = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    controle_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations_colis_controles')
    date_controle = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_colis_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Colis de préparation'
        verbose_name_plural = 'Colis de préparation'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_colis_co_statut'),
            models.Index(fields=['company', 'installation'],
                         name='idx_colis_co_install'),
        ]

    def __str__(self):
        return f'{self.reference} ({self.statut})'


class ColisLigne(models.Model):
    """FG322 — article emballé dans un colis (SKU + quantité + contrôle OK)."""

    colis = models.ForeignKey(
        Colis, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_colis_lignes')
    designation = models.CharField(max_length=255, blank=True, null=True)
    quantite = models.PositiveIntegerField(default=0)
    controle_ok = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Ligne de colis'
        verbose_name_plural = 'Lignes de colis'
        ordering = ['colis_id', 'id']
        indexes = [
            models.Index(fields=['colis'], name='idx_colisl_colis'),
            models.Index(fields=['produit'], name='idx_colisl_produit'),
        ]

    def __str__(self):
        return f'{self.designation or self.produit_id} × {self.quantite}'
