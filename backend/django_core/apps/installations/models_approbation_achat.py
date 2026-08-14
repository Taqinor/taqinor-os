"""
NTP2P2 — Plan d'approbation générique pour les demandes d'achat (FG310).

Réutilise le PATRON éprouvé de ``contrats.RegleApprobation`` /
``contrats.EtapeApprobation`` (règle par seuil de montant → N étapes
séquentielles instanciées à la soumission) SANS l'importer : la frontière
cross-app interdit d'importer les ``models`` d'une autre app métier. Les deux
modèles vivent donc dans l'app ``installations``, exactement là où vit déjà
``DemandeAchat`` (FG310) — même app, aucune dépendance nouvelle.

Différences assumées avec le patron ``contrats`` :
  * le périmètre d'une règle est un SEUIL DE MONTANT + un chantier/programme
    OPTIONNEL (``contrats`` cible un ``type_contrat``) ;
  * ``autorise_depassement_budget`` (NTP2P4) : une règle peut explicitement
    AUTORISER le dépassement du budget départemental sous réserve que ses
    étapes d'approbation soient validées — le contrôle budgétaire dur reste le
    défaut.

Comportement HISTORIQUE INCHANGÉ : tant qu'aucune ``RegleApprobationAchat``
active ne couvre le montant d'une demande, aucune étape n'est instanciée et
``soumettre``/``approuver`` se comportent exactement comme avant (approbation
directe par un responsable/admin). Le plan d'approbation est donc 100 %
opt-in, société par société.

Multi-tenant : les deux modèles héritent de ``core.models.TenantModel``
(socle ARC1 — ``company`` + horodatage), la société est TOUJOURS posée côté
serveur, jamais lue du corps de la requête.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TenantModel


class RegleApprobationAchat(TenantModel):
    """NTP2P2 — règle d'approbation d'une demande d'achat par seuil de montant.

    Une règle « couvre » une demande quand le montant estimé de celle-ci tombe
    dans l'intervalle ``[montant_min, montant_max]`` (bornes optionnelles =
    ouvertes) ET que le chantier/programme de la demande correspond au
    périmètre de la règle (une règle sans chantier ni programme est GÉNÉRIQUE :
    elle couvre toutes les demandes de la société).

    La règle la plus SPÉCIFIQUE gagne (priorité décroissante, puis intervalle
    le plus étroit) — même arbitrage que ``contrats.RegleApprobation``.
    """

    class NiveauApprobation(models.TextChoices):
        RESPONSABLE = 'responsable', 'Responsable'
        ADMINISTRATEUR = 'administrateur', 'Administrateur'
        DIRECTION = 'direction', 'Direction'

    libelle = models.CharField(
        max_length=150, verbose_name='Libellé')
    montant_min = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Montant minimum (MAD)',
        help_text='Borne basse incluse. Vide = pas de borne basse.')
    montant_max = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Montant maximum (MAD)',
        help_text='Borne haute incluse. Vide = pas de borne haute.')
    # Périmètre OPTIONNEL : une règle peut ne viser qu'un chantier ou un
    # programme. Même app → FK directe (aucune frontière franchie).
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='regles_approbation_achat',
        verbose_name='Chantier (optionnel)')
    programme = models.ForeignKey(
        'installations.Projet', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='regles_approbation_achat',
        verbose_name='Programme (optionnel)')
    niveau_approbation = models.CharField(
        max_length=20, choices=NiveauApprobation.choices,
        default=NiveauApprobation.RESPONSABLE,
        verbose_name="Niveau d'approbation requis")
    nombre_approbateurs = models.PositiveIntegerField(
        default=1, verbose_name="Nombre d'approbateurs séquentiels")
    # NTP2P4 — dérogation budgétaire : quand la règle l'autorise, une demande
    # qui dépasse le budget départemental restant N'EST PAS refusée à la
    # soumission ; elle part en approbation et le dépassement est tracé.
    autorise_depassement_budget = models.BooleanField(
        default=False,
        verbose_name='Autorise le dépassement du budget départemental',
        help_text='Quand actif, une demande hors budget part en approbation '
                  'au lieu d\'être refusée (NTP2P4).')
    priorite = models.IntegerField(
        default=0, verbose_name='Priorité (décroissante)')
    actif = models.BooleanField(default=True, verbose_name='Active')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Règle d'approbation d'achat"
        verbose_name_plural = "Règles d'approbation d'achat"
        ordering = ['-priorite', 'id']
        indexes = [
            # Noms d'index ≤ 30 caractères.
            models.Index(fields=['company', 'actif'],
                         name='idx_regapa_co_actif'),
            models.Index(fields=['company', 'chantier'],
                         name='idx_regapa_co_chant'),
        ]

    def __str__(self):
        return f'{self.libelle} ({self.nombre_approbateurs} approbateur·s)'

    def clean(self):
        super().clean()
        if (self.montant_min is not None and self.montant_max is not None
                and self.montant_min > self.montant_max):
            raise ValidationError(
                'Le montant minimum ne peut pas dépasser le montant maximum.')
        if self.nombre_approbateurs is not None and self.nombre_approbateurs < 1:
            raise ValidationError(
                "Une règle exige au moins un approbateur.")

    def couvre(self, montant, *, chantier_id=None, programme_id=None):
        """True si cette règle s'applique à ce montant et à ce périmètre."""
        if not self.actif:
            return False
        montant = Decimal(montant or 0)
        if self.montant_min is not None and montant < self.montant_min:
            return False
        if self.montant_max is not None and montant > self.montant_max:
            return False
        if self.chantier_id and self.chantier_id != chantier_id:
            return False
        if self.programme_id and self.programme_id != programme_id:
            return False
        return True

    def largeur_intervalle(self):
        """Largeur de l'intervalle de montant — sert à départager deux règles
        de même priorité (la plus ÉTROITE, donc la plus spécifique, gagne).
        Une borne ouverte compte comme infinie."""
        if self.montant_min is None or self.montant_max is None:
            return Decimal('Infinity')
        return Decimal(self.montant_max) - Decimal(self.montant_min)

    def specificite(self):
        """Nombre de dimensions de périmètre fixées (chantier, programme) —
        une règle ciblée bat une règle générique à priorité égale."""
        return int(bool(self.chantier_id)) + int(bool(self.programme_id))


