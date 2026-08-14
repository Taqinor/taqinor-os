"""Modèles du module « fidelite » (Groupe NTRET) — programme de fidélité par
points, paliers et carte dématérialisée.

MULTI-TENANT : tout modèle hérite de ``core.models.TenantModel`` (FK
``company`` + horodatage, ARC1) — la société est TOUJOURS posée côté serveur,
jamais lue d'un corps de requête.

Frontière inter-app (CLAUDE.md) : le lien vers le client passe par une FK À
CHAÎNE ``'crm.Client'`` — jamais un import direct de ``apps.crm.models``.
"""
import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TenantModel


def generer_code_qr():
    """NTRET11 — jeton opaque non séquentiel pour la carte dématérialisée
    (jamais l'id de la ligne, ni une valeur devinable)."""
    return secrets.token_urlsafe(24)


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


class PalierFidelite(TenantModel):
    """Palier de fidélité (Bronze/Argent/Or…) — NTRET10.

    Un compte franchit un palier quand son solde de points OU son CA TTC
    cumulé de l'année civile atteint le seuil du palier (l'un des deux
    seuils suffit — ``services.recalculer_palier`` retient le palier du plus
    haut ``ordre`` atteint).
    """

    programme = models.ForeignKey(
        ProgrammeFidelite,
        on_delete=models.CASCADE,  # on_delete: composition — un palier n'existe que dans son programme
        related_name='paliers')
    libelle = models.CharField(max_length=60)
    ordre = models.PositiveSmallIntegerField(
        help_text=(
            'Rang croissant (1 = le plus bas). Détermine le palier retenu '
            '(le plus haut `ordre` atteint gagne).'))
    seuil_points = models.PositiveIntegerField(null=True, blank=True)
    seuil_ca_cumule = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Seuil de chiffre d'affaires TTC cumulé sur l'année civile.")
    remise_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Remise automatique (%) appliquée à la caisse pour ce palier.')
    points_bonus_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Bonus (%) de points supplémentaires accordé à ce palier.')

    class Meta:
        verbose_name = 'Palier de fidélité'
        verbose_name_plural = 'Paliers de fidélité'
        ordering = ['programme', 'ordre']
        constraints = [
            models.UniqueConstraint(
                fields=['programme', 'ordre'],
                name='uniq_palierfidelite_programme_ordre'),
            models.CheckConstraint(
                check=(
                    models.Q(seuil_points__isnull=False)
                    | models.Q(seuil_ca_cumule__isnull=False)),
                name='chk_palierfidelite_seuil_requis'),
        ]

    def __str__(self):
        return f'{self.libelle} ({self.programme.nom})'


class CompteFidelite(TenantModel):
    """Compte fidélité d'un client (1-1) — solde de points courant + palier.

    Naît automatiquement au premier crédit de points
    (``services.crediter_points_pour_vente``), jamais d'une création
    manuelle via l'API (voir ``views.CompteFideliteViewSet``, lecture seule).
    """

    client = models.OneToOneField(
        'crm.Client',
        # on_delete: composition — la carte de fidélité est un attribut du client
        # (1-1) ; supprimer le client doit emporter sa carte et ses mouvements,
        # sinon il resterait un solde de points orphelin non rattachable.
        on_delete=models.CASCADE,
        related_name='compte_fidelite')
    solde_points = models.PositiveIntegerField(default=0)
    palier_actuel = models.ForeignKey(
        PalierFidelite, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='comptes')
    code_qr = models.CharField(
        max_length=64, unique=True, default=generer_code_qr, editable=False,
        help_text=(
            'Jeton opaque non séquentiel (carte dématérialisée NTRET11) — '
            "globalement unique : résout LUI-MÊME LA société, jamais "
            'réutilisable pour un autre tenant.'))

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
        CompteFidelite,
        on_delete=models.CASCADE,  # on_delete: composition — un mouvement de points n'existe que dans son compte
        related_name='mouvements')
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
