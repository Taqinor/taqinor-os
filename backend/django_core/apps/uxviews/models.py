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
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
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


class FavoriUtilisateur(TenantModel):
    """NTUX12 — un enregistrement épinglé par UN utilisateur.

    Strictement PERSONNEL : un favori n'est jamais visible ni modifiable par un
    autre utilisateur, même de la même société (critère d'acceptation NTUX12).

    GÉNÉRIQUE : la cible est pointée par `contenttypes` (`content_type` +
    `object_id`) — un favori peut donc viser n'importe quel écran de détail
    (Lead, Devis, Client, Chantier, Ticket…) sans que `uxviews` importe une
    seule app métier. Le libellé n'est PAS stocké : il est résolu à la lecture
    depuis la cible (jamais un snapshot qui dériverait après un renommage).

    `ordre` porte le glisser-déposer de la liste (NTUX21) : petit = en tête.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        # on_delete: composition — un favori n'a aucun sens sans son
        # propriétaire (donnée strictement personnelle, jamais transférée).
        on_delete=models.CASCADE,
        related_name='favoris',
    )
    content_type = models.ForeignKey(
        ContentType,
        # on_delete: composition — sans son type, la cible n'est plus résoluble.
        on_delete=models.CASCADE,
        related_name='+', verbose_name='Type de la cible',
    )
    object_id = models.PositiveIntegerField('Identifiant de la cible')
    cible = GenericForeignKey('content_type', 'object_id')
    ordre = models.PositiveIntegerField('Ordre', default=0)

    class Meta:
        verbose_name = 'Favori'
        verbose_name_plural = 'Favoris'
        ordering = ['ordre', 'id']
        constraints = [
            # Épingler deux fois le même enregistrement est un no-op, pas un
            # doublon. Scopé société ET propriétaire (deux utilisateurs peuvent
            # épingler le même chantier).
            models.UniqueConstraint(
                fields=['company', 'owner', 'content_type', 'object_id'],
                name='uxviews_favori_unique_par_utilisateur',
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'owner', 'ordre'],
                         name='uxviews_favori_ordre_idx'),
        ]

    def __str__(self):
        return f'{self.cle_modele}#{self.object_id}'

    @property
    def cle_modele(self):
        """Clé du modèle cible, ex. ``'installations.installation'``."""
        if self.content_type_id is None:
            return ''
        ct = self.content_type
        return f'{ct.app_label}.{ct.model}'
