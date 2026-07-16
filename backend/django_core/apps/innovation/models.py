"""Modèles du module Innovation & boucle de feedback produit (`apps.innovation`).

Trois étages (voir docs/new_tasks_plan.md, Groupe NTIDE) :

1. Boîte à idées interne — ``Idee`` (NTIDE1), suivi de ``VoteIdee`` (NTIDE2).
2. Campagnes d'innovation ciblées — hors périmètre de ce lot (NTIDE25+).
3. Canal feedback produit in-app — hors périmètre de ce lot (NTIDE36+).

Multi-société : tous les modèles héritent de ``core.models.TenantModel``
(FK ``company`` + ``created_at``/``updated_at``), jamais une FK ``company``
à la main (SCA4).
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class Idee(TenantModel):
    """Une idée proposée par un collaborateur (NTIDE1).

    ``linked_type``/``linked_id`` forment une référence OPAQUE (string-FK)
    vers un devis/ticket SAV/chantier — jamais un import cross-app des
    modèles ``ventes``/``sav``/``installations``.
    """

    class Statut(models.TextChoices):
        OUVERT = 'ouvert', 'Ouvert'
        EXAMINEE = 'examinee', 'Examinée'
        RETENUE = 'retenue', 'Retenue'
        REALISEE = 'realisee', 'Réalisée'
        FERMEE = 'fermee', 'Fermée'

    # Statuts qui ne sont plus modifiables (terminal du point de vue de la
    # machine à états des actions NTIDE5 — cf. ``apps.innovation.views``).
    STATUTS_ACTIFS = (Statut.OUVERT, Statut.EXAMINEE, Statut.RETENUE)

    class LinkedType(models.TextChoices):
        DEVIS = 'devis', 'Devis'
        TICKET = 'ticket', 'Ticket SAV'
        CHANTIER = 'chantier', 'Chantier'

    # Redéclaré à l'identique (ARC1) : related_name explicite dédié.
    company = models.ForeignKey(
        'authentication.Company',
        # on_delete: idées scopées société — disparaissent avec elle (nettoyage tenant standard).
        on_delete=models.CASCADE,
        related_name='innovation_idees', verbose_name='Société')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='idees_proposees',
        verbose_name='Auteur')
    titre = models.CharField(max_length=255, verbose_name='Titre')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    # Libre (ex. « SAV », « Devis », « Stock »…) — PAS une liste fermée :
    # NTIDE10 propose les 5 valeurs les plus fréquentes en autocomplétion.
    contexte = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Contexte')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.OUVERT,
        verbose_name='Statut')
    # Dénormalisé : maintenu par VoteIdee.save()/delete() (NTIDE2), jamais
    # recalculé à la lecture — évite un COUNT() sur chaque ligne de liste.
    votes_count = models.PositiveIntegerField(
        default=0, verbose_name='Votes (dénormalisé)')
    linked_type = models.CharField(
        max_length=10, choices=LinkedType.choices, blank=True, default='',
        verbose_name='Type lié (devis/ticket/chantier)')
    linked_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID lié (opaque)')

    class Meta:
        verbose_name = 'Idée'
        verbose_name_plural = 'Idées'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='innovation_idee_co_statut'),
            models.Index(fields=['company', 'contexte'],
                         name='innovation_idee_co_ctx'),
        ]

    def __str__(self):
        return self.titre


class VoteIdee(TenantModel):
    """Un vote d'un utilisateur pour une idée (NTIDE2) — unique par (idee,
    votant). L'auteur de l'idée ne peut pas voter pour sa propre idée (règle
    appliquée côté vue, cf. ``apps.innovation.views.VoteIdeeViewSet``)."""

    company = models.ForeignKey(
        'authentication.Company',
        # on_delete: votes scopés société — disparaissent avec elle (nettoyage tenant standard).
        on_delete=models.CASCADE,
        related_name='innovation_votes', verbose_name='Société')
    idee = models.ForeignKey(
        Idee,
        # on_delete: un vote n'existe que rattaché à son idée (composition).
        on_delete=models.CASCADE,
        related_name='votes', verbose_name='Idée')
    votant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        # on_delete: vote sans valeur historique isolée — disparaît avec le compte votant.
        on_delete=models.CASCADE,
        related_name='votes_idees', verbose_name='Votant')

    class Meta:
        verbose_name = 'Vote idée'
        verbose_name_plural = 'Votes idée'
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['idee', 'votant'],
                name='innovation_vote_unique_idee_votant'),
        ]

    def __str__(self):
        return f'{self.votant_id} → idée {self.idee_id}'
