"""ZSTK9 — Capacité & compatibilité d'emplacement + règle de rangement
configurable (storage categories / putaway rules, Odoo parity).

FG319/320 posent des casiers + une opération de put-away, mais la suggestion
était codée en dur (casier déjà affecté au produit, sinon 1er casier par
ordre) — Odoo a des « Storage Categories » (capacité/compatibilité) + des
« Putaway Rules » configurables.

``CategorieStockage`` (capacité/compatibilité) est posable sur un
``BinLocation`` (FK nullable — sans catégorie, comportement historique
inchangé). ``RegleRangement`` (produit string-FK, ``bin_cible`` FK, priorité)
est consultée EN PREMIER par la suggestion put-away (FG320,
``selectors.suggerer_bin_putaway``), qui rejette ensuite un casier dont la
capacité/compatibilité est dépassée, avant le repli historique.

Additif, multi-tenant (société posée côté serveur)."""
from django.db import models


class CategorieStockage(models.Model):
    """ZSTK9 — catégorie de stockage : capacité (poids/quantité max) et
    compatibilité (mélange de produits autorisé ou non) posable sur un
    `BinLocation`. Sans catégorie posée sur un casier, ce dernier garde son
    comportement historique (aucune limite)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_categories_stockage')
    nom = models.CharField(max_length=120)
    poids_max_kg = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    qte_max = models.PositiveIntegerField(null=True, blank=True)
    melange_autorise = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Catégorie de stockage'
        verbose_name_plural = 'Catégories de stockage'
        ordering = ['nom']
        unique_together = [('company', 'nom')]

    def __str__(self):
        return self.nom


class RegleRangement(models.Model):
    """ZSTK9 — règle de rangement configurable : pour un produit (string-FK)
    OU une catégorie produit (texte libre), un casier cible préféré à une
    priorité donnée. Consultée par PRIORITÉ (plus petite d'abord) avant le
    repli historique (FG319/320)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_regles_rangement')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        null=True, blank=True, related_name='+')
    categorie_produit = models.CharField(
        max_length=120, blank=True, null=True,
        help_text='Catégorie produit (texte libre) — alternative à `produit` '
                  'pour une règle qui vise toute une famille.')
    bin_cible = models.ForeignKey(
        'installations.BinLocation', on_delete=models.CASCADE,
        related_name='regles_rangement')
    priorite = models.PositiveIntegerField(default=100)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Règle de rangement'
        verbose_name_plural = 'Règles de rangement'
        ordering = ['priorite', 'id']
        indexes = [
            models.Index(fields=['company', 'produit'],
                         name='idx_regrang_co_produit'),
            models.Index(fields=['company', 'actif'],
                         name='idx_regrang_co_actif'),
        ]

    def __str__(self):
        cible = self.produit_id or self.categorie_produit
        return f'Règle {cible} → {self.bin_cible_id} (prio {self.priorite})'
