"""
FG320 — Rangement guidé (put-away).

À la réception d'une marchandise, FG320 trace la MISE EN STOCK physique : pour
un produit reçu, on suggère le casier (`BinLocation`, FG319) où ranger et on
enregistre l'opération (produit, quantité, casier suggéré, casier effectif, qui,
quand). La suggestion réutilise le casier déjà affecté au produit (FG319), sinon
le premier casier non archivé de l'emplacement par ordre de parcours.

Cross-app : `stock.Produit` / `stock.EmplacementStock` en STRING-FK uniquement.
Additif & multi-tenant : FK `company` posée côté serveur. Trace purement
organisationnelle — ne touche jamais aux quantités canoniques du stock.
"""
from django.conf import settings
from django.db import models


class PutAway(models.Model):
    """FG320 — opération de rangement guidé d'un produit reçu vers un casier.

    Multi-tenant : société posée côté serveur. ``bin_suggere`` est calculé à la
    création (peut être nul si aucun casier ne convient) ; ``bin_effectif`` est
    le casier réellement utilisé par le magasinier (confirmé via l'action
    ``ranger``). ``range`` passe le statut à RANGE et horodate."""

    class Statut(models.TextChoices):
        A_RANGER = 'a_ranger', 'À ranger'
        RANGE = 'range', 'Rangé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_putaways')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='installations_putaways')
    emplacement = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_putaways')
    quantite = models.PositiveIntegerField(default=0)
    bin_suggere = models.ForeignKey(
        'installations.BinLocation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='putaways_suggeres')
    bin_effectif = models.ForeignKey(
        'installations.BinLocation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='putaways_effectifs')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.A_RANGER)
    reference_reception = models.CharField(max_length=80, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    range_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations_putaways_ranges')
    date_rangement = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_putaways_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rangement guidé (put-away)'
        verbose_name_plural = 'Rangements guidés (put-away)'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_putaway_co_statut'),
            models.Index(fields=['company', 'produit'],
                         name='idx_putaway_co_produit'),
        ]

    def __str__(self):
        return f'Put-away {self.produit_id} × {self.quantite} ({self.statut})'
