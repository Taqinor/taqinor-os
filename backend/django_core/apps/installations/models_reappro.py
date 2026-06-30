"""
FG326 — Réapprovisionnement multi-dépôts.

FG62 a posé des seuils min/max PAR EMPLACEMENT sur la ventilation du stock. FG326
en fait une RÈGLE de réapprovisionnement : pour un produit dans un emplacement
cible (ex. une camionnette), on définit un min et un max ; quand le stock passe
sous le min, on PROPOSE un transfert depuis un dépôt source pour remonter au max.
La proposition est consultative (le transfert réel passe par le workflow FG325 /
le module stock).

Cross-app : `stock.Produit` / `stock.EmplacementStock` en STRING-FK ; les
quantités courantes sont lues via `stock.selectors`. Additif & multi-tenant : FK
`company` posée côté serveur.
"""
from django.conf import settings
from django.db import models


class RegleReappro(models.Model):
    """FG326 — règle min/max de réapprovisionnement d'un produit dans un
    emplacement cible, avec un dépôt source pour le transfert proposé.

    Multi-tenant : société posée côté serveur. Une seule règle par
    (société, produit, emplacement cible)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_regles_reappro')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='installations_regles_reappro')
    emplacement_cible = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.CASCADE,
        related_name='installations_regles_reappro_cibles')
    emplacement_source = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_regles_reappro_sources')
    seuil_min = models.PositiveIntegerField(default=0)
    seuil_max = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_regles_reappro_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Règle de réapprovisionnement'
        verbose_name_plural = 'Règles de réapprovisionnement'
        ordering = ['produit_id', 'emplacement_cible_id']
        unique_together = [('company', 'produit', 'emplacement_cible')]
        indexes = [
            models.Index(fields=['company', 'active'],
                         name='idx_reappro_co_active'),
            models.Index(fields=['company', 'produit'],
                         name='idx_reappro_co_produit'),
        ]

    def __str__(self):
        return (f'{self.produit_id} @ {self.emplacement_cible_id} '
                f'[{self.seuil_min}-{self.seuil_max}]')
