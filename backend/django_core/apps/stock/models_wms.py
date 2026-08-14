"""Groupe NTWMS — couche ENTREPÔT professionnelle de l'app ``stock``.

Regroupe les modèles WMS que `stock` POSSÈDE (vagues de prélèvement, unités
logistiques/SSCC, quais et rendez-vous transporteur, expéditions, plans de
comptage tournant) pour ne pas alourdir le ``models.py`` historique — même
pratique que ``installations/models_kitting.py``. ``models.py`` les ré-importe
en fin de fichier, donc Django les enregistre normalement sous l'app ``stock``.

CE QUI N'EST **PAS** ICI, ET NE LE SERA JAMAIS
----------------------------------------------
La hiérarchie de casiers zone/allée/casier (``BinLocation``/``BinAffectation``,
FG319), les règles de rangement (``RegleRangement``/``CategorieStockage``,
ZSTK9), le put-away (``PutAway``, FG320) et les bons de prélèvement par
chantier (``PickList``, FG321) existent DÉJÀ dans ``installations``. Ce module
ne les duplique pas : il les référence en STRING-FK et les lit via
``apps.installations.selectors``. Un modèle parallèle serait la dette n°1
identifiée par le fondateur.

Règles respectées : multi-tenant via ``core.models.TenantModel`` ; numérotation
via ``core.numbering`` (jamais ``count()+1``) ; cross-app en STRING-FK
uniquement.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS4 — Vagues et bons de picking optimisés (wave picking)
# ═══════════════════════════════════════════════════════════════════════════

class VaguePicking(TenantModel):
    """Vague de prélèvement MULTI-SOURCE.

    Là où ``installations.PickList`` (FG321) sort le matériel d'UN chantier,
    une vague regroupe les besoins de PLUSIEURS sources (chantiers, commandes)
    en une seule tournée de magasin, ordonnée par le parcours physique.
    Référence ``VAG-YYYYMM-NNNN`` race-safe (``core.numbering``).
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        LANCEE = 'lancee', 'Lancée'
        TERMINEE = 'terminee', 'Terminée'

    reference = models.CharField(max_length=50)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    note = models.TextField(blank=True, null=True)
    date_lancement = models.DateTimeField(null=True, blank=True)
    date_cloture = models.DateTimeField(null=True, blank=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vagues_picking_creees')

    class Meta:
        verbose_name = 'Vague de prélèvement'
        verbose_name_plural = 'Vagues de prélèvement'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='stock_vaguepicking_company_reference_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_vaguepick_co_statut'),
        ]

    def __str__(self):
        return f'{self.reference} ({self.statut})'

    @property
    def est_terminee(self):
        """Vrai quand toutes les lignes sont servies (jamais un état déduit
        du seul statut : la vérité vient des lignes)."""
        lignes = list(self.lignes.all())
        if not lignes:
            return False
        return all(ligne.quantite_prelevee >= ligne.quantite_demandee
                   for ligne in lignes)


