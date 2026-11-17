"""Tâches et ce qui s'y rattache (reference/donnees.md §2.3-§2.7, §2.13, §2.16)."""
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q

from apps.taches.choix import (
    AncreRappel,
    Couleur,
    Frequence,
    LienEtat,
    ModeRecurrence,
    Moment,
    Priorite,
    Source,
    SourceRappel,
    StatutRappel,
    StatutTache,
)
from apps.taches.models.base import GestionnaireNomCle, StrNeutreMixin, poser_nom_cle
from core.champs_plateforme import VerrouOptimisteMixin
from core.models import SoftDeleteModel, TenantModel


class Etiquette(StrNeutreMixin, TenantModel):
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles
    nom = models.CharField(max_length=40)
    nom_cle = models.CharField(max_length=40, editable=False)
    couleur = models.CharField(max_length=16, choices=Couleur.choices, default=Couleur.CIEL)

    objects = GestionnaireNomCle()

    class Meta:
        verbose_name = 'étiquette'
        verbose_name_plural = 'étiquettes'
        constraints = [
            models.UniqueConstraint(fields=['company', 'proprietaire', 'nom_cle'], name='taches_etiq_nom_uniq'),
        ]

    def save(self, *args, **kwargs):
        poser_nom_cle(self, kwargs)
        super().save(*args, **kwargs)


class RegleRecurrence(StrNeutreMixin, TenantModel):
    """Règle d'une tâche récurrente ; « Arrêter » = `actif=False`."""

    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles
    frequence = models.CharField(max_length=12, choices=Frequence.choices)
    intervalle = models.PositiveSmallIntegerField(default=1)
    jours_semaine = models.CharField(max_length=7, default='0000000')
    jour_du_mois = models.SmallIntegerField(null=True, blank=True)
    rang_dans_mois = models.SmallIntegerField(null=True, blank=True)
    mode = models.CharField(max_length=12, choices=ModeRecurrence.choices, default=ModeRecurrence.CALENDRIER)
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'règle de récurrence'
        verbose_name_plural = 'règles de récurrence'


class Tache(StrNeutreMixin, TenantModel, SoftDeleteModel, VerrouOptimisteMixin):
    """Tâche personnelle. Suppression : TOUJOURS `soft_delete(user, record=False)`."""

    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles, suivent le compte
    projet = models.ForeignKey(
        'taches.Projet', on_delete=models.CASCADE,  # on_delete: composition, la purge du projet emporte ses tâches
        null=True, blank=True)
    section = models.ForeignKey(
        'taches.Section', on_delete=models.SET_NULL,  # on_delete: étape supprimée → « Sans étape »
        null=True, blank=True)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,  # on_delete: composition
        null=True, blank=True, related_name='enfants')
    titre = models.CharField(max_length=280)
    notes = models.TextField(blank=True, default='')
    statut = models.CharField(max_length=12, choices=StatutTache.choices, default=StatutTache.A_FAIRE)
    en_attente_de = models.CharField(max_length=200, blank=True, default='')
    priorite = models.PositiveSmallIntegerField(choices=Priorite.choices, default=Priorite.AUCUNE)
    jour_prevu = models.DateField(null=True, blank=True)
    moment = models.CharField(max_length=12, choices=Moment.choices, blank=True, default='')
    heure_debut = models.TimeField(null=True, blank=True)
    echeance = models.DateField(null=True, blank=True)
    echeance_heure = models.TimeField(null=True, blank=True)
    quelque_jour = models.BooleanField(default=False)
    estimation_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    duree_reelle_minutes = models.PositiveIntegerField(null=True, blank=True)
    rang_projet = models.IntegerField(null=True, blank=True)
    rang_jour = models.IntegerField(null=True, blank=True)
    premier_jour_prevu = models.DateField(null=True, blank=True)
    reports = models.PositiveSmallIntegerField(default=0)
    reports_tranches = models.PositiveSmallIntegerField(default=0)
    triee_le = models.DateTimeField(null=True, blank=True)
    client_id = models.CharField(max_length=64, null=True, blank=True)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.MANUEL)
    jalon = models.BooleanField(default=False)
    bloquee_par = models.ForeignKey(
        'self', on_delete=models.SET_NULL,  # on_delete: prérequis purgé → débloquée
        null=True, blank=True, related_name='bloque')
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL,  # on_delete: lien perdu, tâche gardée
        null=True, blank=True, related_name='+')
    object_id = models.PositiveIntegerField(null=True, blank=True)
    lien_libelle = models.CharField(max_length=200, blank=True, default='')
    lien_etat = models.CharField(max_length=12, choices=LienEtat.choices, blank=True, default='')
    lien_verifie_le = models.DateTimeField(null=True, blank=True)
    activite_origine = models.ForeignKey(
        'records.Activity', on_delete=models.SET_NULL,  # on_delete: activité purgée, tâche gardée
        null=True, blank=True, related_name='+')
    recurrence = models.ForeignKey(
        RegleRecurrence, on_delete=models.SET_NULL,  # on_delete: règle supprimée, occurrences gardées
        null=True, blank=True)
    occurrence_du = models.DateField(null=True, blank=True)
    confidentiel = models.BooleanField(default=False)
    fait_le = models.DateTimeField(null=True, blank=True)
    annule_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'tâche'
        verbose_name_plural = 'tâches'
        ordering = ['rang_projet', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'proprietaire', 'client_id'],
                condition=Q(client_id__isnull=False, is_deleted=False),
                name='taches_tache_cli_uniq'),
            models.UniqueConstraint(
                fields=['company', 'activite_origine'],
                condition=Q(activite_origine__isnull=False, is_deleted=False),
                name='taches_tache_act_uniq'),
            models.UniqueConstraint(
                fields=['company', 'recurrence', 'occurrence_du'],
                condition=Q(recurrence__isnull=False, occurrence_du__isnull=False, is_deleted=False),
                name='taches_tache_occ_uniq'),
            models.CheckConstraint(
                condition=Q(heure_debut__isnull=True) | Q(jour_prevu__isnull=False),
                name='taches_heure_sans_jour_ck'),
            models.CheckConstraint(
                condition=Q(echeance_heure__isnull=True) | Q(echeance__isnull=False),
                name='taches_ech_heure_ck'),
        ]
        indexes = [
            models.Index(fields=['company', 'proprietaire', 'statut', 'jour_prevu'], name='taches_tache_jour_idx'),
            models.Index(fields=['company', 'proprietaire', 'statut', 'echeance'], name='taches_tache_ech_idx'),
            models.Index(fields=['projet', 'section', 'rang_projet'], name='taches_tache_proj_idx'),
            models.Index(fields=['company', 'proprietaire', 'fait_le'], name='taches_tache_fait_idx'),
            models.Index(fields=['company', 'proprietaire', 'projet', 'triee_le'], name='taches_tache_boite_idx'),
            models.Index(fields=['company', 'proprietaire', 'bloquee_par'], name='taches_tache_bloq_idx'),
            models.Index(
                fields=['company', 'proprietaire', 'content_type', 'object_id'], name='taches_tache_lien_idx'),
            models.Index(fields=['company', 'is_deleted', 'deleted_at'], name='taches_tache_purge_idx'),
        ]


