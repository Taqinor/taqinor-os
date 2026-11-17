"""Suggestions de tâches venues de l'ERP (reference/donnees.md §2.19, A4).

`titre_propose` vient d'un gabarit SANS nom de client ; destinataire strict = `proprietaire`.
"""
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.taches.choix import FamilleSuggestion, StatutSuggestion
from apps.taches.models.base import StrNeutreMixin
from core.models import TenantModel


class SuggestionTache(StrNeutreMixin, TenantModel):
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles
    famille = models.CharField(max_length=24, choices=FamilleSuggestion.choices)
    cle = models.CharField(max_length=80)
    titre_propose = models.CharField(max_length=200)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL,  # on_delete: suggestion gardée jusqu'à sa purge
        null=True, blank=True, related_name='+')
    object_id = models.PositiveIntegerField(null=True, blank=True)
    lead_ref = models.PositiveIntegerField(null=True, blank=True)
    statut = models.CharField(max_length=12, choices=StatutSuggestion.choices, default=StatutSuggestion.PROPOSEE)
    tache = models.ForeignKey(
        'taches.Tache', on_delete=models.SET_NULL,  # on_delete: tâche purgée, trace gardée
        null=True, blank=True)
    decidee_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'suggestion de tâche'
        verbose_name_plural = 'suggestions de tâche'
        constraints = [
            models.UniqueConstraint(fields=['company', 'proprietaire', 'cle'], name='taches_sugg_cle_uniq'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'proprietaire', 'statut', 'created_at'], name='taches_sugg_boite_idx'),
        ]