class LignePicking(TenantModel):
    """Ligne d'une vague : un produit à prélever, sa source, son casier.

    ``ordre_parcours`` est calculé à la création (tri zone → allée → casier du
    casier résolu, NTWMS3) : la liste servie au magasinier suit le magasin, pas
    l'ordre de saisie.
    """

    vague = models.ForeignKey(
        VaguePicking, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,
        related_name='lignes_picking')  # on_delete: PROTECT — une ligne prélevée est une trace d'exécution magasin ; aligné sur MouvementStock/LigneInventaire
    quantite_demandee = models.PositiveIntegerField(default=0)
    quantite_prelevee = models.PositiveIntegerField(default=0)
    # Casier SOURCE — string-FK vers la hiérarchie FG319 (jamais dupliquée).
    bin = models.ForeignKey(
        'installations.BinLocation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lignes_picking')
    lot = models.ForeignKey(
        'stock.LotEntrepot', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lignes_picking')
    # Sources possibles de la demande (string-FK cross-app).
    installation = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lignes_picking')
    bon_commande = models.ForeignKey(
        'achats.BonCommandeFournisseur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lignes_picking')
    ordre_parcours = models.PositiveIntegerField(default=1000)

    class Meta:
        verbose_name = 'Ligne de prélèvement'
        verbose_name_plural = 'Lignes de prélèvement'
        ordering = ['ordre_parcours', 'id']
        indexes = [
            models.Index(fields=['company', 'vague'],
                         name='idx_lignepick_co_vague'),
        ]

    def __str__(self):
        return f'{self.produit_id} × {self.quantite_demandee}'

    @property
    def reste_a_prelever(self):
        return max(self.quantite_demandee - self.quantite_prelevee, 0)


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS6 — Unités logistiques : colis, palette, SSCC
# ═══════════════════════════════════════════════════════════════════════════

class UniteLogistique(TenantModel):
    """Colis ou palette ADRESSABLE, porteur d'un SSCC GS1 (18 chiffres).

    Étend le colisage FG322 (``installations.Colis``, contrôle avant départ)
    en objet adressable et hiérarchique : une PALETTE (``parent``) regroupe
    plusieurs COLIS, chaque colis regroupe des lignes issues du picking
    (NTWMS4). Le SSCC est calculé en stdlib (clé de contrôle GS1 mod-10) —
    aucune dépendance externe.

    ``sceller()`` (service) FIGE le contenu : après scellage, aucune ligne ne
    peut plus être ajoutée ni modifiée.
    """

    class TypeUnite(models.TextChoices):
        COLIS = 'colis', 'Colis'
        PALETTE = 'palette', 'Palette'

    class Statut(models.TextChoices):
        EN_PREPARATION = 'en_preparation', 'En préparation'
        SCELLE = 'scelle', 'Scellé'
        EXPEDIE = 'expedie', 'Expédié'

    type_unite = models.CharField(
        max_length=10, choices=TypeUnite.choices, default=TypeUnite.COLIS)
    sscc = models.CharField(
        max_length=18,
        help_text='Serial Shipping Container Code GS1 (18 chiffres, clé de '
                  'contrôle mod-10 incluse).')
    # Hiérarchie : une palette contient des colis (self-FK, nullable).
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='enfants',
        help_text='Palette contenante (vide = unité de premier niveau).')
    vague = models.ForeignKey(
        VaguePicking, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='unites_logistiques',
        help_text='Vague de prélèvement d\'origine (NTWMS4), si applicable.')
    poids_kg = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True)
    dimensions = models.CharField(
        max_length=60, blank=True, default='',
        help_text='L × l × h en cm, texte libre (ex. « 120 × 80 × 145 »).')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.EN_PREPARATION)
    date_scellage = models.DateTimeField(null=True, blank=True)
    scelle_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='unites_logistiques_scellees')

    class Meta:
        verbose_name = 'Unité logistique'
        verbose_name_plural = 'Unités logistiques'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'sscc'],
                name='stock_unitelogistique_company_sscc_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_unitelog_co_statut'),
        ]

    def __str__(self):
        return f'{self.get_type_unite_display()} {self.sscc}'

    @property
    def est_figee(self):
        """Une unité scellée ou expédiée ne peut plus changer de contenu."""
        return self.statut in (self.Statut.SCELLE, self.Statut.EXPEDIE)


class UniteLogistiqueLigne(TenantModel):
    """Ligne de contenu d'une unité logistique (produit + quantité + lot)."""

    unite = models.ForeignKey(
        UniteLogistique, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,
        related_name='lignes_unite_logistique')  # on_delete: PROTECT — contenu réel d'un colis expédié, conservé pour la traçabilité (aligné sur LignePicking/MouvementStock)
    quantite = models.PositiveIntegerField(default=0)
    lot = models.ForeignKey(
        'stock.LotEntrepot', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lignes_unite_logistique')
    ligne_picking = models.ForeignKey(
        LignePicking, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_unite_logistique',
        help_text='Ligne de vague d\'origine (NTWMS4), si applicable.')

    class Meta:
        verbose_name = 'Ligne d\'unité logistique'
        verbose_name_plural = 'Lignes d\'unité logistique'
        ordering = ['id']
        indexes = [
            models.Index(fields=['company', 'unite'],
                         name='idx_unitelogl_co_unite'),
        ]

    def __str__(self):
        return f'{self.produit_id} × {self.quantite}'
