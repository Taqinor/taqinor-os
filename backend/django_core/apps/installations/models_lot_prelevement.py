"""ZSTK10 — Regroupement de prélèvements en lot (batch transfer, Odoo parity).

Les pick-lists (FG321, `PickList`) sont générées PAR CHANTIER ; Odoo permet
de grouper plusieurs pickings en un « Batch Transfer » qu'un magasinier
traite en une seule tournée.

``LotPrelevement`` regroupe plusieurs `PickList` (même dépôt) derrière une
référence anti-collision (`apps.ventes.utils.references`) et un statut de
progression. La vue consolidée (`services.lignes_lot_prelevement`) TRIE
toutes les lignes des pick-lists incluses par casier (`BinLocation.ordre`,
réutilise FG321) pour une passe unique de magasinier.

Additif, multi-tenant (société posée côté serveur)."""
from django.conf import settings
from django.db import models


class LotPrelevement(models.Model):
    """ZSTK10 — lot de prélèvement regroupant plusieurs pick-lists (FG321)
    du MÊME dépôt pour une tournée magasinier unique."""

    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='lots_prelevement')
    reference = models.CharField(max_length=50)
    pick_lists = models.ManyToManyField(
        'installations.PickList', related_name='lots_prelevement')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.PLANIFIE)
    operateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lots_prelevement_assignes')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lots_prelevement_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lot de prélèvement'
        verbose_name_plural = 'Lots de prélèvement'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return f'{self.reference} ({self.statut})'
