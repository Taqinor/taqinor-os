"""Modèles du module Hôtellerie & restauration (`apps.hospitality`).

Vertical vendable à un hôtel/riad/groupe resto marocain (Groupe NTHOT,
`docs/plans/PLAN_VERTICALS.md`). Multi-société stricte : chaque modèle porte
un FK ``company`` posé côté serveur (jamais lu du corps de requête). Liens
vers d'autres apps métier (crm, ventes, sav) passent par des FK string
('app.Model') ou par des identifiants souples (`*_id`) résolus via les
selectors/services de l'app cible — jamais un import direct de leurs modèles.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TenantModel


# ── NTHOT1 — Plan des chambres / unités ─────────────────────────────────────

class TypeChambre(TenantModel):
    """Catégorie de chambre (Standard/Suite/Riad-suite…)."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='hospitality_types_chambre',
        verbose_name='Société',
    )
    libelle = models.CharField(max_length=100, verbose_name='Libellé')
    capacite_max = models.PositiveIntegerField(
        default=2, verbose_name='Capacité maximale')
    description = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Type de chambre'
        verbose_name_plural = 'Types de chambre'
        ordering = ['libelle']

    def __str__(self):
        return self.libelle


class Chambre(TenantModel):
    """Chambre/unité physique de l'établissement."""

    class Statut(models.TextChoices):
        LIBRE = 'libre', 'Libre'
        OCCUPEE = 'occupee', 'Occupée'
        SALE = 'sale', 'Sale'
        EN_NETTOYAGE = 'en_nettoyage', 'En nettoyage'
        HORS_SERVICE = 'hors_service', 'Hors service'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='hospitality_chambres',
        verbose_name='Société',
    )
    type_chambre = models.ForeignKey(
        TypeChambre,
        on_delete=models.PROTECT,
        related_name='chambres',
        verbose_name='Type de chambre',
    )
    numero = models.CharField(max_length=20, verbose_name='Numéro')
    nom = models.CharField(max_length=100, blank=True, default='')
    etage = models.CharField(max_length=20, blank=True, default='')
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.LIBRE)
    vue = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Vue')

    class Meta:
        verbose_name = 'Chambre'
        verbose_name_plural = 'Chambres'
        ordering = ['numero']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'numero'],
                name='hospitality_chambre_unique_numero_par_societe',
            ),
        ]

    def __str__(self):
        return self.nom or self.numero


# ── NTHOT2 — Tarification saisonnière (rack/corporate/ota) ─────────────────

class PlanTarifaire(TenantModel):
    """Prix par nuit d'un type de chambre pour une période/canal donnés.

    Plusieurs plans peuvent se chevaucher : le prix applicable est résolu par
    ``services.prix_applicable`` (priorité canal explicite, sinon
    corporate > ota > rack par défaut — jamais ambigu)."""

    class Canal(models.TextChoices):
        RACK = 'rack', 'Rack (tarif public)'
        CORPORATE = 'corporate', 'Corporate'
        OTA = 'ota', 'OTA'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='hospitality_plans_tarifaires',
        verbose_name='Société',
    )
    type_chambre = models.ForeignKey(
        TypeChambre,
        on_delete=models.CASCADE,  # on_delete: cascade parent→enfant (composant du parent)
        related_name='plans_tarifaires',
        verbose_name='Type de chambre',
    )
    canal = models.CharField(
        max_length=10, choices=Canal.choices, default=Canal.RACK)
    date_debut = models.DateField(verbose_name='Date de début')
    date_fin = models.DateField(verbose_name='Date de fin')
    prix_nuit_ht = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Prix/nuit HT')
    min_nuits = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Minimum de nuits')

    class Meta:
        verbose_name = 'Plan tarifaire'
        verbose_name_plural = 'Plans tarifaires'
        ordering = ['-date_debut']

    def __str__(self):
        return (
            f'{self.type_chambre} — {self.canal} '
            f'({self.date_debut}→{self.date_fin})')


# ── NTHOT3 — Réservations (walk-in/téléphone/email) ─────────────────────────

