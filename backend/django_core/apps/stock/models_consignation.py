"""NTDST3 — Consignation de stock CHEZ LE CLIENT (dépôt-vente).

Le client garde de la marchandise sur son site et ne paie que ce qu'il
consomme. C'est du stock qui a quitté notre dépôt SANS être vendu : il faut
donc décrémenter le dépôt à la mise en place (mouvement SORTIE motivé), suivre
le restant, et ne facturer qu'à la consommation déclarée.

INVARIANTS SERVEUR (les deux erreurs classiques du dépôt-vente) :
  * une déclaration de consommation ne décrémente JAMAIS une deuxième fois le
    dépôt principal — le stock est parti à la création du dépôt ;
  * une consommation n'est jamais négative ni supérieure au restant.

Cross-app : ``client`` pointe ``crm.Client`` en STRING-FK (jamais un import de
``apps.crm.models``).
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class DepotConsignation(TenantModel):
    """Marchandise déposée chez un client, non encore facturée."""

    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        CLOS = 'clos', 'Clos'

    client = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT,  # on_delete: PROTECT — un dépôt engage de la marchandise RÉELLE chez ce client ; on refuse la suppression plutôt que d'orpheliner du stock physique
        related_name='depots_consignation_stock')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,  # on_delete: PROTECT — trace de stock physique déposé (aligné sur MouvementStock)
        related_name='depots_consignation')
    quantite_deposee = models.PositiveIntegerField(default=0)
    quantite_consommee_declaree = models.PositiveIntegerField(default=0)
    date_depot = models.DateField()
    adresse_site = models.CharField(max_length=255, blank=True, default='')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.ACTIF)
    emplacement_source = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='depots_consignation')
    note = models.TextField(blank=True, default='')
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='depots_consignation_crees')

    class Meta:
        verbose_name = 'Dépôt de consignation'
        verbose_name_plural = 'Dépôts de consignation'
        ordering = ['-date_depot', '-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_depotcons_co_statut'),
            models.Index(fields=['company', 'client'],
                         name='idx_depotcons_co_client'),
        ]

    def __str__(self):
        return f'Consignation {self.produit_id} chez {self.client_id}'

    @property
    def quantite_restante(self):
        """Déposé − consommé déclaré, jamais négatif."""
        return max(int(self.quantite_deposee or 0)
                   - int(self.quantite_consommee_declaree or 0), 0)


class DeclarationConsommation(TenantModel):
    """Une consommation déclarée par le client sur un dépôt.

    ``statut`` FACTUREE est ce qui rend la facturation IDEMPOTENTE (NTDST4) :
    facturer deux fois la même déclaration est refusé côté serveur.
    """

    class Statut(models.TextChoices):
        DECLAREE = 'declaree', 'Déclarée'
        FACTUREE = 'facturee', 'Facturée'

    depot = models.ForeignKey(
        DepotConsignation, on_delete=models.CASCADE,  # on_delete: CASCADE — une déclaration n'existe QUE pour son dépôt (composition stricte, aucune valeur orpheline)
        related_name='declarations')
    quantite = models.PositiveIntegerField()
    date_declaration = models.DateField()
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.DECLAREE)
    document_reference = models.CharField(
        max_length=80, blank=True, default='',
        help_text='Référence du document de vente émis (NTDST4).')
    declaree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='declarations_consommation_stock')
    note = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Déclaration de consommation'
        verbose_name_plural = 'Déclarations de consommation'
        ordering = ['-date_declaration', '-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_declcons_co_statut'),
        ]

    def __str__(self):
        return f'{self.depot_id} × {self.quantite} ({self.statut})'
