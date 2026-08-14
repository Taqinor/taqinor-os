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

    class ModeTransport(models.TextChoices):
        # NTLOG4 — flotte interne vs affrètement tiers.
        FLOTTE_PROPRE = 'flotte_propre', 'Flotte propre'
        AFFRETEMENT = 'affretement', 'Affrètement'

    class ModeAcheminementPhysique(models.TextChoices):
        # NTLOG20 — mode PHYSIQUE (route/mer/air), sert au facteur d'émission
        # CO2 — sans rapport avec `ModeTransport` ci-dessus.
        ROUTE = 'route', 'Route'
        MER = 'mer', 'Mer'
        AIR = 'air', 'Air'

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

    # NTLOG4 — affectation flotte propre vs affrètement.
    mode_transport = models.CharField(
        max_length=15, choices=ModeTransport.choices,
        default=ModeTransport.AFFRETEMENT)
    # string-FK vers flotte.ActifFlotte (référence unifiée Vehicule XOR
    # EnginRoulant — FLOTTE5 — jamais un doublon de modèle véhicule).
    flotte_actif_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Actif flotte (flotte.ActifFlotte)')
    conducteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordres_transport_conduits')
    # string-FK vers installations.Transporteur EXISTANT (NTLOG6 — jamais un
    # nouveau modèle transporteur dans cette app).
    installations_transporteur_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Transporteur (installations.Transporteur)')

    # NTLOG20 — mode physique + distance pour l'estimation CO2 (indicative).
    mode_acheminement_physique = models.CharField(
        max_length=10, choices=ModeAcheminementPhysique.choices,
        default=ModeAcheminementPhysique.ROUTE)
    distance_km = models.DecimalField(
        max_digits=8, decimal_places=1, null=True, blank=True)

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
        OrdreTransport, on_delete=models.CASCADE, related_name='lignes')  # on_delete: composition — la ligne/etape n'existe que dans son ordre de transport
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
        OrdreTransport, on_delete=models.CASCADE, related_name='etapes')  # on_delete: composition — la ligne/etape n'existe que dans son ordre de transport
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


class CoutFretReel(TenantModel):
    """NTLOG16 — coût de fret réel ventilé sur un ordre de transport. Étend
    le landed cost FG316/DC38 (`apps.stock.services`) SANS redéfinir son
    modèle : `selectors.frais_transport_pour_landed_cost` est le point de
    lecture unique que FG316 pourra consommer."""

    class TypeCout(models.TextChoices):
        TRANSPORT = 'transport', 'Transport'
        ASSURANCE = 'assurance', 'Assurance'
        MANUTENTION = 'manutention', 'Manutention'
        DEDOUANEMENT = 'dedouanement', 'Dédouanement'

    ordre_transport = models.ForeignKey(
        OrdreTransport, on_delete=models.CASCADE, related_name='couts_fret')  # on_delete: composition — le cout/litige n'existe que pour son ordre de transport
    montant_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))
    devise = models.CharField(max_length=8, default='MAD')
    type_cout = models.CharField(
        max_length=15, choices=TypeCout.choices, default=TypeCout.TRANSPORT)
    # string-FK optionnelle vers stock.BonCommandeFournisseur.
    stock_boncommandefournisseur_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='BCF (stock.BonCommandeFournisseur)')
    note = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Coût de fret réel'
        verbose_name_plural = 'Coûts de fret réels'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'stock_boncommandefournisseur_id'],
                         name='idx_cfr_co_bcf'),
        ]

    def __str__(self):
        return f'{self.type_cout} {self.montant_ht} {self.devise}'