class Reservation(TenantModel):
    """Réservation walk-in/téléphone/email/OTA (saisie manuelle uniquement —
    aucune intégration OTA automatique, cf. NTHOT4 gated)."""

    class Origine(models.TextChoices):
        WALK_IN = 'walk_in', 'Walk-in'
        TELEPHONE = 'telephone', 'Téléphone'
        EMAIL = 'email', 'Email'
        OTA_GATED = 'ota_gated', 'OTA (saisie manuelle)'

    class Statut(models.TextChoices):
        CONFIRMEE = 'confirmee', 'Confirmée'
        EN_ATTENTE = 'en_attente', 'En attente'
        ANNULEE = 'annulee', 'Annulée'
        NO_SHOW = 'no_show', 'No-show'
        EN_COURS = 'en_cours', 'En cours (check-in fait)'
        TERMINEE = 'terminee', 'Terminée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='hospitality_reservations',
        verbose_name='Société',
    )
    chambre = models.ForeignKey(
        Chambre,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reservations',
        verbose_name='Chambre',
    )
    type_chambre = models.ForeignKey(
        TypeChambre,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='reservations',
        verbose_name='Type de chambre (si chambre non assignée)',
    )
    origine = models.CharField(
        max_length=12, choices=Origine.choices, default=Origine.WALK_IN)
    date_arrivee = models.DateField(verbose_name="Date d'arrivée")
    date_depart = models.DateField(verbose_name='Date de départ')
    nb_adultes = models.PositiveIntegerField(default=1)
    nb_enfants = models.PositiveIntegerField(default=0)

    # Client résolu (pattern crm.resolve_client_for_lead) : soit un compte
    # CRM existant (FK string souple, jamais un import de apps.crm.models),
    # soit une saisie directe nom/téléphone si aucun compte CRM.
    client = models.ForeignKey(
        'crm.Client',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='hospitality_reservations',
        verbose_name='Client CRM',
    )
    client_nom = models.CharField(max_length=200, blank=True, default='')
    client_telephone = models.CharField(max_length=30, blank=True, default='')

    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.CONFIRMEE)
    # Prix figé au moment de la réservation (résolu via services.prix_applicable,
    # NTHOT2) — indépendant d'une évolution ultérieure des plans tarifaires.
    prix_nuit_snapshot = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='hospitality_reservations_creees',
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Réservation'
        verbose_name_plural = 'Réservations'
        ordering = ['-date_arrivee']

    def __str__(self):
        return f'Réservation #{self.pk} ({self.date_arrivee}→{self.date_depart})'

    @property
    def nb_nuits(self):
        return max((self.date_depart - self.date_arrivee).days, 0)


# ── NTHOT5 — Fiche de police marocaine (check-in) ───────────────────────────

class FicheClient(TenantModel):
    """Fiche de police par occupant (réglementation police des étrangers/
    nationaux), requise pour le check-in — un occupant sans fiche complète
    bloque l'action ``check-in``."""

    class TypePiece(models.TextChoices):
        CIN = 'cin', 'CIN'
        PASSEPORT = 'passeport', 'Passeport'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='hospitality_fiches_client',
        verbose_name='Société',
    )
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,  # on_delete: cascade parent→enfant (composant du parent)
        related_name='fiches_client',
        verbose_name='Réservation',
    )
    nom_complet = models.CharField(max_length=200)
    nationalite = models.CharField(max_length=100)
    type_piece = models.CharField(max_length=10, choices=TypePiece.choices)
    numero_piece = models.CharField(max_length=50)
    date_naissance = models.DateField()
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Fiche de police'
        verbose_name_plural = 'Fiches de police'
        ordering = ['id']

    def __str__(self):
        return self.nom_complet


# ── NTHOT7 — Folio client unifié ────────────────────────────────────────────

