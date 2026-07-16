"""Modèles du module Hôtellerie & restauration (`apps.hospitality`).

Vertical vendable à un hôtel/riad/groupe resto marocain (Groupe NTHOT,
`docs/plans/PLAN_VERTICALS.md`). Multi-société stricte : chaque modèle porte
un FK ``company`` posé côté serveur (jamais lu du corps de requête). Liens
vers d'autres apps métier (crm, ventes, sav) passent par des FK string
('app.Model') ou par des identifiants souples (`*_id`) résolus via les
selectors/services de l'app cible — jamais un import direct de leurs modèles.
"""
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
