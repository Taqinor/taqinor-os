"""Projets et ce qui s'y rattache (reference/donnees.md §2.1, §2.2, §2.17, §2.18)."""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.taches.choix import Couleur, DecisionRevue, IssueProjet, Priorite, StatutProjet, Visibilite
from apps.taches.models.base import (
    GestionnaireNomCle,
    GestionnaireNomCleVivants,
    StrNeutreMixin,
    poser_nom_cle,
)
from core.champs_plateforme import VerrouOptimisteMixin
from core.models import SoftDeleteModel, TenantModel


class Projet(StrNeutreMixin, TenantModel, SoftDeleteModel, VerrouOptimisteMixin):
    """Projet personnel. Suppression : TOUJOURS `soft_delete(user, record=False)`."""

    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles, suivent le compte
    nom = models.CharField(max_length=120)
    nom_cle = models.CharField(max_length=120, editable=False)
    objectif = models.TextField(blank=True, default='')
    icone = models.CharField(max_length=8, blank=True, default='')
    couleur = models.CharField(max_length=16, choices=Couleur.choices)
    priorite = models.PositiveSmallIntegerField(choices=Priorite.choices, default=Priorite.AUCUNE)
    statut = models.CharField(max_length=12, choices=StatutProjet.choices, default=StatutProjet.ACTIF)
    statut_depuis = models.DateTimeField(default=timezone.now)
    date_debut = models.DateField(null=True, blank=True)
    echeance = models.DateField(null=True, blank=True)
    termine_le = models.DateTimeField(null=True, blank=True)
    issue = models.CharField(max_length=10, choices=IssueProjet.choices, blank=True, default='')
    bilan = models.CharField(max_length=280, blank=True, default='')
    risque = models.CharField(max_length=280, blank=True, default='')
    domaine = models.CharField(max_length=40, blank=True, default='')
    planification_le = models.DateTimeField(null=True, blank=True)
    rang = models.IntegerField(default=0)
    confidentiel = models.BooleanField(default=False)
    visibilite = models.CharField(max_length=10, choices=Visibilite.choices, default=Visibilite.PRIVE)
    affichage = models.JSONField(default=dict, blank=True)

    objects = GestionnaireNomCleVivants()
    all_objects = GestionnaireNomCle()

    class Meta:
        verbose_name = 'projet'
        verbose_name_plural = 'projets'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'proprietaire', 'nom_cle'],
                condition=Q(is_deleted=False),
                name='taches_projet_nom_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'proprietaire', 'statut'], name='taches_projet_stat_idx'),
        ]

    def save(self, *args, **kwargs):
        poser_nom_cle(self, kwargs)
        super().save(*args, **kwargs)


class Section(StrNeutreMixin, TenantModel):
    """« Étape » d'un projet. Suppression dure ; ses tâches passent « Sans étape »."""

    projet = models.ForeignKey(Projet, on_delete=models.CASCADE)  # on_delete: composition
    nom = models.CharField(max_length=120)
    nom_cle = models.CharField(max_length=120, editable=False)
    rang = models.IntegerField(default=0)
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)

    objects = GestionnaireNomCle()

    class Meta:
        verbose_name = 'étape'
        verbose_name_plural = 'étapes'
        constraints = [
            models.UniqueConstraint(fields=['company', 'projet', 'nom_cle'], name='taches_section_nom_uniq'),
        ]
        indexes = [
            models.Index(fields=['projet', 'rang'], name='taches_section_rang_idx'),
        ]

    def save(self, *args, **kwargs):
        poser_nom_cle(self, kwargs)
        super().save(*args, **kwargs)


class ModeleProjet(StrNeutreMixin, TenantModel):
    """Modèle de projet réutilisable (contenu figé, `contenu.v = 1`)."""

    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles
    nom = models.CharField(max_length=120)
    contenu = models.JSONField(default=dict, blank=True)
    cree_depuis = models.ForeignKey(
        Projet, on_delete=models.SET_NULL, null=True, blank=True)  # on_delete: le modèle survit au projet

    class Meta:
        verbose_name = 'modèle de projet'
        verbose_name_plural = 'modèles de projet'
        constraints = [
            models.UniqueConstraint(fields=['company', 'proprietaire', 'nom'], name='taches_modele_nom_uniq'),
        ]


class RevueProjet(StrNeutreMixin, TenantModel):
    """Revue hebdomadaire d'un projet (`semaine` = lundi)."""

    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE)  # on_delete: composition
    semaine = models.DateField()
    intention = models.CharField(max_length=200, blank=True, default='')
    prochaine_action = models.ForeignKey(
        'taches.Tache', on_delete=models.SET_NULL, null=True, blank=True)  # on_delete: tâche purgée, revue gardée
    decision = models.CharField(max_length=10, choices=DecisionRevue.choices, blank=True, default='')
    focus = models.BooleanField(default=False)
    faites_semaine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'revue de projet'
        verbose_name_plural = 'revues de projet'
        constraints = [
            models.UniqueConstraint(fields=['company', 'projet', 'semaine'], name='taches_revueprj_uniq'),
            models.UniqueConstraint(
                fields=['company', 'proprietaire', 'semaine'],
                condition=Q(focus=True),
                name='taches_revue_focus_uniq'),
        ]
