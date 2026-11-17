"""La journée : compteurs du jour et lignes du plan (reference/donnees.md §2.8, §2.9).

Aucun titre n'est copié ici (I6) : `PlanJour` ne garde que des nombres.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.taches.choix import CapaciteSource, Creneau, StatutJour
from apps.taches.models.base import StrNeutreMixin
from core.models import TenantModel


class PlanJour(StrNeutreMixin, TenantModel):
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles
    jour = models.DateField()
    planifie_le = models.DateTimeField(null=True, blank=True)
    cloture_le = models.DateTimeField(null=True, blank=True)
    app_ouverte_le = models.DateTimeField(null=True, blank=True)
    allege_le = models.DateTimeField(null=True, blank=True)
    reflexion = models.CharField(max_length=280, blank=True, default='')
    objectif_du_jour = models.PositiveSmallIntegerField(null=True, blank=True)
    capacite_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    capacite_source = models.CharField(max_length=12, choices=CapaciteSource.choices, blank=True, default='')
    statut_jour = models.CharField(max_length=12, choices=StatutJour.choices, blank=True, default='')
    compte_rythme = models.PositiveSmallIntegerField(default=0)
    micro_comptees = models.PositiveSmallIntegerField(default=0)
    essentiels_choisis = models.PositiveSmallIntegerField(default=0)
    essentiels_faits = models.PositiveSmallIntegerField(default=0)
    plan_prevues = models.PositiveSmallIntegerField(default=0)
    plan_faites = models.PositiveSmallIntegerField(default=0)
    minutes_prevues = models.PositiveIntegerField(default=0)
    minutes_faites = models.PositiveIntegerField(default=0)
    taille_mediane_min = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = 'plan du jour'
        verbose_name_plural = 'plans du jour'
        constraints = [
            models.UniqueConstraint(fields=['company', 'proprietaire', 'jour'], name='taches_planjour_uniq'),
        ]


class LignePlanJour(StrNeutreMixin, TenantModel):
    """Une ligne du plan : une tâche OU une activité ERP, jamais les deux."""

    plan = models.ForeignKey(PlanJour, on_delete=models.CASCADE)  # on_delete: composition
    tache = models.ForeignKey(
        'taches.Tache', on_delete=models.CASCADE,  # on_delete: composition, les compteurs restent sur PlanJour
        null=True, blank=True)
    activite_id = models.PositiveIntegerField(null=True, blank=True)
    prevue_au_plan = models.BooleanField()
    faite = models.BooleanField(default=False)
    reportee = models.BooleanField(default=False)
    essentielle = models.BooleanField(default=False)
    creneau = models.CharField(max_length=12, choices=Creneau.choices, blank=True, default='')
    rang = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = 'ligne du plan du jour'
        verbose_name_plural = 'lignes du plan du jour'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'plan', 'tache'],
                condition=Q(tache__isnull=False),
                name='taches_ligne_uniq'),
            models.UniqueConstraint(
                fields=['company', 'plan', 'activite_id'],
                condition=Q(activite_id__isnull=False),
                name='taches_ligne_act_uniq'),
            models.CheckConstraint(
                condition=(Q(tache__isnull=False, activite_id__isnull=True)
                           | Q(tache__isnull=True, activite_id__isnull=False)),
                name='taches_ligne_cible_ck'),
        ]
