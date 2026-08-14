"""NTDST14 — Tournées de vente / van sales : stock EMBARQUÉ dans un véhicule.

Un agent charge sa camionnette le matin, vend en tournée, et rentre le soir
avec le reliquat. Ce stock roulant existe physiquement : il doit sortir du
dépôt au chargement et y revenir au déchargement — jamais « disparaître » du
compte de la société entre les deux.

Cross-app : ``actif_flotte`` pointe ``flotte.ActifFlotte`` en STRING-FK
(jamais un import de ``apps.flotte.models``).
"""
from django.db import models

from core.models import TenantModel


class StockVehicule(TenantModel):
    """Quantité d'un produit actuellement EMBARQUÉE dans un véhicule."""

    actif_flotte = models.ForeignKey(
        'flotte.ActifFlotte', on_delete=models.PROTECT,  # on_delete: PROTECT — la ligne mesure du stock PHYSIQUE embarqué ; supprimer le véhicule ne doit jamais faire disparaître de la marchandise
        related_name='stocks_embarques')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,  # on_delete: PROTECT — trace de stock physique (aligné sur MouvementStock/StockEmplacement)
        related_name='stocks_vehicule')
    quantite_embarquee = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Stock embarqué véhicule'
        verbose_name_plural = 'Stocks embarqués véhicule'
        ordering = ['actif_flotte_id', 'produit_id']
        constraints = [
            # UNE ligne par (société, véhicule, produit) : indispensable, le
            # service fait un `get_or_create` sur ce triplet — sans contrainte,
            # deux chargements concurrents créeraient deux lignes et le
            # déchargement n'en verrait qu'une.
            models.UniqueConstraint(
                fields=['company', 'actif_flotte', 'produit'],
                name='stock_stockvehicule_co_actif_produit_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'actif_flotte'],
                         name='idx_stockveh_co_actif'),
        ]

    def __str__(self):
        return (f'{self.produit_id} × {self.quantite_embarquee} '
                f'@ véhicule {self.actif_flotte_id}')
