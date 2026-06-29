"""
FG302 — Calendrier de disponibilité des ressources terrain.

``IndisponibiliteRessource`` enregistre, sur une fenêtre de dates [date_debut,
date_fin] INCLUSIVE, l'INDISPONIBILITÉ d'une ressource terrain — un TECHNICIEN
(un utilisateur) OU une CAMIONNETTE (un ``stock.EmplacementStock``) — pour cause
de congé, formation, arrêt (maladie/panne) ou autre. C'est le pendant
« absence » du plan de charge (FG299), de la détection de conflits (FG300) et du
nivellement (FG301) : ces sélecteurs peuvent EXCLURE une ressource indisponible
via ``selectors.ressource_indisponible``.

Couche INDÉPENDANTE des trois couches de statuts de l'OS (entonnoir STAGES.py,
statut document ventes, statut chantier) : une indisponibilité ne touche AUCUN
statut. Son enum de type est PROPRE à l'app installations (jamais STAGES.py).

Additif & multi-tenant : on AJOUTE une table avec une FK ``company`` posée côté
serveur. À NE PAS confondre avec ``gestion_projet.Indisponibilite`` (ressources
de PROGRAMME) — celle-ci vise les ressources TERRAIN des interventions.
"""
from django.conf import settings
from django.db import models


class IndisponibiliteRessource(models.Model):
    """FG302 — créneau d'indisponibilité d'une ressource terrain (technicien OU
    camionnette) sur [date_debut, date_fin] inclusive.

    Exactement UNE des deux cibles doit être renseignée : soit ``technicien``
    (un utilisateur), soit ``camionnette`` (un ``stock.EmplacementStock``). Au
    moins une, jamais les deux à la fois (garde ``clean()``). ``type_indispo``
    ventile le motif (congé / formation / arrêt / autre). Multi-tenant : la
    société est posée côté serveur, jamais lue du corps de la requête."""

    class Type(models.TextChoices):
        CONGE = 'conge', 'Congé'
        FORMATION = 'formation', 'Formation'
        ARRET = 'arret', 'Arrêt (maladie / panne)'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_indispos')
    # Cible TECHNICIEN (nullable) — un utilisateur indisponible.
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_indispos')
    # Cible CAMIONNETTE (nullable) — un emplacement de stock (dépôt/camionnette).
    # String-FK : les modèles stock ne sont jamais importés (couplage lâche).
    camionnette = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_indispos')
    # max_length=10 couvre le plus long code de Type ('formation' = 9).
    type_indispo = models.CharField(
        max_length=10, choices=Type.choices, default=Type.CONGE)
    date_debut = models.DateField()
    date_fin = models.DateField()
    motif = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_indispos_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Indisponibilité de ressource'
        verbose_name_plural = 'Indisponibilités de ressource'
        ordering = ['-date_debut', '-date_creation']
        indexes = [
            # Nom ≤ 30 caractères (contrainte Django/Postgres).
            models.Index(fields=['company', 'technicien'],
                         name='idx_indispo_co_tech'),
            models.Index(fields=['company', 'camionnette'],
                         name='idx_indispo_co_camion'),
            models.Index(fields=['company', 'date_debut', 'date_fin'],
                         name='idx_indispo_co_dates'),
        ]

    def __str__(self):
        cible = self.technicien_id or f'camion#{self.camionnette_id}'
        return (f'{self.get_type_indispo_display()} · {cible} · '
                f'{self.date_debut}→{self.date_fin}')

    def clean(self):
        """Garde métier : exactement UNE cible (technicien XOR camionnette) et
        dates dans le bon ordre (``date_fin`` ≥ ``date_debut``)."""
        from django.core.exceptions import ValidationError
        errors = {}
        has_tech = self.technicien_id is not None
        has_camion = self.camionnette_id is not None
        if not has_tech and not has_camion:
            errors['technicien'] = (
                'Indiquez une ressource (technicien ou camionnette).')
        elif has_tech and has_camion:
            errors['camionnette'] = (
                'Une indisponibilité vise UNE seule ressource '
                '(technicien OU camionnette, pas les deux).')
        if (self.date_debut is not None and self.date_fin is not None
                and self.date_fin < self.date_debut):
            errors['date_fin'] = (
                'La date de fin doit être postérieure ou égale à la date de '
                'début.')
        if errors:
            raise ValidationError(errors)
