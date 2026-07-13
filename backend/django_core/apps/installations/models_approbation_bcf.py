"""
FG312 — Paliers d'approbation de BCF par seuil (workflow par montant).

Avant l'ENVOI d'un bon de commande fournisseur (``stock.BonCommandeFournisseur``,
string-FK), un palier d'approbation est exigé SELON LE MONTANT : en dessous d'un
seuil paramétrable, un Responsable suffit ; au-delà, l'approbation d'un
Administrateur est requise.

``SeuilApprobationBCF`` porte le seuil paramétrable PAR société (un seul actif).
``ApprobationBCF`` enregistre l'approbation d'un BCF donné : qui a approuvé, à
quel palier, et le montant approuvé (figé pour traçabilité). Le palier REQUIS se
calcule à partir du montant et du seuil.

Cross-app : ``stock.BonCommandeFournisseur`` en string-FK uniquement — aucun
import du modèle ``stock`` au chargement. Couche INDÉPENDANTE des statuts de l'OS.
Additif & multi-tenant : FK ``company`` posée côté serveur.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models


# Paliers d'approbation (PROPRES à ce workflow — distincts des rôles ERP).
PALIER_RESPONSABLE = 'responsable'
PALIER_ADMIN = 'admin'
PALIER_CHOICES = [
    (PALIER_RESPONSABLE, 'Responsable'),
    (PALIER_ADMIN, 'Administrateur'),
]


class SeuilApprobationBCF(models.Model):
    """FG312 — seuil (MAD) par société : un BCF dont le montant d'achat dépasse
    ``seuil_responsable`` exige l'approbation d'un Administrateur ; en dessous,
    un Responsable suffit. Un seul seuil actif par société.

    Multi-tenant : la société est posée côté serveur."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_seuils_approbation_bcf')
    # Montant d'achat (HT, MAD) jusqu'auquel un Responsable peut approuver.
    seuil_responsable = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'))
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Seuil d'approbation BCF"
        verbose_name_plural = "Seuils d'approbation BCF"
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='idx_seuilbcf_co_actif'),
        ]

    def __str__(self):
        return f'Seuil {self.seuil_responsable} (société {self.company_id})'

    def palier_requis(self, montant):
        """Palier requis pour approuver ``montant`` : responsable si ≤ seuil,
        sinon admin."""
        montant = montant or Decimal('0')
        if montant <= (self.seuil_responsable or Decimal('0')):
            return PALIER_RESPONSABLE
        return PALIER_ADMIN


class ApprobationBCF(models.Model):
    """FG312 — approbation d'un bon de commande fournisseur (string-FK vers
    stock). Trace l'approbateur, le palier appliqué et le montant approuvé
    (figé). Une seule approbation par BCF (unicité société + bcf).

    Multi-tenant : la société est posée côté serveur."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_approbations_bcf')
    # Bon de commande fournisseur approuvé (string-FK vers stock).
    bcf = models.ForeignKey(
        'achats.BonCommandeFournisseur', on_delete=models.CASCADE,
        related_name='installations_approbations')
    # Palier appliqué (PROPRE à ce workflow). max_length=20 couvre 'responsable'.
    palier = models.CharField(max_length=20, choices=PALIER_CHOICES)
    # Montant d'achat (HT, MAD) au moment de l'approbation — figé.
    montant_approuve = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'))
    approuve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_approbations_bcf')
    note = models.TextField(blank=True, null=True)
    date_approbation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Approbation BCF"
        verbose_name_plural = "Approbations BCF"
        ordering = ['-date_approbation']
        unique_together = [('company', 'bcf')]
        indexes = [
            models.Index(fields=['company', 'bcf'],
                         name='idx_appbcf_co_bcf'),
        ]

    def __str__(self):
        return f'BCF {self.bcf_id} · {self.palier}'
