"""NTDST14 — historique : stock embarqué dans un véhicule (van sales).

SOLMVP12 (20/09/2026) — le lien véhicule (module flotte, détaché de stock) a
été retiré : la fonctionnalité « van sales » de chargement/déchargement par
véhicule a été supprimée avec lui (voir ``docs/parked-modules.md``). Le
modèle est conservé à l'identique (table + données historiques), sans son
champ de lien.
"""
from django.db import models

from core.models import TenantModel


class StockVehicule(TenantModel):
    """Historique : quantité d'un produit EMBARQUÉE (fonctionnalité retirée,
    SOLMVP12 — la colonne de lien véhicule a été supprimée)."""

    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,  # on_delete: PROTECT — trace de stock physique (aligné sur MouvementStock/StockEmplacement)
        related_name='stocks_vehicule')
    quantite_embarquee = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Stock embarqué véhicule'
        verbose_name_plural = 'Stocks embarqués véhicule'
        ordering = ['produit_id']

    def __str__(self):
        return f'{self.produit_id} × {self.quantite_embarquee}'
