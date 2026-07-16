"""
FG317 — Réceptionné-non-facturé (GR/IR — Goods Received / Invoice Received).

Quand une marchandise est RÉCEPTIONNÉE (entrée en stock) sans que la facture
fournisseur soit encore arrivée, il existe une DETTE LATENTE : on doit déjà
l'argent au fournisseur, mais la facture (``stock.FactureFournisseur``) n'est pas
là pour la comptabiliser. ``ReceptionNonFacturee`` provisionne cette dette : elle
rattache une réception (``stock.ReceptionFournisseur``) / un BCF
(``stock.BonCommandeFournisseur``) à un montant PROVISIONNÉ, jusqu'au LETTRAGE
(``lettre``) avec la facture reçue.

Cross-app : références ``stock`` en STRING-FK uniquement — aucun import du modèle
``stock``. Montants INTERNES. Couche INDÉPENDANTE des statuts de l'OS. Additif &
multi-tenant : FK ``company`` posée côté serveur.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models


class ReceptionNonFacturee(models.Model):
    """FG317 — provision de dette latente : marchandise reçue, facture
    fournisseur non encore reçue. Lettrée (``lettre=True``) à l'arrivée de la
    facture. Multi-tenant : société posée côté serveur. Montants INTERNES."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_receptions_non_facturees')
    # Réception et/ou BCF d'origine (string-FK vers stock, optionnels).
    reception = models.ForeignKey(
        'achats.ReceptionFournisseur', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_gr_ir')
    bon_commande = models.ForeignKey(
        'achats.BonCommandeFournisseur', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_gr_ir')
    # Facture fournisseur de lettrage (string-FK), posée à la levée.
    facture = models.ForeignKey(
        'achats.FactureFournisseur', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_gr_ir')
    libelle = models.CharField(max_length=200, blank=True, null=True)
    # Montant PROVISIONNÉ HT (dette latente, INTERNE).
    montant_provision = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'))
    date_reception = models.DateField(null=True, blank=True)
    # Lettré ? Vrai quand la facture est arrivée et rapprochée — la provision
    # est alors soldée.
    lettre = models.BooleanField(default=False)
    date_lettrage = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_gr_ir_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réceptionné-non-facturé (GR/IR)'
        verbose_name_plural = 'Réceptionnés-non-facturés (GR/IR)'
        ordering = ['-date_creation']
        indexes = [
            # Noms d'index ≤ 30 caractères.
            models.Index(fields=['company', 'lettre'],
                         name='idx_grir_co_lettre'),
            models.Index(fields=['company', 'bon_commande'],
                         name='idx_grir_co_bcf'),
        ]

    def __str__(self):
        return f'GR/IR {self.montant_provision} (société {self.company_id})'

    @property
    def montant_a_provisionner(self):
        """Montant encore provisionné (0 une fois lettré). INTERNE."""
        if self.lettre:
            return Decimal('0')
        return self.montant_provision or Decimal('0')
