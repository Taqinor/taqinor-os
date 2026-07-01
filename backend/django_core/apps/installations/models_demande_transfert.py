"""
FG325 — Demande de transfert inter-emplacements (workflow).

Le module stock exécute déjà un transfert DIRECT (N15 `TransfertStock`) qui
déplace une quantité d'un emplacement à l'autre. FG325 ajoute le WORKFLOW EN
AMONT : un magasinier DEMANDE un transfert (source → destination, SKU, quantité),
un responsable l'APPROUVE (ou le refuse), puis il est marqué EXÉCUTÉ une fois le
mouvement physique fait. C'est la couche de demande/approbation ; l'exécution
réelle du mouvement de stock reste pilotée par le module stock.

Cross-app : `stock.EmplacementStock` / `stock.Produit` en STRING-FK uniquement —
aucun import du modèle stock. Additif & multi-tenant : FK `company` posée côté
serveur.
"""
from django.conf import settings
from django.db import models


class DemandeTransfert(models.Model):
    """FG325 — demande de transfert inter-emplacements (workflow d'approbation).

    Référence ``DTR-YYYYMM-NNNN`` anti-collision. Cycle : demandé → approuvé /
    refusé → exécuté. Les champs d'approbation/exécution sont posés serveur par
    les actions dédiées."""

    class Statut(models.TextChoices):
        DEMANDE = 'demande', 'Demandé'
        APPROUVE = 'approuve', 'Approuvé'
        REFUSE = 'refuse', 'Refusé'
        EXECUTE = 'execute', 'Exécuté'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_demandes_transfert')
    reference = models.CharField(max_length=50)
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='installations_demandes_transfert')
    source = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.PROTECT,
        related_name='installations_demandes_transfert_sortantes')
    destination = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.PROTECT,
        related_name='installations_demandes_transfert_entrantes')
    quantite = models.PositiveIntegerField(default=0)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.DEMANDE)
    motif = models.TextField(blank=True, null=True)
    motif_refus = models.TextField(blank=True, null=True)
    approuve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_demandes_transfert_approuvees')
    date_approbation = models.DateTimeField(null=True, blank=True)
    date_execution = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_demandes_transfert_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Demande de transfert'
        verbose_name_plural = 'Demandes de transfert'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_dtr_co_statut'),
            models.Index(fields=['company', 'produit'],
                         name='idx_dtr_co_produit'),
        ]

    def __str__(self):
        return f'{self.reference} ({self.statut})'
