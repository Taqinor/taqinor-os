"""Modèles du module « ecommerce_connect » (Groupe NTRET) — connecteurs
Shopify (NTRET18) et WooCommerce (NTRET19), tous deux ``[GATED: clé API]``.

MULTI-TENANT : tout modèle hérite de ``core.models.TenantModel`` (FK
``company`` + horodatage, ARC1).

Frontière inter-app (CLAUDE.md) : ``produit_id``/``facture_id`` référencent
``stock.Produit``/``ventes.Facture`` par un ENTIER OPAQUE — jamais une FK
cross-app — même patron que ``contrats.Contrat.sav_contrat_maintenance_id``.
Ce module ne stocke AUCUN secret (clé API) en base : la clé vit UNIQUEMENT
dans les variables d'environnement (``.env``, voir ``shopify.py``/
``woocommerce.py``) — absente = tout dégrade en no-op total.
"""
from django.db import models

from core.models import TenantModel


class ConnexionEcommerce(TenantModel):
    """Configuration (SANS secret) d'une boutique Shopify/WooCommerce.

    Le secret/la clé API viennent EXCLUSIVEMENT de ``.env`` (jamais de cette
    table) — ce modèle ne porte que des métadonnées non sensibles. Une
    société peut avoir au plus UNE connexion par plateforme.
    """

    class Plateforme(models.TextChoices):
        SHOPIFY = 'shopify', 'Shopify'
        WOOCOMMERCE = 'woocommerce', 'WooCommerce'

    plateforme = models.CharField(max_length=20, choices=Plateforme.choices)
    boutique_url = models.URLField(
        blank=True, default='',
        help_text="URL de la boutique (ex. https://ma-boutique.myshopify.com).")
    actif = models.BooleanField(
        default=False,
        help_text=(
            'Interrupteur applicatif — ne remplace PAS la clé API : sans '
            "clé en .env, la synchronisation reste no-op même si actif=True."))
    derniere_sync_catalogue = models.DateTimeField(null=True, blank=True)
    derniere_sync_commandes = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Connexion e-commerce'
        verbose_name_plural = 'Connexions e-commerce'
        ordering = ['plateforme']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'plateforme'],
                name='uniq_connexionecommerce_company_plateforme'),
        ]

    def __str__(self):
        return f'{self.get_plateforme_display()} ({self.boutique_url or "—"})'


class ProduitSync(TenantModel):
    """Association produit ERP ↔ produit externe (Shopify/WooCommerce).

    Le produit ERP est référencé par ``produit_id`` (entier opaque vers
    ``stock.Produit`` — jamais une FK, jamais un import de ``apps.stock``) :
    l'opt-in « vendable en ligne » vit ICI (dans notre propre app), pas comme
    un nouveau champ sur ``stock.Produit`` (hors périmètre de cette lane).
    """

    class Statut(models.TextChoices):
        OK = 'ok', 'Synchronisé'
        ERREUR = 'erreur', 'Erreur'
        EN_ATTENTE = 'en_attente', 'En attente'

    connexion = models.ForeignKey(
        ConnexionEcommerce, on_delete=models.CASCADE, related_name='produits')
    produit_id = models.PositiveIntegerField(
        help_text="Référence opaque vers stock.Produit.id (jamais une FK).")
    vendable_en_ligne = models.BooleanField(default=True)
    external_product_id = models.CharField(max_length=100, blank=True, default='')
    derniere_sync = models.DateTimeField(null=True, blank=True)
    dernier_statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    dernier_message = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Produit synchronisé'
        verbose_name_plural = 'Produits synchronisés'
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['connexion', 'produit_id'],
                name='uniq_produitsync_connexion_produit'),
        ]

    def __str__(self):
        return f'Produit #{self.produit_id} ↔ {self.connexion}'


class CommandeSync(TenantModel):
    """Commande externe (Shopify/WooCommerce) PAYÉE, traitée côté ERP.

    ``external_order_id`` + ``connexion`` sont la clé d'IDEMPOTENCE : un
    webhook rejoué (at-least-once, comme tout webhook e-commerce) ne crée
    JAMAIS une seconde facture (voir ``shopify.py``/``common.py``).
    ``facture_id`` référence ``ventes.Facture`` par entier opaque (jamais une
    FK cross-app).
    """

    class Statut(models.TextChoices):
        TRAITEE = 'traitee', 'Traitée'
        ERREUR = 'erreur', 'Erreur'

    connexion = models.ForeignKey(
        ConnexionEcommerce, on_delete=models.CASCADE, related_name='commandes')
    external_order_id = models.CharField(max_length=100)
    facture_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Référence opaque vers ventes.Facture.id (jamais une FK).")
    statut = models.CharField(max_length=10, choices=Statut.choices)
    message = models.TextField(blank=True, default='')
    payload_brut = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Commande synchronisée'
        verbose_name_plural = 'Commandes synchronisées'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['connexion', 'external_order_id'],
                name='uniq_commandesync_connexion_external_order'),
        ]

    def __str__(self):
        return f'{self.external_order_id} ({self.connexion})'