class EtapeApprobationAchat(TenantModel):
    """NTP2P2 — étape d'approbation SÉQUENTIELLE d'une demande d'achat.

    Les étapes sont instanciées en bloc à la soumission de la demande
    (``services.lancer_workflow_approbation_achat``), numérotées 1..N. Elles se
    décident DANS L'ORDRE : approuver l'étape 2 alors que l'étape 1 est encore
    ``en_attente`` est refusé. Quand la DERNIÈRE étape est approuvée, la
    demande bascule ``approuvee`` (et devient donc convertible en BCF) ; un
    rejet à n'importe quelle étape bascule la demande ``refusee``.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        APPROUVE = 'approuve', 'Approuvée'
        REJETE = 'rejete', 'Rejetée'

    demande = models.ForeignKey(
        'installations.DemandeAchat', on_delete=models.CASCADE,
        related_name='etapes_approbation',
        verbose_name="Demande d'achat")
    regle = models.ForeignKey(
        RegleApprobationAchat, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='etapes',
        verbose_name='Règle appliquée')
    niveau = models.PositiveIntegerField(
        default=1, verbose_name='Rang séquentiel (1..N)')
    niveau_approbation = models.CharField(
        max_length=20, choices=RegleApprobationAchat.NiveauApprobation.choices,
        default=RegleApprobationAchat.NiveauApprobation.RESPONSABLE,
        verbose_name="Niveau d'approbation requis")
    approbateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='etapes_approbation_achat',
        verbose_name='Approbateur')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    decision_le = models.DateTimeField(null=True, blank=True)
    commentaire = models.TextField(blank=True, default='')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Étape d'approbation d'achat"
        verbose_name_plural = "Étapes d'approbation d'achat"
        ordering = ['demande_id', 'niveau', 'id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_etapa_co_statut'),
            models.Index(fields=['demande', 'niveau'],
                         name='idx_etapa_dem_niv'),
        ]

    def __str__(self):
        return f'Étape {self.niveau} · {self.get_statut_display()}'

    @property
    def est_decidee(self):
        return self.statut != self.Statut.EN_ATTENTE
