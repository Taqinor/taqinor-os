"""Modèles du module « fidelite » (Groupe NTRET) — programme de fidélité par
points, paliers et carte dématérialisée.

MULTI-TENANT : tout modèle hérite de ``core.models.TenantModel`` (FK
``company`` + horodatage, ARC1) — la société est TOUJOURS posée côté serveur,
jamais lue d'un corps de requête.

Frontière inter-app (CLAUDE.md) : le lien vers le client passe par une FK À
CHAÎNE ``'crm.Client'`` — jamais un import direct de ``apps.crm.models``.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TenantModel


class ProgrammeFidelite(TenantModel):
    """Configuration du programme de fidélité par points d'une société.

    Un seul programme ACTIF (``actif=True``) par société à la fois — imposé
    par une contrainte d'unicité PARTIELLE en base (voir ``Meta.constraints``),
    jamais un check applicatif contournable par une course. Un programme
    désactivé = aucun mouvement de points créé (NTRET9,
    ``services.crediter_points_pour_vente`` no-op).
    """

    nom = models.CharField(max_length=150, default='Programme fidélité')
    actif = models.BooleanField(default=False)
    points_par_mad = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('1.00'),
        help_text='Points crédités par MAD TTC dépensé.')
    valeur_mad_par_point = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal('0.10'),
        help_text=(
            "Valeur (MAD) d'un point à la dépense — affichage seul, aucune "
            "dépense de points n'est câblée par ce lot (NTRET9)."))

    class Meta:
        verbose_name = 'Programme de fidélité'
        verbose_name_plural = 'Programmes de fidélité'
        ordering = ['-actif', 'nom']
        constraints = [
            # Un seul programme actif par société — index unique partiel
            # (PostgreSQL), pas de race possible même en écriture concurrente.
            models.UniqueConstraint(
                fields=['company'], condition=models.Q(actif=True),
                name='uniq_programmefidelite_company_actif'),
        ]

    def __str__(self):
        return f'{self.nom} ({"actif" if self.actif else "inactif"})'


class CompteFidelite(TenantModel):
    """Compte fidélité d'un client (1-1) — solde de points courant.

    Naît automatiquement au premier crédit de points
    (``services.crediter_points_pour_vente``), jamais d'une création
    manuelle via l'API (voir ``views.CompteFideliteViewSet``, lecture seule).
    """

    client = models.OneToOneField(
        'crm.Client', on_delete=models.CASCADE,
        related_name='compte_fidelite')
    solde_points = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Compte de fidélité'
        verbose_name_plural = 'Comptes de fidélité'
        ordering = ['-created_at']

    def __str__(self):
        return f'Fidélité #{self.client_id} — {self.solde_points} pts'


class MouvementFidelite(TenantModel):
    """Ligne de mouvement (gain/dépense/ajustement) sur un compte fidélité.

    ``source_type``/``source_id`` référencent l'objet d'origine (ex. une
    ``pos.VenteComptoir`` ou une ``ventes.Facture``) par un ENTIER opaque —
    jamais une FK cross-app (même patron que
    ``contrats.Contrat.sav_contrat_maintenance_id``).
    """

    class TypeMouvement(models.TextChoices):
        GAIN = 'gain', 'Gain'
        DEPENSE = 'depense', 'Dépense'
        AJUSTEMENT = 'ajustement', 'Ajustement manuel'

    compte = models.ForeignKey(
        CompteFidelite, on_delete=models.CASCADE, related_name='mouvements')
    type_mouvement = models.CharField(
        max_length=12, choices=TypeMouvement.choices)
    points = models.IntegerField(
        help_text='Positif pour un gain, négatif pour une dépense/reprise.')
    source_type = models.CharField(
        max_length=30, blank=True, default='',
        help_text=(
            "Origine du mouvement (ex. 'vente_comptoir', 'facture', "
            "'parrainage', 'manuel')."))
    source_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Référence à l'objet source (id brut, jamais une FK cross-app).")
    montant_source = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text=(
            'Montant TTC de la vente ayant généré ce gain (sert au calcul du '
            "CA cumulé pour les paliers NTRET10)."))
    motif = models.CharField(max_length=255, blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mouvements_fidelite_crees')

    class Meta:
        verbose_name = 'Mouvement de fidélité'
        verbose_name_plural = 'Mouvements de fidélité'
        ordering = ['-created_at']
        indexes = [
            # Nom EXPLICITE (sinon Django dérive un hash qui diverge du nom
            # écrit à la main dans la migration — piège connu du dépôt).
            models.Index(fields=['compte', '-created_at'],
                         name='fidelite_mvt_compte_date_idx'),
        ]

    def __str__(self):
        return f'{self.type_mouvement} {self.points:+d} pts (compte {self.compte_id})'
