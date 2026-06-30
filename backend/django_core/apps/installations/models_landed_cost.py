"""
FG316 — Frais d'import & coût de revient débarqué (landed cost).

Étend le dossier d'import (``DossierImport``, FG315) avec :
  * ``FraisImport`` : les frais encourus (fret maritime, douane, TVA import,
    transit/transport interne, manutention, assurance…) sur un dossier ;
  * ``LandedCostLigne`` : la ventilation du COÛT DÉBARQUÉ par SKU — coût FOB +
    quote-part des frais — pour obtenir le vrai prix de revient par article.

Le coût débarqué se calcule en RÉPARTISSANT le total des frais sur les lignes au
prorata de leur valeur FOB (clé d'allocation standard). Montants INTERNES — jamais
client-facing.

DÉVIATION ASSUMÉE vs DC38 : DC38 vise à intégrer le landed cost dans
``stock.average_cost_with_source``. Cette lane ne PEUT PAS éditer ``stock`` (app
business-core, interdit). On expose donc le coût débarqué par SKU côté
installations (string-FK ``stock.Produit``) en LECTURE ; l'écriture dans le coût
moyen pondéré stock restera à câbler par la lane stock quand DC38 sera traité.

Cross-app : ``stock.Produit`` en STRING-FK uniquement. Additif & multi-tenant.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models


class FraisImport(models.Model):
    """FG316 — un frais d'import imputé à un dossier (fret, douane, TVA import,
    transit…). Montant INTERNE. Multi-tenant : société posée côté serveur."""

    class Categorie(models.TextChoices):
        FRET = 'fret', 'Fret maritime / aérien'
        DOUANE = 'douane', 'Droits de douane'
        TVA_IMPORT = 'tva_import', 'TVA à l\'import'
        TRANSIT = 'transit', 'Transit / transport interne'
        MANUTENTION = 'manutention', 'Manutention / magasinage'
        ASSURANCE = 'assurance', 'Assurance'
        AUTRE = 'autre', 'Autre frais'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_frais_import')
    dossier = models.ForeignKey(
        'installations.DossierImport', on_delete=models.CASCADE,
        related_name='frais')
    # max_length=20 couvre 'manutention' (11) / 'tva_import' (10).
    categorie = models.CharField(
        max_length=20, choices=Categorie.choices, default=Categorie.AUTRE)
    libelle = models.CharField(max_length=200, blank=True, null=True)
    montant = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    date_frais = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_frais_import_crees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Frais d'import"
        verbose_name_plural = "Frais d'import"
        ordering = ['dossier_id', 'categorie', 'id']
        indexes = [
            models.Index(fields=['company', 'dossier'],
                         name='idx_frais_co_dossier'),
        ]

    def __str__(self):
        return f'{self.get_categorie_display()} · {self.montant}'


class LandedCostLigne(models.Model):
    """FG316 — ligne de coût débarqué par SKU sur un dossier d'import : valeur
    FOB (coût marchandise) + quantité. La quote-part des frais et le coût débarqué
    unitaire sont DÉRIVÉS via ``selectors.landed_cost_dossier``. Montants
    INTERNES. Multi-tenant : société posée côté serveur."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_landed_cost_lignes')
    dossier = models.ForeignKey(
        'installations.DossierImport', on_delete=models.CASCADE,
        related_name='landed_lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_landed_cost_lignes')
    designation = models.CharField(max_length=255, blank=True, null=True)
    quantite = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    # Valeur FOB de la marchandise (coût d'achat HT, INTERNE) pour cette ligne.
    valeur_fob = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ligne de coût débarqué'
        verbose_name_plural = 'Lignes de coût débarqué'
        ordering = ['dossier_id', 'id']
        indexes = [
            models.Index(fields=['company', 'dossier'],
                         name='idx_landed_co_dossier'),
        ]

    def __str__(self):
        return f'{self.designation or self.produit_id} · FOB {self.valeur_fob}'

    @property
    def cout_fob_unitaire(self):
        """Coût FOB unitaire (valeur FOB / quantité), 0 si quantité nulle."""
        q = self.quantite or Decimal('0')
        if q == 0:
            return Decimal('0')
        return (self.valeur_fob / q).quantize(Decimal('0.01'))
