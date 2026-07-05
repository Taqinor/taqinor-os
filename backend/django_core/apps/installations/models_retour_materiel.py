"""YSTCK4 — Retour chantier : matériel non posé rapporté du site au dépôt.

`consume_reservations`/`field_capture.validate_consommation` sortent le stock
au chantier mais RIEN ne permettait jusqu'ici de faire remonter le surplus
non installé vers le dépôt (un rouleau de câble rapporté du site restait soit
perdu, soit ré-injecté par un ajustement manuel non tracé au chantier).

``RetourMateriel`` (une entête par retour) + ``RetourMaterielLigne`` (une par
SKU) matérialisent le blueprint « retour chantier = mouvement ENTRÉE
référençant la sortie d'origine, décrémente le consommé du projet, jamais un
ajustement positif libre » : la validation d'un retour poste UN
``MouvementStock`` ENTREE par ligne (``apps.stock.services.record_stock_
movement``, jamais un import direct des models stock) référencé
``RETOUR-<reference-chantier>``, plafonné à la quantité RÉELLEMENT sortie
pour ce chantier (somme des ``ConsommationLigne.quantite_utilisee`` validées
moins ce qui a déjà été retourné).

Additif, multi-tenant (société posée côté serveur)."""
from django.conf import settings
from django.db import models

from .models_installation import Installation


class RetourMateriel(models.Model):
    """YSTCK4 — entête d'un retour de matériel non posé, d'un chantier vers
    le dépôt. Une ligne par SKU rapporté (``RetourMaterielLigne``)."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDE = 'valide', 'Validé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='retours_materiel')
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='retours_materiel')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    note = models.TextField(blank=True, null=True)
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
        verbose_name = 'Retour de matériel chantier'
        verbose_name_plural = 'Retours de matériel chantier'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'installation'],
                         name='idx_retmat_co_inst'),
        ]

    def __str__(self):
        return f'Retour · {self.installation_id} ({self.statut})'


class RetourMaterielLigne(models.Model):
    """YSTCK4 — une ligne {produit, quantité} d'un retour de matériel."""

    retour = models.ForeignKey(
        RetourMateriel, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    designation = models.CharField(max_length=255, blank=True, null=True)
    quantite = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # True une fois le mouvement ENTREE posté (idempotence par ligne).
    stock_applique = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Ligne de retour de matériel'
        verbose_name_plural = 'Lignes de retour de matériel'
        ordering = ['retour_id', 'id']
        indexes = [
            models.Index(fields=['retour'], name='idx_retmatl_retour'),
        ]

    def __str__(self):
        return f'{self.designation or self.produit_id} × {self.quantite}'
