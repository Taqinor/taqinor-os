"""Modèles de l'app `apps.transport` (Groupe SUPPLY — NTLOG1-20 en cours).

`OrdreTransport` (enlèvement/livraison/inter-site/import/export) + ses
`EtapeTransport`/`LigneOrdreTransport`, coûts de fret réels, litiges
transport et émissions CO2 estimées.

Cross-app : AUCUN import de `apps.installations`/`apps.stock`/`apps.flotte`/
`apps.ventes` `.models`. Les liens vers ces apps sont des « string-FK » — un
`PositiveIntegerField` nommé `<app>_<model>_id`, résolu à la lecture via le
`selectors.py` de l'app cible (ou, faute de sélecteur dédié, un
`django.apps.apps.get_model(...)` fonction-local en LECTURE SEULE — même
patron que FG294 `installations.selectors.budget_projet_synthese`). Jamais un
`from apps.X.models import ...` statique.

Multi-tenant : chaque modèle hérite de `core.models.TenantModel` (FK
`company` + horodatage posés une fois pour toutes — jamais une FK `company`
à la main, SCA4).

Pas de nouveau `*Activity` (ARC8) : l'historique de `OrdreTransport` passe
par le chatter générique `records.Activity` + `ChatterViewSetMixin` (cibles
déclarées dans `apps/transport/platform.py`). Pas de `FileField` (ARC26) :
les photos/signatures (preuve de livraison, réserves à réception) passent
par `records.Attachment` générique.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TenantModel


class OrdreTransport(TenantModel):
    """NTLOG1 — ordre de transport. `numero` est attribué côté serveur, anti-
    collision (`services.attribuer_numero` → `core.numbering.next_reference`,
    JAMAIS un `count()+1`, ARC6)."""

    class TypeFlux(models.TextChoices):
        ENLEVEMENT_LIVRAISON = 'enlevement_livraison', 'Enlèvement / livraison'
        INTER_SITE = 'inter_site', 'Inter-site'
        IMPORT = 'import', 'Import'
        EXPORT = 'export', 'Export'

    class Statut(models.TextChoices):
        # Machine INDÉPENDANTE de STAGES.py (règle CLAUDE.md #2) — le statut
        # de l'ordre de transport n'est PAS le funnel commercial.
        BROUILLON = 'brouillon', 'Brouillon'
        PLANIFIE = 'planifie', 'Planifié'
        EN_COURS = 'en_cours', 'En cours'
        LIVRE = 'livre', 'Livré'
        ANNULE = 'annule', 'Annulé'

    numero = models.CharField(max_length=30, blank=True, default='')
    type_flux = models.CharField(
        max_length=25, choices=TypeFlux.choices,
        default=TypeFlux.ENLEVEMENT_LIVRAISON)
    expediteur_nom = models.CharField(max_length=255, blank=True, default='')
    expediteur_adresse = models.TextField(blank=True, default='')
    destinataire_nom = models.CharField(max_length=255, blank=True, default='')
    destinataire_adresse = models.TextField(blank=True, default='')
    date_enlevement_prevue = models.DateField(null=True, blank=True)
    date_livraison_prevue = models.DateField(null=True, blank=True)
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.BROUILLON)
    instructions_speciales = models.TextField(blank=True, default='')

    # String-FK optionnelles — document source (jamais un import de modèle).
    ventes_boncommande_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Bon de commande (ventes.BonCommande)')
    ventes_devis_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Devis (ventes.Devis)')
    installations_installation_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Chantier (installations.Installation)')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordres_transport_crees')

    class Meta:
        verbose_name = 'Ordre de transport'
        verbose_name_plural = 'Ordres de transport'
        ordering = ['-created_at']
        constraints = [
            # Vide toléré (brouillon en cours de création) — collision
            # anti-doublon uniquement sur un numéro RÉELLEMENT posé (motif
            # sante.Patient.numero_dossier).
            models.UniqueConstraint(
                fields=['company', 'numero'],
                condition=~models.Q(numero=''),
                name='uniq_ordretransport_co_numero'),
        ]
        indexes = [
            models.Index(fields=['company', 'statut'], name='idx_ot_co_statut'),
        ]

    def __str__(self):
        return self.numero or f'Ordre transport #{self.pk}'


class LigneOrdreTransport(TenantModel):
    """NTLOG2 — marchandise d'un ordre de transport. `stock_produit_id` est
    une string-FK optionnelle vers `stock.Produit` (jamais un import)."""

    ordre = models.ForeignKey(
        OrdreTransport, on_delete=models.CASCADE, related_name='lignes')
    stock_produit_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Produit (stock.Produit)')
    designation = models.CharField(max_length=255, blank=True, default='')
    quantite = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'))
    unite = models.CharField(max_length=20, blank=True, default='')
    poids_kg = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'))
    volume_m3 = models.DecimalField(
        max_digits=10, decimal_places=3, default=Decimal('0'))
    valeur_declaree = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Ligne d'ordre de transport"
        verbose_name_plural = "Lignes d'ordre de transport"
        ordering = ['ordre_id', 'id']
        indexes = [
            models.Index(fields=['ordre'], name='idx_lot_ordre'),
        ]

    def __str__(self):
        return f'{self.designation or self.stock_produit_id} × {self.quantite}'


class EtapeTransport(TenantModel):
    """NTLOG3 — étape enlèvement → transit → livraison d'un ordre."""

    class TypeEtape(models.TextChoices):
        ENLEVEMENT = 'enlevement', 'Enlèvement'
        TRANSIT = 'transit', 'Transit'
        LIVRAISON = 'livraison', 'Livraison'

    class StatutEtape(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        EN_COURS = 'en_cours', 'En cours'
        FAIT = 'fait', 'Fait'
        INCIDENT = 'incident', 'Incident'

    ordre = models.ForeignKey(
        OrdreTransport, on_delete=models.CASCADE, related_name='etapes')
    sequence = models.PositiveIntegerField(default=1)
    type_etape = models.CharField(
        max_length=12, choices=TypeEtape.choices, default=TypeEtape.TRANSIT)
    lieu = models.CharField(max_length=255, blank=True, default='')
    date_prevue = models.DateField(null=True, blank=True)
    date_reelle = models.DateField(null=True, blank=True)
    statut_etape = models.CharField(
        max_length=10, choices=StatutEtape.choices,
        default=StatutEtape.A_FAIRE)

    class Meta:
        verbose_name = 'Étape de transport'
        verbose_name_plural = 'Étapes de transport'
        ordering = ['ordre_id', 'sequence', 'id']
        indexes = [
            models.Index(fields=['ordre', 'sequence'], name='idx_et_ordre_seq'),
        ]

    def __str__(self):
        return f'{self.ordre_id} · étape {self.sequence} ({self.statut_etape})'
