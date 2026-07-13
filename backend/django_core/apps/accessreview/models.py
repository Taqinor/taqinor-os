"""Modèles de la gouvernance des accès (NTSEC19).

* ``AccessReviewCampaign`` — une campagne de revue d'accès (périmètre, dates,
  statut).
* ``AccessReviewItem`` — un item par utilisateur du périmètre, attesté ou
  révoqué par un manager. Une révocation retire le rôle via
  ``apps.roles.services`` (jamais d'import direct de ``roles.models``).

Tout est scopé société (``TenantModel``) ; ``core`` reste fondation.
"""
from django.db import models

from core.models import TenantModel


class AccessReviewCampaign(TenantModel):
    """Campagne de revue d'accès d'une société."""

    class Perimetre(models.TextChoices):
        ALL = 'all', 'Tous les comptes'
        ROLE = 'role', 'Par rôle'
        MODULE = 'module', 'Par module'

    class Statut(models.TextChoices):
        OUVERTE = 'ouverte', 'Ouverte'
        CLOSE = 'close', 'Close'

    nom = models.CharField(max_length=160, verbose_name='Nom')
    perimetre = models.CharField(
        max_length=10, choices=Perimetre.choices, default=Perimetre.ALL)
    # Référence du périmètre : id de rôle (perimetre=role) ou clé module.
    perimetre_ref = models.CharField(max_length=64, blank=True, default='')
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.OUVERTE)

    class Meta:
        verbose_name = "Campagne de revue d'accès"
        verbose_name_plural = "Campagnes de revue d'accès"
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.nom} ({self.statut})'


class AccessReviewItem(TenantModel):
    """Un item de revue : un compte à attester/révoquer dans une campagne."""

    class Decision(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        MAINTENU = 'maintenu', 'Maintenu'
        REVOQUE = 'revoque', 'Révoqué'

    campagne = models.ForeignKey(
        AccessReviewCampaign,
        on_delete=models.CASCADE,  # on_delete: un item n'existe que dans sa campagne (composition)
        related_name='items')
    user = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.CASCADE,  # on_delete: item de revue rattaché au compte; disparaît avec lui
        related_name='access_review_items')
    # Instantané du rôle au lancement (survit à un changement ultérieur).
    role_snapshot = models.JSONField(default=dict, blank=True)
    reviewer = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='access_reviews_faites')
    decision = models.CharField(
        max_length=12, choices=Decision.choices, default=Decision.EN_ATTENTE)
    commentaire = models.TextField(blank=True, default='')
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Item de revue d'accès"
        verbose_name_plural = "Items de revue d'accès"
        constraints = [
            models.UniqueConstraint(
                fields=['campagne', 'user'],
                name='uniq_accessreview_item_par_campagne_user'),
        ]

    def __str__(self):
        return f'Item({self.campagne_id}, user={self.user_id}, {self.decision})'


class SodRule(TenantModel):
    """Règle de séparation des tâches (SoD) — paire de permissions en conflit.

    Deux permissions qu'un même utilisateur ne devrait jamais cumuler (ex.
    « saisir facture » + « valider paiement »). ``severite=critique`` peut
    BLOQUER l'attribution du rôle qui créerait le cumul (via
    ``apps.roles.services``). Scopé société.
    """

    class Severite(models.TextChoices):
        INFO = 'info', 'Information'
        WARNING = 'warning', 'Avertissement'
        CRITIQUE = 'critique', 'Critique'

    permission_a = models.CharField(max_length=100)
    permission_b = models.CharField(max_length=100)
    severite = models.CharField(
        max_length=10, choices=Severite.choices, default=Severite.WARNING)
    libelle = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        verbose_name = 'Règle SoD'
        verbose_name_plural = 'Règles SoD'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'permission_a', 'permission_b'],
                name='uniq_sodrule_par_societe_paire'),
        ]

    def __str__(self):
        return f'SoD({self.permission_a} × {self.permission_b}, {self.severite})'
