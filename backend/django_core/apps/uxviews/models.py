"""NTUX — Vues sauvegardées serveur, personnelles et partagées (fondation
minimale requise par NTUX2/3/4/5/6/8/10/11 : la couche serveur+partage que
`useSavedViews` (localStorage, un écran à la fois) n'a jamais eue).

MULTI-TENANT : `SavedView` hérite de `core.models.TenantModel` (FK `company` +
timestamps) — jamais lue/écrite depuis le corps de requête (TenantMixin).
Cross-app : FK `role` vers `roles.Role` en STRING REFERENCE (jamais
d'import de `apps.roles.models`), conformément à la frontière inter-apps
(CLAUDE.md — lecture via selectors, jamais un import de modèle étranger).
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class SavedView(TenantModel):
    """Vue nommée pour un écran donné (`ecran`, ex. 'crm.leads'), portant sa
    configuration (filtres/tri/colonnes/groupement — NTUX3/4/19) en JSON.
    Personnelle par défaut ; visible par toute l'équipe (même société) quand
    `visibilite=EQUIPE`. Au plus une vue « défaut du rôle » active par
    (company, ecran, role) — appliquée automatiquement au chargement d'un
    écran quand l'utilisateur n'a pas de préférence personnelle (NTUX2)."""

    class Visibilite(models.TextChoices):
        PERSONNELLE = 'PERSONNELLE', 'Personnelle'
        EQUIPE = 'EQUIPE', "Partagée à l'équipe"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  # on_delete: composition (utilisateur)
        related_name='saved_views',
    )
    # Identifiant stable d'écran côté frontend, ex. 'crm.leads', 'ventes.devis'.
    ecran = models.CharField(max_length=80)
    nom = models.CharField(max_length=120)
    # {filtres, tri, colonnes_visibles, groupement, densite?} — NTUX1/3/4/17/19.
    configuration = models.JSONField(default=dict, blank=True)
    visibilite = models.CharField(
        max_length=12, choices=Visibilite.choices, default=Visibilite.PERSONNELLE,
    )
    est_defaut_role = models.BooleanField(default=False)
    # STRING FK — jamais d'import de apps.roles.models (frontière inter-apps).
    role = models.ForeignKey(
        'roles.Role', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='saved_views_defaut',
    )

    class Meta:
        verbose_name = 'Vue sauvegardée'
        verbose_name_plural = 'Vues sauvegardées'
        ordering = ['ecran', 'nom']

    def __str__(self):
        return f'{self.ecran} — {self.nom}'
