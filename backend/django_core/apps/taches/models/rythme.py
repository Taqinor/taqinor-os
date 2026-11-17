"""Le rythme : réglages typés, préférences dites, journal des sollicitations
(reference/donnees.md §2.10-§2.12).

`ReglagesRythme` n'est créée QUE par `creer_taches()` (première tâche, invariant 29) ; `vu/` ne la
crée jamais.
"""
from django.conf import settings
from django.db import models

from apps.taches.choix import (
    CanalIncitation,
    ClePreference,
    FamilleSuggestion,
    ModeRythme,
    ReponseIncitation,
    SourcePreference,
    TypeIncitationEcran,
    TypeIncitationPush,
)
from apps.taches.models.base import StrNeutreMixin
from core.models import TenantModel

#: Les trois familles de suggestions ERP allumées par défaut (A4) ; `visite_validee` est éteinte.
FAMILLES_ALLUMEES = (
    FamilleSuggestion.DEVIS_ACCEPTE,
    FamilleSuggestion.CHANTIER_RECEPTIONNE,
    FamilleSuggestion.CHANTIER_ANNULE,
)

#: `IncitationCoach.type` : les types push puis les types écran (C14), une seule énumération en base.
TYPES_INCITATION = TypeIncitationPush.choices + TypeIncitationEcran.choices


def familles_allumees():
    """Défaut APPELABLE de `ReglagesRythme.familles_suggestions` (une liste neuve par ligne)."""
    return [str(famille) for famille in FAMILLES_ALLUMEES]


class ReglagesRythme(StrNeutreMixin, TenantModel):
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles
    mode = models.CharField(max_length=12, choices=ModeRythme.choices, default=ModeRythme.POUSSER)
    comprendre_mon_rythme = models.BooleanField(default=True)
    palier = models.PositiveSmallIntegerField(null=True, blank=True)
    palier_source = models.CharField(max_length=12, blank=True, default='')
    bloc_debut = models.DateField(null=True, blank=True)
    refus_montee = models.PositiveSmallIntegerField(default=0)
    blocs_a_sauter = models.PositiveSmallIntegerField(default=0)
    echec_n = models.PositiveSmallIntegerField(default=0)
    baisse_refusee = models.BooleanField(default=False)
    essai_restant = models.BooleanField(default=False)
    meilleur_tenu = models.PositiveSmallIntegerField(null=True, blank=True)
    echec_niveau = models.PositiveSmallIntegerField(null=True, blank=True)
    ref_taille_min = models.PositiveSmallIntegerField(null=True, blank=True)
    echec_le = models.DateField(null=True, blank=True)
    tenir_fixee_le = models.DateField(null=True, blank=True)
    tenir_silence_jusquau = models.DateField(null=True, blank=True)
    tenir_reference = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    titres_notifications = models.BooleanField(default=False)
    titres_notifications_demande_le = models.DateTimeField(null=True, blank=True)
    titres_calendrier = models.BooleanField(default=True)
    titres_tuile = models.BooleanField(default=True)
    messages_sans_delai = models.BooleanField(default=False)
    rappel_avant_bloc_min = models.PositiveSmallIntegerField(null=True, blank=True)
    projet_arret_jours = models.PositiveSmallIntegerField(default=10)
    familles_suggestions = models.JSONField(default=familles_allumees, blank=True)
    suggestions_societe = models.BooleanField(default=False)
    erp_dans_journee = models.BooleanField(default=True)
    pauses_sollicitations = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = 'réglages du rythme'
        verbose_name_plural = 'réglages du rythme'
        constraints = [
            models.UniqueConstraint(fields=['company', 'proprietaire'], name='taches_reglages_uniq'),
        ]


class Preference(StrNeutreMixin, TenantModel):
    """Ce que l'utilisateur a DIT (une clé de `ClePreference`) ; clé absente = défaut."""

    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles
    cle = models.CharField(max_length=30, choices=ClePreference.choices)
    valeur = models.JSONField()
    source = models.CharField(max_length=10, choices=SourcePreference.choices, default=SourcePreference.ECRAN)
    dite_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'préférence'
        verbose_name_plural = 'préférences'
        constraints = [
            models.UniqueConstraint(fields=['company', 'proprietaire', 'cle'], name='taches_pref_cle_uniq'),
        ]


class IncitationCoach(StrNeutreMixin, TenantModel):
    """Journal des sollicitations et cartes à réponse ; aucun texte stocké (I9)."""

    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)  # on_delete: données personnelles
    jour = models.DateField()
    type = models.CharField(max_length=24, choices=TYPES_INCITATION)
    cle = models.CharField(max_length=24, blank=True, default='')
    canal = models.CharField(max_length=8, choices=CanalIncitation.choices)
    donnees = models.JSONField(default=dict, blank=True)
    montre_le = models.DateTimeField(null=True, blank=True)
    ouvert_le = models.DateTimeField(null=True, blank=True)
    repondu_le = models.DateTimeField(null=True, blank=True)
    reponse = models.CharField(max_length=24, choices=ReponseIncitation.choices, blank=True, default='')
    expire_le = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'sollicitation'
        verbose_name_plural = 'sollicitations'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'proprietaire', 'type', 'jour', 'cle'], name='taches_incit_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'proprietaire', 'jour'], name='taches_incit_jour_idx'),
        ]
