"""Modèles du module Hôtellerie & restauration (`apps.hospitality`).

Vertical vendable à un hôtel/riad/groupe resto marocain (Groupe NTHOT,
`docs/plans/PLAN_VERTICALS.md`). Multi-société stricte : chaque modèle porte
un FK ``company`` posé côté serveur (jamais lu du corps de requête). Liens
vers d'autres apps métier (crm, ventes, sav) passent par des FK string
('app.Model') ou par des identifiants souples (`*_id`) résolus via les
selectors/services de l'app cible — jamais un import direct de leurs modèles.
"""
from django.conf import settings
from django.db import models


# ── NTHOT1 — Plan des chambres / unités ─────────────────────────────────────

class TypeChambre(models.Model):
    """Catégorie de chambre (Standard/Suite/Riad-suite…)."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
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


class Chambre(models.Model):
    """Chambre/unité physique de l'établissement."""

    class Statut(models.TextChoices):
        LIBRE = 'libre', 'Libre'
        OCCUPEE = 'occupee', 'Occupée'
        SALE = 'sale', 'Sale'
        EN_NETTOYAGE = 'en_nettoyage', 'En nettoyage'
        HORS_SERVICE = 'hors_service', 'Hors service'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
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

class PlanTarifaire(models.Model):
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
        on_delete=models.CASCADE,
        related_name='hospitality_plans_tarifaires',
        verbose_name='Société',
    )
    type_chambre = models.ForeignKey(
        TypeChambre,
        on_delete=models.CASCADE,
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

class Reservation(models.Model):
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
        on_delete=models.CASCADE,
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