class LitigeTransport(TenantModel):
    """NTLOG17 — litige transport (avarie/retard/manquant/erreur de
    livraison). Machine à états INDÉPENDANTE, calquée sur
    `litiges.Reclamation` (LITIGE2) SANS importer son modèle. Les
    transitions journalisent sur le chatter de l'ordre parent
    (`services.log_activite_ordre`, jamais une nouvelle classe `*Activity`,
    ARC8)."""

    class TypeLitige(models.TextChoices):
        AVARIE = 'avarie', 'Avarie'
        RETARD = 'retard', 'Retard'
        MANQUANT = 'manquant', 'Manquant'
        ERREUR_LIVRAISON = 'erreur_livraison', 'Erreur de livraison'

    class Statut(models.TextChoices):
        OUVERT = 'ouvert', 'Ouvert'
        EN_TRAITEMENT = 'en_traitement', 'En traitement'
        RESOLU = 'resolu', 'Résolu'
        REJETE = 'rejete', 'Rejeté'

    ordre_transport = models.ForeignKey(
        OrdreTransport, on_delete=models.CASCADE, related_name='litiges')  # on_delete: composition — le cout/litige n'existe que pour son ordre de transport
    type_litige = models.CharField(
        max_length=20, choices=TypeLitige.choices, default=TypeLitige.AVARIE)
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.OUVERT)
    montant_conteste = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))
    description = models.TextField(blank=True, default='')
    # NTLOG19 — trace de l'envoi de la réclamation transporteur chiffrée.
    reclamation_envoyee_le = models.DateTimeField(null=True, blank=True)
    reclamation_destinataire = models.CharField(
        max_length=255, blank=True, default='')
    # NTLOG31 — montant réellement obtenu du transporteur à la résolution
    # (peut différer de `montant_conteste`) ; posé optionnellement par
    # `views.LitigeTransportViewSet.resoudre`, `None` tant que non résolu ou
    # non renseigné (relevé NTLOG31 l'affiche vide dans ce cas, jamais un 0
    # trompeur).
    montant_resolu = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='litiges_transport_crees')

    class Meta:
        verbose_name = 'Litige transport'
        verbose_name_plural = 'Litiges transport'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'statut'], name='idx_lt_co_statut'),
        ]

    def __str__(self):
        return f'{self.type_litige} · {self.ordre_transport_id}'


class ReserveReception(TenantModel):
    """NTLOG18 — réserve saisie à la réception (au moment du POD), avec
    photos via `records.Attachment` générique (jamais un nouveau
    `FileField`). Sa création fait automatiquement naître un
    `LitigeTransport` « ouvert » (`services.creer_litige_depuis_reserve`)."""

    etape = models.ForeignKey(
        EtapeTransport, on_delete=models.CASCADE, related_name='reserves')  # on_delete: composition — la reserve n'existe que pour son etape de transport
    nature_reserve = models.TextField(blank=True, default='')
    montant_estime_dommage = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True)
    # Référence croisée posée côté serveur à la création (jamais lue du
    # corps de requête) — voir services.creer_litige_depuis_reserve.
    litige = models.ForeignKey(
        LitigeTransport, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reserves')

    class Meta:
        verbose_name = 'Réserve à réception'
        verbose_name_plural = 'Réserves à réception'
        ordering = ['-created_at']

    def __str__(self):
        return f'Réserve · étape {self.etape_id}'


class FacteurEmissionCO2(TenantModel):
    """NTLOG20 — facteur d'émission CO2 éditable en Paramètres, par mode
    physique d'acheminement (route/mer/air), en kg CO2 par tonne.km."""

    class Mode(models.TextChoices):
        ROUTE = 'route', 'Route'
        MER = 'mer', 'Mer'
        AIR = 'air', 'Air'

    mode = models.CharField(max_length=10, choices=Mode.choices)
    facteur_kg_co2_par_tonne_km = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal('0'))

    class Meta:
        verbose_name = "Facteur d'émission CO2"
        verbose_name_plural = "Facteurs d'émission CO2"
        ordering = ['mode']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'mode'], name='uniq_facteurco2_co_mode'),
        ]

    def __str__(self):
        return f'{self.mode} · {self.facteur_kg_co2_par_tonne_km} kgCO2/t.km'