class ElementChecklist(StrNeutreMixin, TenantModel):
    tache = models.ForeignKey(Tache, on_delete=models.CASCADE)  # on_delete: composition
    libelle = models.CharField(max_length=255)
    fait = models.BooleanField(default=False)
    fait_le = models.DateTimeField(null=True, blank=True)
    rang = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'élément de check-list'
        verbose_name_plural = 'éléments de check-list'
        indexes = [
            models.Index(fields=['tache', 'rang'], name='taches_check_rang_idx'),
        ]


class EtiquetteTache(StrNeutreMixin, TenantModel):
    tache = models.ForeignKey(Tache, on_delete=models.CASCADE)  # on_delete: composition
    etiquette = models.ForeignKey(
        Etiquette, on_delete=models.CASCADE)  # on_delete: étiquette supprimée → retirée des tâches

    class Meta:
        verbose_name = 'étiquette de tâche'
        verbose_name_plural = 'étiquettes de tâche'
        constraints = [
            models.UniqueConstraint(fields=['company', 'tache', 'etiquette'], name='taches_etiqt_uniq'),
        ]


class Rappel(StrNeutreMixin, TenantModel):
    """Rappel d'une tâche, à l'heure murale (`jour`, `heure`)."""

    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles
    tache = models.ForeignKey(Tache, on_delete=models.CASCADE)  # on_delete: composition
    ancre = models.CharField(max_length=12, choices=AncreRappel.choices, blank=True, default='')
    decalage_jours = models.SmallIntegerField(default=0)
    jour = models.DateField()
    heure = models.TimeField()
    statut = models.CharField(max_length=12, choices=StatutRappel.choices, default=StatutRappel.EN_ATTENTE)
    envoye_le = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=12, choices=SourceRappel.choices, default=SourceRappel.MANUEL)

    class Meta:
        verbose_name = 'rappel'
        verbose_name_plural = 'rappels'
        indexes = [
            models.Index(
                fields=['company', 'jour', 'heure'],
                condition=Q(statut=StatutRappel.EN_ATTENTE),
                name='taches_rappel_du_idx'),
            models.Index(fields=['company', 'tache'], name='taches_rappel_tache_idx'),
        ]


class VueEnregistree(StrNeutreMixin, TenantModel):
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles
    nom = models.CharField(max_length=60)
    filtres = models.JSONField(default=dict, blank=True)
    rang = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'vue enregistrée'
        verbose_name_plural = 'vues enregistrées'
        constraints = [
            models.UniqueConstraint(fields=['company', 'proprietaire', 'nom'], name='taches_vue_nom_uniq'),
        ]
