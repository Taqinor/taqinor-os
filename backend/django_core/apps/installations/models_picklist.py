"""
FG321 — Bons de prélèvement (pick list) par chantier.

À partir des réservations de stock d'un chantier (`StockReservation`, N14), on
génère un BON DE PRÉLÈVEMENT : la liste des SKU à sortir du magasin, ordonnée
par casier (`BinLocation`, FG319) pour minimiser le parcours du préparateur.
Chaque ligne se coche au fur et à mesure (prélevé / quantité prélevée).

Cross-app : `stock.Produit` en STRING-FK. `Installation` / `StockReservation` /
`BinLocation` sont du MÊME app (FK directe). Additif & multi-tenant : FK
`company` posée côté serveur. Couche organisationnelle — ne touche jamais aux
quantités canoniques (la consommation reste pilotée par la réservation N14).
"""
from django.conf import settings
from django.db import models


class PickList(models.Model):
    """FG321 — bon de prélèvement d'un chantier. Référence ``PICK-YYYYMM-NNNN``
    anti-collision. Statut de progression : émis → en cours → terminé."""

    class Statut(models.TextChoices):
        EMIS = 'emis', 'Émis'
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_picklists')
    reference = models.CharField(max_length=50)
    installation = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='picklists')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EMIS)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_picklists_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Bon de prélèvement'
        verbose_name_plural = 'Bons de prélèvement'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_pick_co_statut'),
            models.Index(fields=['company', 'installation'],
                         name='idx_pick_co_install'),
        ]

    def __str__(self):
        return f'{self.reference} ({self.statut})'


class PickListLigne(models.Model):
    """FG321 — ligne de prélèvement : un SKU à sortir, son casier et l'avancement.

    ``ordre`` recopie l'ordre de parcours du casier au moment de la génération
    (les lignes sans casier passent en dernier). ``preleve`` + ``quantite_prelevee``
    suivent l'exécution."""

    pick_list = models.ForeignKey(
        PickList, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_picklist_lignes')
    designation = models.CharField(max_length=255, blank=True, null=True)
    bin = models.ForeignKey(
        'installations.BinLocation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='picklist_lignes')
    quantite_demandee = models.PositiveIntegerField(default=0)
    quantite_prelevee = models.PositiveIntegerField(default=0)
    ordre = models.PositiveIntegerField(default=0)
    preleve = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Ligne de prélèvement'
        verbose_name_plural = 'Lignes de prélèvement'
        ordering = ['pick_list_id', 'ordre', 'id']
        indexes = [
            models.Index(fields=['pick_list'], name='idx_pickl_picklist'),
            models.Index(fields=['produit'], name='idx_pickl_produit'),
        ]

    def __str__(self):
        return f'{self.designation or self.produit_id} × {self.quantite_demandee}'
