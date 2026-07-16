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
