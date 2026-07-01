"""
FG327 — Stock en consignation / emballages consignés.

Certain matériel n'est PAS possédé : palettes, tourets de câble, bouteilles,
matériel prêté par un fournisseur. Il est RETOURNABLE et souvent assorti d'une
caution. FG327 trace ce stock consigné : désignation, fournisseur, quantité
détenue, caution unitaire, statut (détenu → retourné), avec la trace du retour.

Cross-app : `stock.Fournisseur` en STRING-FK uniquement. Montant de caution
INTERNE. Additif & multi-tenant : FK `company` posée côté serveur. Ne fait PAS
partie du stock vendable canonique (matériel non possédé).
"""
from django.conf import settings
from django.db import models


class MaterielConsigne(models.Model):
    """FG327 — lot de matériel consigné retournable (non possédé).

    Multi-tenant : société posée côté serveur. ``caution_unitaire`` est le
    montant consigné par unité (INTERNE). ``retourner`` solde le lot et horodate
    le retour."""

    class TypeMateriel(models.TextChoices):
        PALETTE = 'palette', 'Palette'
        TOURET = 'touret', 'Touret de câble'
        BOUTEILLE = 'bouteille', 'Bouteille'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        DETENU = 'detenu', 'Détenu'
        RETOURNE = 'retourne', 'Retourné'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_materiels_consignes')
    designation = models.CharField(max_length=255)
    type_materiel = models.CharField(
        max_length=20, choices=TypeMateriel.choices,
        default=TypeMateriel.AUTRE)
    fournisseur = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_materiels_consignes')
    quantite = models.PositiveIntegerField(default=0)
    caution_unitaire = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.DETENU)
    reference_externe = models.CharField(max_length=80, blank=True, null=True)
    date_reception = models.DateField(null=True, blank=True)
    date_retour = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    retourne_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_materiels_consignes_retournes')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_materiels_consignes_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Matériel consigné'
        verbose_name_plural = 'Matériels consignés'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_consig_co_statut'),
            models.Index(fields=['company', 'fournisseur'],
                         name='idx_consig_co_fourn'),
        ]

    def __str__(self):
        return f'{self.designation} × {self.quantite} ({self.statut})'

    @property
    def caution_totale(self):
        """Caution totale immobilisée (caution_unitaire × quantité)."""
        return self.caution_unitaire * self.quantite
