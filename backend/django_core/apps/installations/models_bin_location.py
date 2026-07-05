"""
FG319 — Emplacements fins zone/allée/casier (bin locations).

Le stock par emplacement (`stock.EmplacementStock`, N15) ventile déjà le total
d'un produit entre dépôts/camionnettes. FG319 ajoute une couche d'ADRESSAGE FIN
SOUS un emplacement : zone → allée → casier, pour retrouver physiquement un
onduleur précis dans le dépôt. C'est un sous-découpage purement organisationnel
(localisation), il ne modifie JAMAIS les quantités canoniques du stock.

Cross-app : `stock.EmplacementStock` / `stock.Produit` en STRING-FK uniquement —
aucun import du modèle `stock`. Additif & multi-tenant : FK `company` posée côté
serveur.
"""
from django.conf import settings
from django.db import models


class BinLocation(models.Model):
    """FG319 — casier adressable (zone / allée / casier) sous un emplacement.

    Multi-tenant : société posée côté serveur. Le `code` complet (ex.
    ``A-03-12``) est unique par société+emplacement parent. Sert d'adresse de
    rangement guidé (FG320) et d'ordonnancement des prélèvements (FG321)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_bin_locations')
    emplacement = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.CASCADE,
        related_name='installations_bin_locations')
    code = models.CharField(
        max_length=40,
        help_text='Adresse complète du casier, ex. A-03-12.')
    zone = models.CharField(max_length=20, blank=True, null=True)
    allee = models.CharField(max_length=20, blank=True, null=True)
    casier = models.CharField(max_length=20, blank=True, null=True)
    # Ordre de parcours physique : sert à trier une pick list (FG321) dans le
    # sens de circulation du magasin (du plus proche de l'entrée au plus loin).
    ordre = models.PositiveIntegerField(default=100)
    # ZSTK9 — catégorie de stockage (capacité/compatibilité) posable sur ce
    # casier. Nullable : sans catégorie, comportement historique inchangé
    # (aucune limite consultée par la suggestion put-away).
    categorie = models.ForeignKey(
        'installations.CategorieStockage', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='bins')
    note = models.TextField(blank=True, null=True)
    archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_bin_locations_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Casier de rangement'
        verbose_name_plural = 'Casiers de rangement'
        ordering = ['emplacement_id', 'ordre', 'code']
        unique_together = [('company', 'emplacement', 'code')]
        indexes = [
            models.Index(fields=['company', 'emplacement'],
                         name='idx_bin_co_emplacement'),
            models.Index(fields=['company', 'archived'],
                         name='idx_bin_co_archived'),
        ]

    def __str__(self):
        return self.code


class BinAffectation(models.Model):
    """FG319 — affecte un produit (SKU) à un casier, avec une quantité indicative.

    Permet « où se trouve ce produit ? » : un même SKU peut être réparti sur
    plusieurs casiers. La quantité est INDICATIVE (localisation), elle ne fait
    pas autorité sur le total canonique `stock.EmplacementStock`."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_bin_affectations')
    bin = models.ForeignKey(
        BinLocation, on_delete=models.CASCADE, related_name='affectations')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='installations_bin_affectations')
    quantite = models.PositiveIntegerField(default=0)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Affectation produit ↔ casier'
        verbose_name_plural = 'Affectations produit ↔ casier'
        ordering = ['bin_id', 'produit_id']
        unique_together = [('bin', 'produit')]
        indexes = [
            models.Index(fields=['company', 'produit'],
                         name='idx_binaff_co_produit'),
        ]

    def __str__(self):
        return f'{self.produit_id} @ {self.bin_id} × {self.quantite}'