class Folio(TenantModel):
    """Folio client : toutes les lignes facturables d'un séjour (nuitées,
    extras, restaurant, taxe de séjour) avant clôture en UNE facture ventes
    consolidée (``services.cloturer_folio``, via ``apps.ventes.services``,
    jamais un import du modèle Facture)."""

    class Statut(models.TextChoices):
        OUVERT = 'ouvert', 'Ouvert'
        SOLDE = 'solde', 'Soldé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='hospitality_folios',
        verbose_name='Société',
    )
    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.CASCADE,  # on_delete: cascade parent→enfant (composant du parent)
        related_name='folio',
        verbose_name='Réservation',
    )
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.OUVERT)
    # ID de la Facture ventes consolidée, posée à la clôture — identifiant
    # souple (jamais un import de apps.ventes.models sur ce champ).
    facture_id = models.PositiveIntegerField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_cloture = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Folio'
        verbose_name_plural = 'Folios'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Folio #{self.pk} — réservation #{self.reservation_id}'

    @property
    def total_ht(self):
        return sum(
            (ligne.montant_ht for ligne in self.lignes.all()), Decimal('0'))


class LigneFolio(models.Model):
    """Ligne facturable du folio (nuitée/extra/restaurant/taxe de séjour)."""

    class Origine(models.TextChoices):
        NUITEE = 'nuitee', 'Nuitée'
        EXTRA = 'extra', 'Extra'
        RESTAURANT = 'restaurant', 'Restaurant'
        TAXE_SEJOUR = 'taxe_sejour', 'Taxe de séjour'

    folio = models.ForeignKey(
        Folio, on_delete=models.CASCADE,  # on_delete: cascade parent→enfant (composant du parent)
        related_name='lignes')
    origine = models.CharField(max_length=15, choices=Origine.choices)
    description = models.CharField(max_length=255, blank=True, default='')
    montant_ht = models.DecimalField(max_digits=10, decimal_places=2)
    tva = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('20'))
    # Origine documentaire souple (ex. 'pos.VenteComptoir') — jamais un import
    # direct du modèle source ; résolu via le selector de l'app cible.
    source_type = models.CharField(max_length=30, blank=True, default='')
    source_id = models.PositiveIntegerField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ligne de folio'
        verbose_name_plural = 'Lignes de folio'
        ordering = ['id']

    def __str__(self):
        return f'{self.origine} — {self.montant_ht}'


# ── NTHOT8 — Taxe de séjour paramétrable ───────────────────────────────────

class ParametresTaxeSejour(TenantModel):
    """Paramètres de taxe de séjour, une ligne par société. Appliquée
    automatiquement à la clôture du folio (``services.cloturer_folio``)."""

    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='hospitality_parametres_taxe_sejour',
        verbose_name='Société',
    )
    montant_par_nuit_par_personne = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0'))
    exoneration_enfants = models.BooleanField(default=True)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Paramètres taxe de séjour'
        verbose_name_plural = 'Paramètres taxe de séjour'

    def __str__(self):
        return f'Taxe de séjour — {self.company}'


# ── NTHOT9 — Housekeeping ───────────────────────────────────────────────────

class TacheMenage(TenantModel):
    """Tâche de ménage assignée à une femme/homme de chambre. Créée
    automatiquement au check-out (``services.check_out``, type ``depart``)."""

    class TypeTache(models.TextChoices):
        DEPART = 'depart', 'Départ'
        RECOUCHE = 'recouche', 'Recouche'
        NETTOYAGE_COMPLET = 'nettoyage_complet', 'Nettoyage complet'

    class Statut(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        EN_COURS = 'en_cours', 'En cours'
        TERMINEE = 'terminee', 'Terminée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='hospitality_taches_menage',
        verbose_name='Société',
    )
    chambre = models.ForeignKey(
        Chambre, on_delete=models.CASCADE,  # on_delete: cascade parent→enfant (composant du parent)
        related_name='taches_menage')
    type_tache = models.CharField(
        max_length=20, choices=TypeTache.choices,
        default=TypeTache.NETTOYAGE_COMPLET)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='hospitality_taches_menage',
    )
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.A_FAIRE)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_completion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Tâche de ménage'
        verbose_name_plural = 'Tâches de ménage'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.get_type_tache_display()} — {self.chambre}'
