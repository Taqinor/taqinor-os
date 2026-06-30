"""
FG314 — Commandes-cadres / contrats annuels (blanket orders).

Un contrat-cadre négocie À L'AVANCE des prix et un volume engagé avec un
fournisseur (``stock.Fournisseur``, string-FK), sur une période, pour des SKU
donnés (``CommandeCadreLigne`` → ``stock.Produit``, string-FK). On le DÉCLINE
ensuite en commandes d'appel (``AppelCommande``) qui consomment le volume engagé
au prix négocié — sans renégocier à chaque besoin.

Le contrat-cadre n'émet PAS de bon de commande matériel (le BCF reste géré par
``stock``) : il fournit le PRIX et le VOLUME de référence. Cross-app : références
``stock`` en STRING-FK uniquement — aucun import du modèle ``stock``.

Cycle de vie PROPRE (brouillon → actif → clos), distinct des autres couches de
statut de l'OS. Additif & multi-tenant : FK ``company`` posée côté serveur.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models


class CommandeCadre(models.Model):
    """FG314 — contrat-cadre annuel avec un fournisseur (prix négociés + volume
    engagé sur une période). Multi-tenant : société posée côté serveur. Référence
    ``CC-YYYYMM-NNNN`` anti-collision (jamais count()+1)."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ACTIF = 'actif', 'Actif'
        CLOS = 'clos', 'Clos'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_commandes_cadre')
    reference = models.CharField(max_length=50)
    intitule = models.CharField(max_length=255)
    fournisseur = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.PROTECT,
        related_name='installations_commandes_cadre')
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_commandes_cadre_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Commande-cadre'
        verbose_name_plural = 'Commandes-cadres'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_cc_co_statut'),
            models.Index(fields=['company', 'fournisseur'],
                         name='idx_cc_co_fournisseur'),
        ]

    def __str__(self):
        return f'{self.reference} · {self.intitule}'


class CommandeCadreLigne(models.Model):
    """FG314 — ligne d'un contrat-cadre : un SKU (string-FK stock.Produit), un
    prix unitaire NÉGOCIÉ (INTERNE) et un volume ENGAGÉ. Le consommé est dérivé
    des commandes d'appel."""

    commande_cadre = models.ForeignKey(
        CommandeCadre, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_commande_cadre_lignes')
    designation = models.CharField(max_length=255, blank=True, null=True)
    prix_negocie = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    volume_engage = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Ligne de commande-cadre'
        verbose_name_plural = 'Lignes de commande-cadre'
        indexes = [
            models.Index(fields=['commande_cadre'],
                         name='idx_ccl_cadre'),
        ]

    def __str__(self):
        return f'{self.designation or self.produit_id} @ {self.prix_negocie}'

    @property
    def volume_consomme(self):
        """Σ des quantités appelées sur cette ligne (commandes d'appel)."""
        return sum((a.quantite for a in self.appels.all()), Decimal('0'))

    @property
    def volume_restant(self):
        """Volume engagé restant (jamais négatif)."""
        reste = (self.volume_engage or Decimal('0')) - self.volume_consomme
        return reste if reste > 0 else Decimal('0')


class AppelCommande(models.Model):
    """FG314 — commande d'appel : consomme une quantité d'une ligne de
    contrat-cadre au prix négocié. Multi-tenant : société posée côté serveur."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_appels_commande')
    ligne = models.ForeignKey(
        CommandeCadreLigne, on_delete=models.CASCADE, related_name='appels')
    quantite = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    date_appel = models.DateField(null=True, blank=True)
    # Chantier destinataire (optionnel, même app).
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_appels_commande')
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_appels_commande_crees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Commande d'appel"
        verbose_name_plural = "Commandes d'appel"
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'ligne'],
                         name='idx_appel_co_ligne'),
        ]

    def __str__(self):
        return f'Appel {self.quantite} · ligne {self.ligne_id}'

    @property
    def montant(self):
        """Montant de l'appel = quantité × prix négocié de la ligne (INTERNE)."""
        prix = self.ligne.prix_negocie if self.ligne_id else Decimal('0')
        return (self.quantite or Decimal('0')) * (prix or Decimal('0'))
