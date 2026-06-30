"""
FG318 — Contrats & accords de prix fournisseur (datés / versionnés).

Au-delà du « dernier prix d'achat » (toujours volatil), un contrat de prix
fournisseur fige une CONVENTION datée et VERSIONNÉE : tel fournisseur
(``stock.Fournisseur``, string-FK) garantit tels prix (``ContratPrixLigne`` →
``stock.Produit``, string-FK) sur une période, avec un numéro de version. On peut
ainsi retrouver le prix convenu À UNE DATE donnée, pas seulement le dernier saisi.

Cross-app : références ``stock`` en STRING-FK uniquement — aucun import du modèle
``stock``. Montants INTERNES. Couche INDÉPENDANTE des statuts de l'OS. Additif &
multi-tenant : FK ``company`` posée côté serveur.
"""
from django.conf import settings
from django.db import models


class ContratPrixFournisseur(models.Model):
    """FG318 — convention de prix datée/versionnée avec un fournisseur.

    Multi-tenant : société posée côté serveur. Référence ``CPF-YYYYMM-NNNN``
    anti-collision (jamais count()+1). ``version`` permet de tracer les révisions
    successives d'un même accord."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ACTIF = 'actif', 'Actif'
        EXPIRE = 'expire', 'Expiré'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_contrats_prix')
    reference = models.CharField(max_length=50)
    intitule = models.CharField(max_length=255)
    fournisseur = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.PROTECT,
        related_name='installations_contrats_prix')
    version = models.PositiveIntegerField(default=1)
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_contrats_prix_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contrat de prix fournisseur'
        verbose_name_plural = 'Contrats de prix fournisseur'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            # Noms d'index ≤ 30 caractères.
            models.Index(fields=['company', 'fournisseur'],
                         name='idx_cpf_co_fournisseur'),
            models.Index(fields=['company', 'statut'],
                         name='idx_cpf_co_statut'),
        ]

    def __str__(self):
        return f'{self.reference} v{self.version}'

    def est_en_vigueur(self, a_la_date=None):
        """Vrai si le contrat est actif et couvre la date donnée (aujourd'hui par
        défaut). Une borne absente est ouverte de ce côté."""
        from django.utils import timezone
        if self.statut != self.Statut.ACTIF:
            return False
        ref = a_la_date or timezone.now().date()
        if self.date_debut and ref < self.date_debut:
            return False
        if self.date_fin and ref > self.date_fin:
            return False
        return True


class ContratPrixLigne(models.Model):
    """FG318 — prix convenu d'un SKU dans un contrat (string-FK stock.Produit ou
    désignation libre). Prix unitaire NÉGOCIÉ (INTERNE). Une remise % facultative
    documente l'accord."""

    contrat = models.ForeignKey(
        ContratPrixFournisseur, on_delete=models.CASCADE,
        related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_contrat_prix_lignes')
    designation = models.CharField(max_length=255, blank=True, null=True)
    prix_convenu = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    remise_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = 'Ligne de contrat de prix'
        verbose_name_plural = 'Lignes de contrat de prix'
        indexes = [
            models.Index(fields=['contrat'], name='idx_cpl_contrat'),
            models.Index(fields=['produit'], name='idx_cpl_produit'),
        ]

    def __str__(self):
        return f'{self.designation or self.produit_id} @ {self.prix_convenu}'
