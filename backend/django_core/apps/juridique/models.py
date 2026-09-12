"""Modèles des affaires juridiques (module ``apps.juridique``, groupe NTJUR).

``DossierJuridique`` (NTJUR1) est le dossier de contentieux/précontentieux
d'une société : sa référence anti-collision (``JUR-{annee}-{seq}``) est
produite par ``core.numbering`` (jamais ``count() + 1`` — collision déjà vécue
en production sur les documents supprimés, cf. ``apps/ventes/utils/references``).

Multi-société : tout modèle hérite de ``core.models.TenantModel`` (FK
``company`` + horodatage, ARC1) ; la société est TOUJOURS posée côté serveur.
Les objets d'autres apps (réclamation ``litiges``, contrat, provision
``compta``) sont référencés par un simple identifiant (string-ref), jamais par
une FK réelle ni un import de leur ``models`` — la frontière inter-apps passe
par ``selectors.py`` / ``services.py``.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TenantModel


class DossierJuridique(TenantModel):
    """Un dossier juridique (contentieux, précontentieux, consultatif…).

    NTJUR1 — socle du module. Le ``statut`` procédural porte ses PROPRES clés
    (ouvert → … → clos_*), explicitement SÉPARÉES du funnel commercial
    ``STAGES.py`` (règle #2 : ce n'est pas une étape de vente) et du cycle des
    documents Devis/Facture (règle #4). Les transitions légales et les actions
    qui les appliquent vivent dans ``services.changer_statut`` (NTJUR2) : le
    champ est en lecture seule au sérialiseur, jamais posable par un PATCH brut
    (garde ``scripts/check_machine_etats_statut_readonly.py``).
    """

    class Nature(models.TextChoices):
        CONTENTIEUX = 'contentieux', 'Contentieux'
        PRECONTENTIEUX = 'precontentieux', 'Précontentieux'
        CONSULTATIF = 'consultatif', 'Consultatif'
        RECOUVREMENT = 'recouvrement', 'Recouvrement'

    class TypeProcedure(models.TextChoices):
        CIVIL = 'civil', 'Civil'
        COMMERCIAL = 'commercial', 'Commercial'
        SOCIAL = 'social', 'Social'
        PENAL = 'penal', 'Pénal'
        ADMINISTRATIF = 'administratif', 'Administratif'
        ARBITRAGE = 'arbitrage', 'Arbitrage'

    class DegreJuridiction(models.TextChoices):
        PREMIERE_INSTANCE = 'premiere_instance', 'Première instance'
        APPEL = 'appel', 'Appel'
        CASSATION = 'cassation', 'Cassation'

    class Position(models.TextChoices):
        DEMANDEUR = 'demandeur', 'Demandeur'
        DEFENDEUR = 'defendeur', 'Défendeur'

    class NiveauConfidentialite(models.TextChoices):
        PUBLIC = 'public', 'Public'
        INTERNE = 'interne', 'Interne'
        CONFIDENTIEL = 'confidentiel', 'Confidentiel'

    class Statut(models.TextChoices):
        """Machine à états PROCÉDURALE — clés propres au module juridique.

        JAMAIS les clés de ``STAGES.py`` (funnel commercial, règle #2) ni
        celles du cycle Devis/Facture (règle #4) : un dossier juridique n'est
        ni une opportunité ni un document de vente.
        """
        OUVERT = 'ouvert', 'Ouvert'
        INSTRUCTION = 'instruction', 'En instruction'
        AUDIENCE_PROGRAMMEE = 'audience_programmee', 'Audience programmée'
        EN_DELIBERE = 'en_delibere', 'En délibéré'
        JUGEMENT_RENDU = 'jugement_rendu', 'Jugement rendu'
        APPEL = 'appel', 'En appel'
        EXECUTION = 'execution', 'En exécution'
        CLOS_GAGNE = 'clos_gagne', 'Clos — gagné'
        CLOS_PERDU = 'clos_perdu', 'Clos — perdu'
        CLOS_TRANSACTION = 'clos_transaction', 'Clos — transaction'
        CLOS_DESISTEMENT = 'clos_desistement', 'Clos — désistement'

    #: Statuts TERMINAUX (un dossier clos ne repart pas).
    STATUTS_CLOS = (
        Statut.CLOS_GAGNE, Statut.CLOS_PERDU,
        Statut.CLOS_TRANSACTION, Statut.CLOS_DESISTEMENT,
    )

    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    titre = models.CharField(max_length=255, verbose_name='Titre')
    nature = models.CharField(
        max_length=20, choices=Nature.choices,
        default=Nature.CONTENTIEUX, verbose_name='Nature')
    type_procedure = models.CharField(
        max_length=20, choices=TypeProcedure.choices,
        default=TypeProcedure.CIVIL, verbose_name='Type de procédure')
    juridiction_nom = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Juridiction')
    juridiction_ville = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Ville de la juridiction')
    juridiction_degre = models.CharField(
        max_length=20, choices=DegreJuridiction.choices,
        default=DegreJuridiction.PREMIERE_INSTANCE,
        verbose_name='Degré de juridiction')
    montant_en_jeu = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant en jeu')
    partie_adverse_nom = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Partie adverse')
    notre_position = models.CharField(
        max_length=15, choices=Position.choices,
        default=Position.DEFENDEUR, verbose_name='Notre position')
    resume_faits = models.TextField(
        blank=True, default='', verbose_name='Résumé des faits')
    date_ouverture = models.DateField(verbose_name="Date d'ouverture")
    responsable_interne = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        # on_delete: un dossier juridique SURVIT au départ de son responsable
        # (pièce à valeur légale) — jamais de cascade.
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='dossiers_juridiques',
        verbose_name='Responsable interne',
    )
    # Même patron que ``contrats.Contrat.confidentialite`` : le palier faisant
    # autorité est ``CustomUser.menu_tier`` (dérivé du Role FK), jamais le
    # ``role_legacy`` peu fiable. Le filtrage vit dans le ``get_queryset`` du
    # ViewSet (NTJUR1) — un dossier confidentiel est INVISIBLE, pas 403.
    confidentialite = models.CharField(
        max_length=20, choices=NiveauConfidentialite.choices,
        default=NiveauConfidentialite.INTERNE,
        verbose_name='Confidentialité')
    statut = models.CharField(
        max_length=25, choices=Statut.choices,
        default=Statut.OUVERT, verbose_name='Statut')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        # on_delete: trace d'auteur, jamais une raison de perdre le dossier.
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='dossiers_juridiques_crees',
        verbose_name='Créé par',
    )

    class Meta:
        verbose_name = 'Dossier juridique'
        verbose_name_plural = 'Dossiers juridiques'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='juridique_dossier_co_ref_uniq'),
        ]

    def __str__(self):
        return f'{self.reference} {self.titre}'.strip()

    @property
    def est_clos(self):
        """Vrai si le dossier a atteint un statut terminal ``clos_*``."""
        return self.statut in {s.value for s in self.STATUTS_CLOS}


class CabinetAvocat(TenantModel):
    """Registre des cabinets / avocats externes de la société (NTJUR9).

    Prérequis du mandat (NTJUR10) et donc du workflow d'approbation des
    engagements juridiques (NTJUR19) : sans cabinet, aucun mandat à approuver.
    """

    nom = models.CharField(max_length=200, verbose_name='Nom du cabinet')
    barreau = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Barreau')
    specialites = models.TextField(
        blank=True, default='',
        verbose_name='Spécialités',
        help_text='Liste libre, une spécialité par ligne ou séparée par des '
                  'virgules.')
    contact_principal = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Contact principal')
    email = models.EmailField(blank=True, default='', verbose_name='E-mail')
    telephone = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Téléphone')
    taux_horaire_moyen = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Taux horaire moyen')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = "Cabinet d'avocats"
        verbose_name_plural = "Cabinets d'avocats"
        ordering = ['nom', 'id']

    def __str__(self):
        return self.nom


class MandatAvocat(TenantModel):
    """Mandat confié à un cabinet sur un dossier, et ses honoraires (NTJUR10).

    Le ``statut`` ne passe à ``actif`` qu'après le workflow d'approbation
    (NTJUR19) lorsqu'une ``RegleApprobationJuridique`` couvre son montant
    engagé — c'est le point de contrôle des dépenses juridiques.
    """

    class ModeFacturation(models.TextChoices):
        FORFAIT = 'forfait', 'Forfait'
        HORAIRE = 'horaire', 'Horaire'
        RESULTAT = 'resultat', 'Au résultat'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_APPROBATION = 'en_approbation', "En attente d'approbation"
        ACTIF = 'actif', 'Actif'
        CLOS = 'clos', 'Clos'

    dossier = models.ForeignKey(
        DossierJuridique,
        # on_delete: un mandat n'a aucun sens hors de son dossier.
        on_delete=models.CASCADE,
        related_name='mandats',
        verbose_name='Dossier juridique',
    )
    cabinet = models.ForeignKey(
        CabinetAvocat,
        # on_delete: on ne perd jamais l'historique d'un mandat parce qu'un
        # cabinet a été retiré du registre — il est simplement détaché.
        on_delete=models.PROTECT,
        related_name='mandats',
        verbose_name="Cabinet d'avocats",
    )
    date_mandat = models.DateField(verbose_name='Date du mandat')
    mode_facturation = models.CharField(
        max_length=15, choices=ModeFacturation.choices,
        default=ModeFacturation.FORFAIT, verbose_name='Mode de facturation')
    montant_forfait = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Montant du forfait')
    taux_horaire = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Taux horaire')
    # NTJUR12 — l'« estimation horaire » du budget ENGAGÉ a besoin d'un volume :
    # sans lui, un mandat horaire pèserait 0 dans l'engagement (et passerait
    # sous tout seuil d'approbation NTJUR19). 0 = non estimé.
    heures_estimees = models.PositiveIntegerField(
        default=0, verbose_name='Heures estimées')
    pourcentage_resultat = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Pourcentage au résultat')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')

    class Meta:
        verbose_name = 'Mandat avocat'
        verbose_name_plural = 'Mandats avocat'
        ordering = ['-date_mandat', '-id']

    def __str__(self):
        return f'{self.cabinet_id} — dossier {self.dossier_id}'

    @property
    def montant_engage(self):
        """Montant ENGAGÉ par ce mandat (base du seuil d'approbation NTJUR19).

        * forfait  → le forfait ;
        * horaire  → taux horaire × heures estimées (0 si non estimé) ;
        * résultat → 0 : l'honoraire de résultat n'est dû qu'en cas de gain,
          il n'engage rien à la signature (jamais un chiffre inventé).
        """
        if self.mode_facturation == self.ModeFacturation.FORFAIT:
            return self.montant_forfait or Decimal('0')
        if self.mode_facturation == self.ModeFacturation.HORAIRE:
            taux = self.taux_horaire or Decimal('0')
            return taux * Decimal(self.heures_estimees or 0)
        return Decimal('0')


class RegleApprobationJuridique(TenantModel):
    """Règle d'approbation d'un engagement de dépense juridique (NTJUR19).

    Patron IDENTIQUE à ``contrats.RegleApprobation`` (CONTRAT13) : la logique
    n'est pas réinventée, elle est dupliquée parce qu'AUCUNE FK réelle
    cross-app n'est possible (``juridique`` n'importe jamais les modèles de
    ``contrats``). Data-driven : aucun seuil codé en dur — le seuil VIT dans
    les règles en base, société par société.
    """

    class NiveauApprobation(models.TextChoices):
        RESPONSABLE = 'responsable', 'Responsable'
        ADMINISTRATEUR = 'administrateur', 'Administrateur'
        DIRECTION = 'direction', 'Direction'

    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    # Nature de dossier ciblée (reprend les choix de DossierJuridique).
    # Vide = toutes natures.
    nature_dossier = models.CharField(
        max_length=20, choices=DossierJuridique.Nature.choices,
        blank=True, default='', verbose_name='Nature de dossier ciblée')
    montant_min = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Montant minimum')
    montant_max = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Montant maximum')
    niveau_approbation = models.CharField(
        max_length=20, choices=NiveauApprobation.choices,
        default=NiveauApprobation.RESPONSABLE,
        verbose_name="Niveau d'approbation requis")
    nombre_approbateurs = models.PositiveIntegerField(
        default=1, verbose_name="Nombre d'approbateurs requis")
    priorite = models.PositiveIntegerField(default=0, verbose_name='Priorité')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = "Règle d'approbation juridique"
        verbose_name_plural = "Règles d'approbation juridique"
        ordering = ['-priorite', 'id']
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='juridique_regleapp_co_act'),
        ]

    def __str__(self):
        cible = (self.get_nature_dossier_display()
                 if self.nature_dossier else 'Toutes natures')
        return f'{self.libelle} ({cible})'

    def clean(self):
        if (self.montant_min is not None and self.montant_max is not None
                and self.montant_min > self.montant_max):
            raise ValidationError(
                'Le montant minimum ne peut pas dépasser le montant maximum.')

    def couvre(self, montant, nature_dossier=None):
        """Indique si la règle couvre un couple (montant, nature de dossier)."""
        if (self.nature_dossier and nature_dossier
                and self.nature_dossier != nature_dossier):
            return False
        if self.nature_dossier and not nature_dossier:
            return False
        if montant is None:
            return self.montant_min is None and self.montant_max is None
        montant = Decimal(str(montant))
        if self.montant_min is not None and montant < self.montant_min:
            return False
        if self.montant_max is not None and montant > self.montant_max:
            return False
        return True

    def largeur_intervalle(self):
        """Largeur de l'intervalle (départage de spécificité). ``None`` =
        intervalle ouvert, donc moins spécifique."""
        if self.montant_min is None or self.montant_max is None:
            return None
        return self.montant_max - self.montant_min


class EtapeApprobationJuridique(TenantModel):
    """Une étape du workflow d'approbation d'un mandat (NTJUR19).

    Statuts LOCAUX au workflow (``en_attente`` → ``approuve``/``rejete``) :
    aucun lien avec ``STAGES.py`` (règle #2) ni avec ``DossierJuridique.statut``
    (machine procédurale), qui n'est JAMAIS touché par une décision d'étape.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        APPROUVE = 'approuve', 'Approuvé'
        REJETE = 'rejete', 'Rejeté'

    mandat = models.ForeignKey(
        MandatAvocat,
        # on_delete: une étape n'existe que pour son mandat.
        on_delete=models.CASCADE,
        related_name='etapes_approbation',
        verbose_name='Mandat',
    )
    regle = models.ForeignKey(
        RegleApprobationJuridique,
        # on_delete: supprimer la règle n'efface pas l'historique des décisions.
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='etapes_approbation',
        verbose_name="Règle d'approbation source",
    )
    niveau = models.PositiveIntegerField(
        default=1, verbose_name="Niveau / rang de l'étape")
    niveau_approbation = models.CharField(
        max_length=20,
        choices=RegleApprobationJuridique.NiveauApprobation.choices,
        default=RegleApprobationJuridique.NiveauApprobation.RESPONSABLE,
        verbose_name="Niveau d'approbation requis")
    approbateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        # on_delete: on garde la trace de l'étape même si le compte part.
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='juridique_etapes_approuvees',
        verbose_name='Approbateur',
    )
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.EN_ATTENTE, verbose_name='Statut')
    decision_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Décidé le')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')

    class Meta:
        verbose_name = "Étape d'approbation juridique"
        verbose_name_plural = "Étapes d'approbation juridique"
        ordering = ['mandat_id', 'niveau', 'id']
        indexes = [
            models.Index(fields=['mandat', 'niveau'],
                         name='juridique_etapeapp_ma_niv'),
        ]

    def __str__(self):
        return (f'Étape {self.niveau} — {self.get_statut_display()} '
                f'(mandat {self.mandat_id})')
