"""Modèles du module GRC & Conformité (Groupe NTGRC).

Convention du dépôt : tout modèle multi-société hérite de
``core.models.TenantModel`` (FK ``company`` + horodatage, ARC1). Les
références vers une AUTRE app sont déclarées en CHAÎNE (``'app.Model'``) ou
portées par un identifiant texte (``*_ref``) — jamais un import de ses
``models``.
"""
from django.db import models
from django.utils import timezone

from core.models import TenantModel


class PolitiqueRetentionObjet(TenantModel):
    """NTGRC4 — durée de conservation d'un TYPE d'objet, par société.

    Paramètre la rétention que les apps métier appliquent elles-mêmes via le
    registre de fondation ``core.retention`` : ``grc`` décrit QUOI et COMBIEN
    DE TEMPS, chaque app décide COMMENT (et n'expose que les actions qu'elle
    sait réellement exécuter). Rien n'est jamais supprimé automatiquement :
    ``run_retention`` est en DRY-RUN par défaut et n'agit qu'avec
    ``--commit``/``--apply``.

    Distinct de ``ged.PolitiqueRetention`` (rétention DOCUMENTAIRE, par
    cabinet/dossier/type de document) : ici la maille est le TYPE D'OBJET
    métier (lead, client, facture, ticket, ligne d'audit).
    """

    TYPE_CRM_LEAD = 'crm_lead'
    TYPE_CRM_CLIENT = 'crm_client'
    TYPE_VENTES_FACTURE = 'ventes_facture'
    TYPE_SAV_TICKET = 'sav_ticket'
    TYPE_AUDIT_LOG = 'audit_log'
    TYPE_CHOICES = [
        (TYPE_CRM_LEAD, 'Lead CRM'),
        (TYPE_CRM_CLIENT, 'Client CRM'),
        (TYPE_VENTES_FACTURE, 'Facture'),
        (TYPE_SAV_TICKET, 'Ticket SAV'),
        (TYPE_AUDIT_LOG, "Ligne du journal d'audit"),
    ]

    ACTION_SIGNALER = 'signaler'
    ACTION_ANONYMISER = 'anonymiser'
    ACTION_ARCHIVER = 'archiver'
    ACTION_CHOICES = [
        (ACTION_SIGNALER, 'Signaler seulement'),
        (ACTION_ANONYMISER, 'Anonymiser'),
        (ACTION_ARCHIVER, 'Archiver'),
    ]

    type_objet = models.CharField(
        'Type d\'objet', max_length=30, choices=TYPE_CHOICES)
    duree_conservation_mois = models.PositiveIntegerField(
        'Durée de conservation (mois)', default=36,
        help_text='Au-delà de cette durée, l\'objet est échu.')
    action_echeance = models.CharField(
        "Action à l'échéance", max_length=12, choices=ACTION_CHOICES,
        default=ACTION_SIGNALER,
        help_text="Une action que l'app cible ne sait pas exécuter retombe "
                  'sur « signaler » — jamais sur une suppression inventée.')
    actif = models.BooleanField('Active', default=True)

    class Meta:
        verbose_name = 'Politique de rétention par type d\'objet'
        verbose_name_plural = 'Politiques de rétention par type d\'objet'
        ordering = ['type_objet', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'type_objet'],
                name='grc_politiqueretentionobjet_co_type'),
        ]

    def __str__(self):
        return (f'{self.get_type_objet_display()} — '
                f'{self.duree_conservation_mois} mois '
                f'({self.get_action_echeance_display()})')


class JournalDestructionError(Exception):
    """NTGRC5 — levée à toute tentative de modifier/supprimer une ligne.

    Hérite d'``Exception`` (même contrat que ``ged.ArchivageLegalError``) ; la
    vue la traduit en 403, jamais en 500.
    """


class JournalDestruction(TenantModel):
    """NTGRC5 — journal APPEND-ONLY des destructions/anonymisations réelles.

    ``core.RetentionRun`` ne retient qu'un COMPTE par politique : « 42 objets
    traités » ne prouve à personne CE qui a été détruit, quand, par qui et au
    titre de quoi. Ce journal porte la ligne détaillée, une par objet
    réellement touché, écrite par les fournisseurs DSR (NTGRC1) et par les
    politiques de rétention (NTGRC4).

    AUCUNE donnée personnelle n'y est stockée : le type d'objet, son
    identifiant technique, le motif et une EMPREINTE SHA-256 de la valeur
    détruite — l'empreinte prouve « c'est bien cette donnée-là » sans la
    conserver. Ce serait absurde (et illégal) de recopier dans un registre ce
    qu'on vient d'effacer sur demande.

    IMMUABLE : ``save()`` refuse toute mise à jour et ``delete()` refuse la
    suppression, exactement comme ``ged.ArchivageLegal`` (GED23). Le viewset
    n'expose ni PUT/PATCH ni DELETE ; la garde modèle empêche tout contournement
    par un autre chemin de code.

    Les références vers les autres apps sont des identifiants TEXTE
    (``objet_ref``, ``politique_ref``, ``demande_droit_ref``) — jamais une FK
    vers un modèle d'une autre app, et la ligne survit donc à la disparition de
    l'objet qu'elle documente (c'est tout l'intérêt d'un journal de
    destruction).
    """

    ACTION_SUPPRIME = 'supprime'
    ACTION_ANONYMISE = 'anonymise'
    ACTION_ARCHIVE = 'archive'
    ACTION_CHOICES = [
        (ACTION_SUPPRIME, 'Supprimé'),
        (ACTION_ANONYMISE, 'Anonymisé'),
        (ACTION_ARCHIVE, 'Archivé'),
    ]

    type_objet = models.CharField(
        "Type d'objet", max_length=60,
        help_text='Ex. « crm_lead », « stock_fournisseur ».')
    objet_ref = models.CharField(
        "Référence de l'objet", max_length=64,
        help_text='Identifiant technique de l\'objet touché (jamais son nom).')
    action = models.CharField(
        'Action', max_length=12, choices=ACTION_CHOICES)
    politique_ref = models.CharField(
        'Politique de rétention', max_length=64, blank=True, default='',
        help_text='Id de la `grc.PolitiqueRetentionObjet` appliquée, si la '
                  'destruction vient d\'un balayage de rétention.')
    demande_droit_ref = models.CharField(
        'Demande de droit', max_length=64, blank=True, default='',
        help_text='Référence de la `core.DataSubjectRequest` à l\'origine de '
                  "l'effacement, s'il vient d'une demande de personne.")
    executee_par = models.CharField(
        'Exécutée par', max_length=150, blank=True, default='',
        help_text="Instantané du nom d'utilisateur (survit à la suppression "
                  'du compte) ; vide pour un balayage système.')
    motif = models.TextField('Motif', blank=True, default='')
    empreinte_avant = models.CharField(
        'Empreinte avant destruction (SHA-256)', max_length=64, blank=True,
        default='',
        help_text='SHA-256 de la valeur détruite — jamais la valeur.')

    class Meta:
        verbose_name = 'Ligne du journal de destruction'
        verbose_name_plural = 'Journal de destruction'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'type_objet'],
                         name='grc_journaldestr_co_type_idx'),
            models.Index(fields=['company', '-created_at'],
                         name='grc_journaldestr_co_date_idx'),
        ]

    def save(self, *args, **kwargs):
        """Création SEULE : une ligne de journal ne se réécrit jamais."""
        if self.pk is not None:
            raise JournalDestructionError(
                'Le journal de destruction est immuable (création seule) : '
                'une ligne ne peut pas être modifiée.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Refuse la suppression : un journal qu'on peut vider ne prouve rien."""
        raise JournalDestructionError(
            'Le journal de destruction est immuable : une ligne ne peut pas '
            'être supprimée.')

    def __str__(self):
        quand = f' ({self.created_at:%Y-%m-%d})' if self.created_at else ''
        return (f'{self.type_objet}#{self.objet_ref} — '
                f'{self.get_action_display()}{quand}')


class ViolationDonnees(TenantModel):
    """NTGRC6 — registre des violations de données personnelles (« breach »).

    Loi 09-08 / RGPD : une violation se notifie à l'autorité SANS DÉLAI, et au
    plus tard 72 heures après en avoir pris connaissance. L'échéance est donc
    calculée à la DÉTECTION (le moment où l'on a su), pas à l'incident (le
    moment où c'est arrivé) — les deux dates sont distinctes et toutes deux
    conservées, parce que l'écart entre elles est précisément ce qu'un
    contrôleur regarde.

    Distinct de ``qhse`` (risques santé/sécurité au travail) et de
    ``IncidentSecurite`` (incident technique, qui peut n'impliquer AUCUNE
    donnée personnelle). Ici c'est le registre RÉGLEMENTAIRE.
    """

    #: Préfixe des références (VD-YYYYMM-0001), race-safe via `core.numbering`.
    REFERENCE_PREFIX = 'VD'
    #: Délai légal de notification, en heures.
    DELAI_NOTIFICATION_HEURES = 72

    NATURE_CONFIDENTIALITE = 'confidentialite'
    NATURE_INTEGRITE = 'integrite'
    NATURE_DISPONIBILITE = 'disponibilite'
    NATURE_CHOICES = [
        (NATURE_CONFIDENTIALITE, 'Atteinte à la confidentialité'),
        (NATURE_INTEGRITE, "Atteinte à l'intégrité"),
        (NATURE_DISPONIBILITE, 'Atteinte à la disponibilité'),
    ]

    GRAVITE_FAIBLE = 'faible'
    GRAVITE_MOYENNE = 'moyenne'
    GRAVITE_ELEVEE = 'elevee'
    GRAVITE_CRITIQUE = 'critique'
    GRAVITE_CHOICES = [
        (GRAVITE_FAIBLE, 'Faible'),
        (GRAVITE_MOYENNE, 'Moyenne'),
        (GRAVITE_ELEVEE, 'Élevée'),
        (GRAVITE_CRITIQUE, 'Critique'),
    ]

    STATUT_OUVERTE = 'ouverte'
    STATUT_EN_ANALYSE = 'en_analyse'
    STATUT_NOTIFIEE = 'notifiee'
    STATUT_CLOTUREE = 'cloturee'
    STATUT_CHOICES = [
        (STATUT_OUVERTE, 'Ouverte'),
        (STATUT_EN_ANALYSE, 'En analyse'),
        (STATUT_NOTIFIEE, 'Notifiée'),
        (STATUT_CLOTUREE, 'Clôturée'),
    ]

    reference = models.CharField('Référence', max_length=40, blank=True,
                                 default='')
    date_detection = models.DateTimeField(
        'Date de détection',
        help_text='Moment où la violation a été CONNUE — c\'est elle qui '
                  'déclenche le délai de 72 h.')
    date_incident = models.DateTimeField(
        'Date de l\'incident', null=True, blank=True,
        help_text='Moment où la violation s\'est produite, si connu.')
    nature = models.CharField(
        'Nature', max_length=20, choices=NATURE_CHOICES,
        default=NATURE_CONFIDENTIALITE)
    categories_donnees = models.JSONField(
        'Catégories de données touchées', default=list, blank=True,
        help_text='Ex. ["identite", "contact", "donnees_bancaires"].')
    nombre_personnes_estime = models.PositiveIntegerField(
        'Nombre de personnes concernées (estimé)', default=0)
    gravite = models.CharField(
        'Gravité', max_length=10, choices=GRAVITE_CHOICES,
        default=GRAVITE_MOYENNE)
    risque_personnes = models.TextField(
        'Risque pour les personnes', blank=True, default='')
    mesures_prises = models.TextField(
        'Mesures prises', blank=True, default='')
    notification_cndp_requise = models.BooleanField(
        'Notification CNDP requise', default=True)
    date_notification_cndp = models.DateTimeField(
        'Date de notification CNDP', null=True, blank=True)
    date_echeance_72h = models.DateTimeField(
        'Échéance de notification (72 h)', null=True, blank=True,
        help_text='Détection + 72 h. Posée à la création, jamais reculée.')
    personnes_notifiees = models.BooleanField(
        'Personnes concernées informées', default=False)
    statut = models.CharField(
        'Statut', max_length=12, choices=STATUT_CHOICES,
        default=STATUT_OUVERTE)

    class Meta:
        verbose_name = 'Violation de données'
        verbose_name_plural = 'Registre des violations de données'
        ordering = ['-date_detection', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='grc_violationdonnees_co_ref'),
        ]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='grc_violation_co_statut_idx'),
            models.Index(fields=['company', 'date_echeance_72h'],
                         name='grc_violation_co_ech_idx'),
        ]

    def save(self, *args, **kwargs):
        """Pose l'échéance 72 h UNE FOIS, depuis la date de DÉTECTION.

        Jamais recalculée ensuite : sinon corriger une date de détection après
        coup ferait reculer un délai légal déjà dépassé.
        """
        if self.date_echeance_72h is None and self.date_detection:
            self.date_echeance_72h = self.date_detection + timezone.timedelta(
                hours=self.DELAI_NOTIFICATION_HEURES)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.reference or "VD"} — {self.get_gravite_display()}'


# NTGRC8 — legal hold TRANSVERSE.
#
# Message levé quand une purge ou une anonymisation viserait un objet gelé.
# Même contrat que ``ged.LEGAL_HOLD_MESSAGE`` (GED24), élargi au-delà du seul
# Document : les vues le traduisent en 409 (conflit d'état), jamais en 500.
LEGAL_HOLD_TRANSVERSE_MESSAGE = (
    "Objet sous mise sous séquestre (legal hold) : sa purge et son "
    "anonymisation sont gelées tant qu'un séquestre actif le couvre."
)


class LegalHoldTransverseError(Exception):
    """NTGRC8 — levée quand une purge/anonymisation vise un objet gelé.

    Hérite d'``Exception`` (même contrat que ``ged.LegalHoldError``) pour
    rester explicitement reconnaissable ; traduite en 409 côté vue.
    """


class LegalHold(TenantModel):
    """NTGRC8 — mise sous séquestre TRANSVERSE (au-delà du seul document).

    ``ged.LegalHold`` (GED24) gèle UN document. Un contentieux, lui, ne
    s'arrête pas à la GED : il faut aussi geler le client, ses leads, ses
    tickets. Ce modèle porte le séquestre au niveau du DOSSIER — il ne
    remplace pas celui de la GED, il le COMPOSE : ``objets_sous_hold``
    additionne les deux périmètres (les documents déjà gelés côté GED y
    apparaissent, sans duplication de modèle).

    Le ``perimetre`` est une liste JSON de ``{type_objet, filtre}``. Les
    filtres sont résolus par les ``selectors.py`` des apps cibles — jamais par
    un import de leurs modèles.
    """

    MOTIF_LITIGE = 'litige'
    MOTIF_ENQUETE = 'enquete'
    MOTIF_REGLEMENTAIRE = 'reglementaire'
    MOTIF_CHOICES = [
        (MOTIF_LITIGE, 'Contentieux / litige'),
        (MOTIF_ENQUETE, 'Enquête interne'),
        (MOTIF_REGLEMENTAIRE, 'Demande réglementaire'),
    ]

    STATUT_ACTIF = 'actif'
    STATUT_LEVE = 'leve'
    STATUT_CHOICES = [
        (STATUT_ACTIF, 'Actif'),
        (STATUT_LEVE, 'Levé'),
    ]

    nom = models.CharField('Nom', max_length=160)
    motif = models.CharField(
        'Motif', max_length=15, choices=MOTIF_CHOICES, default=MOTIF_LITIGE)
    perimetre = models.JSONField(
        'Périmètre', default=list, blank=True,
        help_text='Liste de {type_objet, filtre} — ex. '
                  '[{"type_objet": "crm_client", '
                  '"filtre": {"identifiant": "a@b.ma"}}].')
    date_debut = models.DateField('Date de début', null=True, blank=True)
    date_fin = models.DateField('Date de fin', null=True, blank=True)
    statut = models.CharField(
        'Statut', max_length=8, choices=STATUT_CHOICES, default=STATUT_ACTIF)
    demandeur = models.CharField(
        'Demandeur', max_length=160, blank=True, default='',
        help_text='Qui demande le séquestre (avocat, autorité, direction).')
    base_juridique = models.TextField(
        'Base juridique', blank=True, default='')

    class Meta:
        verbose_name = 'Mise sous séquestre (legal hold)'
        verbose_name_plural = 'Mises sous séquestre (legal holds)'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='grc_legalhold_co_statut_idx'),
        ]

    def est_actif(self, aujourdhui=None):
        """Le séquestre couvre-t-il l'instant présent ?

        ``statut`` fait foi ; les dates, quand elles sont renseignées, bornent
        en plus la fenêtre (un séquestre daté du futur ne gèle rien encore, un
        séquestre échu ne gèle plus).
        """
        if self.statut != self.STATUT_ACTIF:
            return False
        jour = aujourdhui or timezone.now().date()
        if self.date_debut and jour < self.date_debut:
            return False
        if self.date_fin and jour > self.date_fin:
            return False
        return True

    def __str__(self):
        return f'{self.nom} ({self.get_statut_display()})'


class RisqueEntreprise(TenantModel):
    """NTGRC13 — registre des risques d'ENTREPRISE (ERM).

    À ne pas confondre avec ``qhse.EvaluationRisque`` (DUERP : risques
    santé/sécurité au poste de travail). Ici la maille est l'entreprise —
    stratégie, finance, conformité, SI, réputation — et le risque porte DEUX
    cotations : INHÉRENTE (avant traitement) et RÉSIDUELLE (après). L'écart
    entre les deux est le seul chiffre qui dise si le traitement sert à
    quelque chose.

    Les criticités sont CALCULÉES (probabilité × impact) et recalculées à
    chaque enregistrement : une criticité saisie à la main finit toujours par
    contredire ses deux facteurs.
    """

    #: Préfixe des références (RQ-YYYYMM-0001), race-safe via `core.numbering`.
    REFERENCE_PREFIX = 'RQ'

    CATEGORIE_CHOICES = [
        ('strategique', 'Stratégique'),
        ('operationnel', 'Opérationnel'),
        ('financier', 'Financier'),
        ('conformite', 'Conformité'),
        ('si', "Système d'information"),
        ('reputation', 'Réputation'),
        ('hse', 'HSE'),
    ]

    REPONSE_CHOICES = [
        ('accepter', 'Accepter'),
        ('reduire', 'Réduire'),
        ('transferer', 'Transférer'),
        ('eviter', 'Éviter'),
    ]

    STATUT_OUVERT = 'ouvert'
    STATUT_TRAITE = 'traite'
    STATUT_SURVEILLE = 'surveille'
    STATUT_CLOS = 'clos'
    STATUT_CHOICES = [
        (STATUT_OUVERT, 'Ouvert'),
        (STATUT_TRAITE, 'Traité'),
        (STATUT_SURVEILLE, 'Sous surveillance'),
        (STATUT_CLOS, 'Clos'),
    ]

    #: Bornes de l'échelle de cotation (grille 5×5, standard ISO 31000).
    ECHELLE_MIN = 1
    ECHELLE_MAX = 5

    reference = models.CharField('Référence', max_length=40, blank=True,
                                 default='')
    titre = models.CharField('Titre', max_length=200)
    categorie = models.CharField(
        'Catégorie', max_length=15, choices=CATEGORIE_CHOICES,
        default='operationnel')
    description = models.TextField('Description', blank=True, default='')
    proprietaire = models.CharField(
        'Propriétaire', max_length=160, blank=True, default='')
    probabilite = models.PositiveSmallIntegerField(
        'Probabilité (1-5)', default=1)
    impact = models.PositiveSmallIntegerField('Impact (1-5)', default=1)
    criticite_inherente = models.PositiveSmallIntegerField(
        'Criticité inhérente', default=1,
        help_text='Calculée : probabilité × impact (jamais saisie).')
    reponse = models.CharField(
        'Réponse au risque', max_length=12, choices=REPONSE_CHOICES,
        default='reduire')
    probabilite_residuelle = models.PositiveSmallIntegerField(
        'Probabilité résiduelle (1-5)', default=1)
    impact_residuel = models.PositiveSmallIntegerField(
        'Impact résiduel (1-5)', default=1)
    criticite_residuelle = models.PositiveSmallIntegerField(
        'Criticité résiduelle', default=1,
        help_text='Calculée : probabilité résiduelle × impact résiduel.')
    statut = models.CharField(
        'Statut', max_length=12, choices=STATUT_CHOICES,
        default=STATUT_OUVERT)
    date_revue_prevue = models.DateField(
        'Prochaine revue prévue', null=True, blank=True)

    class Meta:
        verbose_name = "Risque d'entreprise"
        verbose_name_plural = "Registre des risques d'entreprise"
        ordering = ['-criticite_inherente', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='grc_risqueentreprise_co_ref'),
        ]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='grc_risque_co_statut_idx'),
            models.Index(fields=['company', 'date_revue_prevue'],
                         name='grc_risque_co_revue_idx'),
        ]

    @classmethod
    def borner(cls, valeur):
        """Ramène une cotation dans l'échelle 1-5 (jamais une exception).

        Un formulaire qui envoie 0 ou 12 ne doit pas faire tomber le registre :
        la valeur est bornée, et la criticité reste dans la grille 5×5.
        """
        try:
            valeur = int(valeur)
        except (TypeError, ValueError):
            return cls.ECHELLE_MIN
        return max(cls.ECHELLE_MIN, min(cls.ECHELLE_MAX, valeur))

    def save(self, *args, **kwargs):
        """Recalcule les DEUX criticités à chaque enregistrement."""
        self.probabilite = self.borner(self.probabilite)
        self.impact = self.borner(self.impact)
        self.probabilite_residuelle = self.borner(self.probabilite_residuelle)
        self.impact_residuel = self.borner(self.impact_residuel)
        self.criticite_inherente = self.probabilite * self.impact
        self.criticite_residuelle = (
            self.probabilite_residuelle * self.impact_residuel)
        if kwargs.get('update_fields') is not None:
            champs = set(kwargs['update_fields'])
            champs.update({
                'probabilite', 'impact', 'criticite_inherente',
                'probabilite_residuelle', 'impact_residuel',
                'criticite_residuelle'})
            kwargs['update_fields'] = sorted(champs)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.reference or "RQ"} — {self.titre}'


class PlanTraitementRisque(TenantModel):
    """NTGRC14 — action de traitement d'un risque + son suivi.

    Un registre des risques sans plans d'action est un inventaire de
    problèmes : c'est le plan qui transforme le constat en travail assigné et
    daté. Le retard n'est PAS lu du champ ``statut`` (qui se périme dès que
    personne ne le met à jour) mais recalculé sur l'échéance — voir
    ``selectors.plans_en_retard``.
    """

    STATUT_A_FAIRE = 'a_faire'
    STATUT_EN_COURS = 'en_cours'
    STATUT_FAIT = 'fait'
    STATUT_EN_RETARD = 'en_retard'
    STATUT_CHOICES = [
        (STATUT_A_FAIRE, 'À faire'),
        (STATUT_EN_COURS, 'En cours'),
        (STATUT_FAIT, 'Fait'),
        (STATUT_EN_RETARD, 'En retard'),
    ]

    risque = models.ForeignKey(
        RisqueEntreprise,
        # on_delete: un plan de traitement n'existe que pour SON risque.
        on_delete=models.CASCADE,
        related_name='plans_traitement', verbose_name='Risque')
    action = models.CharField('Action', max_length=255)
    responsable = models.CharField(
        'Responsable', max_length=160, blank=True, default='')
    echeance = models.DateField('Échéance', null=True, blank=True)
    statut = models.CharField(
        'Statut', max_length=10, choices=STATUT_CHOICES,
        default=STATUT_A_FAIRE)
    cout_estime = models.DecimalField(
        'Coût estimé (MAD)', max_digits=12, decimal_places=2, default=0)
    avancement_pct = models.PositiveSmallIntegerField(
        'Avancement (%)', default=0)

    class Meta:
        verbose_name = 'Plan de traitement du risque'
        verbose_name_plural = 'Plans de traitement du risque'
        ordering = ['echeance', 'id']
        indexes = [
            models.Index(fields=['company', 'echeance'],
                         name='grc_plan_co_echeance_idx'),
            models.Index(fields=['company', 'statut'],
                         name='grc_plan_co_statut_idx'),
        ]

    def save(self, *args, **kwargs):
        """Borne l'avancement à 0-100 (un pourcentage n'excède pas 100)."""
        try:
            self.avancement_pct = max(0, min(100, int(self.avancement_pct)))
        except (TypeError, ValueError):
            self.avancement_pct = 0
        return super().save(*args, **kwargs)

    def est_en_retard(self, aujourdhui=None):
        """Échéance dépassée ET pas encore fait (jamais lu du statut stocké)."""
        if self.statut == self.STATUT_FAIT or not self.echeance:
            return False
        return self.echeance < (aujourdhui or timezone.now().date())

    def __str__(self):
        return f'{self.action} ({self.get_statut_display()})'


class RevueRisque(TenantModel):
    """NTGRC15 — revue périodique d'un risque (cadence + journal).

    Un registre des risques qu'on ne relit jamais devient une archive. Chaque
    revue est une ligne IMMUABLE de journal : elle dit qui a regardé, quand,
    ce qui a été décidé, et quand on regarde de nouveau. La date de prochaine
    revue est POUSSÉE sur le risque par le service — sinon la cadence vivrait
    dans deux endroits qui divergeraient.
    """

    DECISION_MAINTENU = 'maintenu'
    DECISION_RECLASSE = 'reclasse'
    DECISION_CLOS = 'clos'
    DECISION_CHOICES = [
        (DECISION_MAINTENU, 'Maintenu en l\'état'),
        (DECISION_RECLASSE, 'Reclassé (cotation revue)'),
        (DECISION_CLOS, 'Clos'),
    ]

    risque = models.ForeignKey(
        RisqueEntreprise,
        # on_delete: une revue n'existe que pour SON risque (journal).
        on_delete=models.CASCADE,
        related_name='revues', verbose_name='Risque')
    date_revue = models.DateField('Date de la revue')
    revu_par = models.CharField(
        'Revu par', max_length=160, blank=True, default='')
    decision = models.CharField(
        'Décision', max_length=10, choices=DECISION_CHOICES,
        default=DECISION_MAINTENU)
    commentaire = models.TextField('Commentaire', blank=True, default='')
    prochaine_revue = models.DateField(
        'Prochaine revue', null=True, blank=True)

    class Meta:
        verbose_name = 'Revue de risque'
        verbose_name_plural = 'Revues de risque'
        ordering = ['-date_revue', '-id']
        indexes = [
            models.Index(fields=['company', 'date_revue'],
                         name='grc_revue_co_date_idx'),
        ]

    def __str__(self):
        return (f'Revue {self.date_revue:%d/%m/%Y} — '
                f'{self.get_decision_display()}')


class ControleInterne(TenantModel):
    """NTGRC16 — bibliothèque des contrôles internes (SOX-lite).

    Un contrôle DÉCRIT ce qu'on vérifie, à quelle fréquence et qui en répond.
    Il ne porte AUCUN résultat : les exécutions vivent dans ``TestControle``
    (NTGRC17). Séparer les deux est ce qui permet de dire « ce contrôle
    mensuel n'a pas été testé ce mois-ci » — un modèle unique ne saurait que
    dire « le dernier test remonte à… ».
    """

    DOMAINE_CHOICES = [
        ('acces', 'Gestion des accès'),
        ('segregation_taches', 'Séparation des tâches'),
        ('cloture_compta', 'Clôture comptable'),
        ('achats', 'Achats'),
        ('paie', 'Paie'),
        ('si', "Système d'information"),
        ('sauvegarde', 'Sauvegarde & continuité'),
    ]

    TYPE_PREVENTIF = 'preventif'
    TYPE_DETECTIF = 'detectif'
    TYPE_CHOICES = [
        (TYPE_PREVENTIF, 'Préventif'),
        (TYPE_DETECTIF, 'Détectif'),
    ]

    FREQ_PERMANENT = 'permanent'
    FREQ_QUOTIDIEN = 'quotidien'
    FREQ_HEBDO = 'hebdo'
    FREQ_MENSUEL = 'mensuel'
    FREQ_TRIMESTRIEL = 'trimestriel'
    FREQ_ANNUEL = 'annuel'
    FREQUENCE_CHOICES = [
        (FREQ_PERMANENT, 'Permanent'),
        (FREQ_QUOTIDIEN, 'Quotidien'),
        (FREQ_HEBDO, 'Hebdomadaire'),
        (FREQ_MENSUEL, 'Mensuel'),
        (FREQ_TRIMESTRIEL, 'Trimestriel'),
        (FREQ_ANNUEL, 'Annuel'),
    ]

    #: Fenêtre de fraîcheur d'un test, en jours, par fréquence. Un contrôle
    #: « permanent » est vérifié en continu : sa fenêtre est celle du mois.
    FENETRE_JOURS = {
        FREQ_PERMANENT: 30,
        FREQ_QUOTIDIEN: 1,
        FREQ_HEBDO: 7,
        FREQ_MENSUEL: 30,
        FREQ_TRIMESTRIEL: 90,
        FREQ_ANNUEL: 365,
    }

    CADRE_CHOICES = [
        ('ISO27001', 'ISO 27001'),
        ('SOX', 'SOX'),
        ('CGNC', 'CGNC'),
        ('interne', 'Référentiel interne'),
    ]

    code = models.CharField('Code', max_length=40)
    intitule = models.CharField('Intitulé', max_length=200)
    objectif = models.TextField('Objectif', blank=True, default='')
    domaine = models.CharField(
        'Domaine', max_length=20, choices=DOMAINE_CHOICES, default='acces')
    type = models.CharField(
        'Type', max_length=10, choices=TYPE_CHOICES, default=TYPE_PREVENTIF)
    frequence = models.CharField(
        'Fréquence', max_length=12, choices=FREQUENCE_CHOICES,
        default=FREQ_MENSUEL)
    proprietaire = models.CharField(
        'Propriétaire', max_length=160, blank=True, default='')
    reference_cadre = models.CharField(
        'Référentiel', max_length=12, choices=CADRE_CHOICES,
        default='interne')
    actif = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Contrôle interne'
        verbose_name_plural = 'Bibliothèque de contrôles internes'
        ordering = ['code', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='grc_controleinterne_co_code'),
        ]
        indexes = [
            models.Index(fields=['company', 'domaine'],
                         name='grc_controle_co_domaine_idx'),
        ]

    @property
    def fenetre_jours(self):
        """Durée de validité d'un test efficace, selon la fréquence."""
        return self.FENETRE_JOURS.get(self.frequence, 30)

    def __str__(self):
        return f'{self.code} — {self.intitule}'


class TestControle(TenantModel):
    """NTGRC17 — exécution planifiée d'un contrôle interne + sa preuve.

    Un contrôle décrit ce qu'on vérifie (``ControleInterne``) ; un test dit
    qu'on l'a VRAIMENT vérifié, quand, sur quel échantillon, avec quelle
    conclusion et quelle pièce à l'appui. Sans cette table, un référentiel de
    contrôles ne prouve rien à un auditeur.

    La pièce de preuve est référencée par une CLÉ de stockage
    (MinIO/GED) — jamais le fichier lui-même, et jamais une FK vers un
    document d'une autre app.
    """

    RESULTAT_EFFICACE = 'efficace'
    RESULTAT_DEFICIENT = 'deficient'
    RESULTAT_NON_TESTE = 'non_teste'
    RESULTAT_CHOICES = [
        (RESULTAT_EFFICACE, 'Efficace'),
        (RESULTAT_DEFICIENT, 'Déficient'),
        (RESULTAT_NON_TESTE, 'Non testé'),
    ]

    STATUT_PLANIFIE = 'planifie'
    STATUT_REALISE = 'realise'
    STATUT_ANNULE = 'annule'
    STATUT_CHOICES = [
        (STATUT_PLANIFIE, 'Planifié'),
        (STATUT_REALISE, 'Réalisé'),
        (STATUT_ANNULE, 'Annulé'),
    ]

    controle = models.ForeignKey(
        ControleInterne,
        # on_delete: un test n'existe que pour SON contrôle.
        on_delete=models.CASCADE,
        related_name='tests', verbose_name='Contrôle')
    date_prevue = models.DateField('Date prévue', null=True, blank=True)
    date_realisee = models.DateField('Date de réalisation', null=True,
                                     blank=True)
    testeur = models.CharField(
        'Testeur', max_length=160, blank=True, default='')
    resultat = models.CharField(
        'Résultat', max_length=10, choices=RESULTAT_CHOICES,
        default=RESULTAT_NON_TESTE)
    echantillon_taille = models.PositiveIntegerField(
        "Taille de l'échantillon", default=0)
    conclusion = models.TextField('Conclusion', blank=True, default='')
    piece_preuve_key = models.CharField(
        'Clé de la pièce de preuve', max_length=500, blank=True, default='',
        help_text='Clé de stockage (MinIO/GED) — jamais le fichier lui-même.')
    statut = models.CharField(
        'Statut', max_length=10, choices=STATUT_CHOICES,
        default=STATUT_PLANIFIE)
    # Risque ouvert automatiquement quand le test conclut « déficient ». Une
    # déficience sans risque tracé disparaît au prochain comité.
    risque_ouvert = models.ForeignKey(
        RisqueEntreprise, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tests_controle_a_lorigine',
        verbose_name='Risque ouvert')

    class Meta:
        verbose_name = 'Test de contrôle'
        verbose_name_plural = 'Tests de contrôle'
        ordering = ['-date_prevue', '-id']
        indexes = [
            models.Index(fields=['company', 'resultat'],
                         name='grc_testctrl_co_resultat_idx'),
            models.Index(fields=['company', 'date_realisee'],
                         name='grc_testctrl_co_date_idx'),
        ]

    def __str__(self):
        return (f'Test {self.controle_id} — '
                f'{self.get_resultat_display()}')


class DeficienceControle(TenantModel):
    """NTGRC18 — constat de déficience sur un test de contrôle.

    Un test « déficient » dit QUE ça n'a pas marché ; la déficience dit QUOI,
    À QUEL POINT c'est grave, QUI remédie et POUR QUAND. C'est le constat
    qu'un auditeur lit, pas le résultat brut du test.

    Les liens vers le registre des risques et vers un CAPA QHSE sont des
    identifiants TEXTE (``*_ref``) : `grc` n'importe JAMAIS
    ``apps.qhse.models`` (frontière cross-app), et la déficience survit à la
    disparition de l'objet qu'elle référence.
    """

    GRAVITE_MINEURE = 'mineure'
    GRAVITE_SIGNIFICATIVE = 'significative'
    GRAVITE_MAJEURE = 'majeure'
    GRAVITE_CHOICES = [
        (GRAVITE_MINEURE, 'Mineure'),
        (GRAVITE_SIGNIFICATIVE, 'Significative'),
        (GRAVITE_MAJEURE, 'Majeure'),
    ]

    STATUT_OUVERTE = 'ouverte'
    STATUT_EN_COURS = 'en_cours'
    STATUT_CORRIGEE = 'corrigee'
    STATUT_CHOICES = [
        (STATUT_OUVERTE, 'Ouverte'),
        (STATUT_EN_COURS, 'En cours de remédiation'),
        (STATUT_CORRIGEE, 'Corrigée'),
    ]

    test_controle = models.ForeignKey(
        TestControle,
        # on_delete: un constat n'existe que pour SON test.
        on_delete=models.CASCADE,
        related_name='deficiences', verbose_name='Test de contrôle')
    gravite = models.CharField(
        'Gravité', max_length=14, choices=GRAVITE_CHOICES,
        default=GRAVITE_MINEURE)
    description = models.TextField('Description', blank=True, default='')
    remediation = models.TextField('Remédiation', blank=True, default='')
    responsable = models.CharField(
        'Responsable', max_length=160, blank=True, default='')
    echeance = models.DateField('Échéance', null=True, blank=True)
    statut = models.CharField(
        'Statut', max_length=10, choices=STATUT_CHOICES,
        default=STATUT_OUVERTE)
    risque_entreprise_ref = models.CharField(
        "Risque d'entreprise lié", max_length=64, blank=True, default='',
        help_text='Identifiant de la `grc.RisqueEntreprise` liée.')
    qhse_capa_ref = models.CharField(
        'CAPA QHSE lié', max_length=64, blank=True, default='',
        help_text='Identifiant de la `qhse.ActionCorrectivePreventive` — '
                  'référence TEXTE, jamais une FK vers une autre app.')

    class Meta:
        verbose_name = 'Déficience de contrôle'
        verbose_name_plural = 'Déficiences de contrôle'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='grc_deficience_co_statut_idx'),
            models.Index(fields=['company', 'gravite'],
                         name='grc_deficience_co_grav_idx'),
        ]

    def __str__(self):
        return (f'Déficience {self.get_gravite_display()} — '
                f'{self.get_statut_display()}')


class PolitiqueInterne(TenantModel):
    """NTGRC19 — politique interne versionnée (référentiel documentaire).

    Le corps ``contenu`` est le brouillon VIVANT : on l'édite librement tant
    que la politique n'est pas publiée. PUBLIER fige le texte dans une
    ``PolitiqueVersion`` IMMUABLE et incrémente le numéro de version.

    C'est ce qui rend une attestation de lecture (NTGRC20) crédible : dire
    « j'ai lu la v2 » n'a de sens que si la v2 ne peut plus bouger.
    """

    CATEGORIE_CHOICES = [
        ('securite', 'Sécurité'),
        ('rh', 'Ressources humaines'),
        ('achats', 'Achats'),
        ('qualite', 'Qualité'),
        ('conformite', 'Conformité'),
        ('it', 'Informatique'),
    ]

    STATUT_BROUILLON = 'brouillon'
    STATUT_PUBLIEE = 'publiee'
    STATUT_OBSOLETE = 'obsolete'
    STATUT_CHOICES = [
        (STATUT_BROUILLON, 'Brouillon'),
        (STATUT_PUBLIEE, 'Publiée'),
        (STATUT_OBSOLETE, 'Obsolète'),
    ]

    CIBLE_TOUS = 'tous'
    CIBLE_ROLE = 'role'
    CIBLE_DEPARTEMENT = 'departement'
    CIBLE_CHOICES = [
        (CIBLE_TOUS, 'Tout le monde'),
        (CIBLE_ROLE, 'Un rôle'),
        (CIBLE_DEPARTEMENT, 'Un département'),
    ]

    titre = models.CharField('Titre', max_length=200)
    categorie = models.CharField(
        'Catégorie', max_length=12, choices=CATEGORIE_CHOICES,
        default='conformite')
    contenu = models.TextField('Contenu', blank=True, default='')
    version = models.PositiveIntegerField(
        'Version', default=0,
        help_text='Incrémentée SERVEUR à chaque publication (0 = jamais '
                  'publiée).')
    statut = models.CharField(
        'Statut', max_length=10, choices=STATUT_CHOICES,
        default=STATUT_BROUILLON)
    date_publication = models.DateTimeField(
        'Date de publication', null=True, blank=True)
    proprietaire = models.CharField(
        'Propriétaire', max_length=160, blank=True, default='')
    cible = models.CharField(
        'Cible', max_length=12, choices=CIBLE_CHOICES, default=CIBLE_TOUS)
    cible_valeur = models.CharField(
        'Valeur de la cible', max_length=120, blank=True, default='',
        help_text='Rôle ou département visé quand la cible n\'est pas '
                  '« tout le monde ».')

    class Meta:
        verbose_name = 'Politique interne'
        verbose_name_plural = 'Politiques internes'
        ordering = ['titre', 'id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='grc_politique_co_statut_idx'),
        ]

    def __str__(self):
        return f'{self.titre} (v{self.version})'


class PolitiqueVersionError(Exception):
    """NTGRC19 — levée à toute tentative de modifier/supprimer une version.

    Même contrat que ``JournalDestructionError`` et ``ged.ArchivageLegalError``
    (hérite d'``Exception``) ; traduite en 403 côté vue, jamais en 500.
    """


class PolitiqueVersion(TenantModel):
    """NTGRC19 — snapshot IMMUABLE d'une politique publiée.

    Le contenu est figé à la publication : ni ``save()`` sur une ligne
    existante, ni ``delete()``. Une version qu'on peut réécrire ne prouve rien
    — et une attestation de lecture pointerait alors un texte mouvant.
    """

    politique = models.ForeignKey(
        PolitiqueInterne,
        # on_delete: une version n'existe que pour SA politique.
        on_delete=models.CASCADE,
        related_name='versions', verbose_name='Politique')
    numero = models.PositiveIntegerField('Numéro de version')
    contenu = models.TextField('Contenu figé', blank=True, default='')
    auteur = models.CharField(
        'Auteur', max_length=150, blank=True, default='',
        help_text="Instantané du nom d'utilisateur (survit à la suppression "
                  'du compte).')
    publiee_le = models.DateTimeField('Publiée le', null=True, blank=True)

    class Meta:
        verbose_name = 'Version de politique'
        verbose_name_plural = 'Versions de politique'
        ordering = ['-numero', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['politique', 'numero'],
                name='grc_politiqueversion_pol_num'),
        ]

    def save(self, *args, **kwargs):
        """Création SEULE : une version publiée ne se réécrit jamais."""
        if self.pk is not None:
            raise PolitiqueVersionError(
                'Une version de politique est immuable (création seule) : '
                'elle ne peut pas être modifiée.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Refuse la suppression : l'historique des versions fait foi."""
        raise PolitiqueVersionError(
            'Une version de politique est immuable : elle ne peut pas être '
            'supprimée.')

    def __str__(self):
        return f'{self.politique_id} v{self.numero}'


class AttestationPolitique(TenantModel):
    """NTGRC20 — attestation de LECTURE d'une politique, par un employé.

    Une politique publiée que personne n'a lue ne protège de rien : c'est
    l'attestation qui transforme un document en obligation opposable. Elle
    porte donc le NUMÉRO DE VERSION attesté — « j'ai lu la charte » ne veut
    rien dire, « j'ai lu la v3 du 12/09 » en veut un, parce que la v3 est
    figée (``PolitiqueVersion``, NTGRC19) et ne peut plus bouger.

    Loi 53-05 (échange électronique de données juridiques, Maroc) : la preuve
    d'un engagement électronique simple repose sur l'identification de son
    auteur et l'intégrité de l'acte. On conserve donc, CÔTÉ SERVEUR
    uniquement : le NOM SAISI par l'attestant (son geste de signature), un
    instantané de son nom d'affichage, l'horodatage serveur, et l'IP/le
    user-agent du poste. Rien de tout cela n'est lu du corps de la requête —
    une preuve qu'on peut s'envoyer à soi-même n'est pas une preuve.

    L'employé est désigné par un identifiant TEXTE (``employe_ref``, l'id du
    ``rh.DossierEmploye``) : ``grc`` n'importe jamais les modèles de ``rh``,
    et l'attestation survit à la clôture du dossier — c'est précisément ce
    qu'un auditeur vient vérifier trois ans plus tard.
    """

    politique = models.ForeignKey(
        PolitiqueInterne,
        # on_delete: une attestation n'existe que pour SA politique ; la
        # politique supprimée, l'attestation n'atteste plus de rien.
        on_delete=models.CASCADE,
        related_name='attestations', verbose_name='Politique')
    version_attestee = models.PositiveIntegerField(
        'Version attestée',
        help_text='Numéro de la version FIGÉE que la personne déclare avoir '
                  'lue (jamais 0 : une politique non publiée ne s\'atteste '
                  'pas).')
    employe_ref = models.CharField(
        'Dossier employé', max_length=64, blank=True, default='',
        help_text='Identifiant texte du rh.DossierEmploye (string-FK).')
    attestant_nom = models.CharField(
        'Attestant', max_length=160, blank=True, default='',
        help_text="Instantané du nom d'affichage (survit au départ).")
    nom_saisi = models.CharField(
        'Nom saisi (loi 53-05)', max_length=160, blank=True, default='',
        help_text='Nom tapé par la personne au moment d\'attester — son '
                  'geste de signature électronique simple.')
    date_attestation = models.DateTimeField(
        'Date d\'attestation', null=True, blank=True,
        help_text='Horodatage SERVEUR, posé à la création.')
    preuve = models.JSONField(
        'Preuve', default=dict, blank=True,
        help_text='IP et user-agent du poste attestant, posés côté serveur.')

    class Meta:
        verbose_name = 'Attestation de politique'
        verbose_name_plural = 'Attestations de politique'
        ordering = ['-date_attestation', '-id']
        constraints = [
            # Une personne n'atteste qu'UNE FOIS une version donnée : sans
            # cette unicité, un double clic gonflerait le taux d'attestation
            # au-dessus de 100 %. La condition écarte les lignes sans dossier
            # employé (attestation saisie pour un tiers non salarié), que
            # Postgres ne doit pas agréger sur la chaîne vide.
            models.UniqueConstraint(
                fields=['politique', 'version_attestee', 'employe_ref'],
                condition=~models.Q(employe_ref=''),
                name='grc_attestation_pol_ver_emp'),
        ]
        indexes = [
            models.Index(fields=['company', 'politique'],
                         name='grc_attestation_co_pol_idx'),
        ]

    def save(self, *args, **kwargs):
        """Horodate CÔTÉ SERVEUR à la création (jamais une date du client)."""
        if self.date_attestation is None:
            self.date_attestation = timezone.now()
        return super().save(*args, **kwargs)

    def __str__(self):
        return (f'{self.attestant_nom or self.employe_ref or "?"} — '
                f'politique {self.politique_id} v{self.version_attestee}')


class QuestionnaireFournisseur(TenantModel):
    """NTGRC22 — questionnaire de conformité adressé à un fournisseur.

    Le maillon manquant de la conformité : une société peut avoir un RoPA
    impeccable et un sous-traitant qui stocke ses données n'importe où. L'art.
    28 du RGPD (et la loi 09-08 côté marocain) impose de s'assurer des
    garanties du sous-traitant — ce questionnaire est la trace de cette
    diligence, avec sa date, ses réponses et son score.

    Le fournisseur est désigné par un identifiant TEXTE
    (``fournisseur_ref`` = id du ``stock.Fournisseur``) : ``grc`` n'importe
    jamais ``stock.models`` et le questionnaire survit à la fiche fournisseur.

    ``statut`` ne s'écrit PAS au champ : il bouge par le service
    (``changer_statut_questionnaire``) ou automatiquement quand toutes les
    réponses sont renseignées — un questionnaire déclaré « complet » alors que
    la moitié des questions est vide ne prouverait rien.
    """

    TYPE_SECURITE = 'securite'
    TYPE_RGPD = 'rgpd'
    TYPE_QUALITE = 'qualite'
    TYPE_RSE = 'rse'
    TYPE_CHOICES = [
        (TYPE_SECURITE, 'Sécurité'),
        (TYPE_RGPD, 'RGPD / données personnelles'),
        (TYPE_QUALITE, 'Qualité'),
        (TYPE_RSE, 'RSE'),
    ]

    STATUT_ENVOYE = 'envoye'
    STATUT_EN_COURS = 'en_cours'
    STATUT_COMPLETE = 'complete'
    STATUT_VALIDE = 'valide'
    STATUT_REFUSE = 'refuse'
    STATUT_CHOICES = [
        (STATUT_ENVOYE, 'Envoyé'),
        (STATUT_EN_COURS, 'En cours'),
        (STATUT_COMPLETE, 'Complété'),
        (STATUT_VALIDE, 'Validé'),
        (STATUT_REFUSE, 'Refusé'),
    ]

    fournisseur_ref = models.CharField(
        'Fournisseur', max_length=64, blank=True, default='',
        help_text='Identifiant texte du stock.Fournisseur (string-FK).')
    type = models.CharField(
        'Type', max_length=10, choices=TYPE_CHOICES, default=TYPE_RGPD)
    statut = models.CharField(
        'Statut', max_length=10, choices=STATUT_CHOICES,
        default=STATUT_ENVOYE)
    date_envoi = models.DateField('Date d\'envoi', null=True, blank=True)
    date_echeance = models.DateField('Échéance', null=True, blank=True)
    score = models.PositiveIntegerField(
        'Score de conformité (%)', default=0,
        help_text='Part des réponses CONFORMES sur le total des questions, '
                  'recalculée serveur — jamais saisie.')
    evaluateur = models.CharField(
        'Évaluateur', max_length=160, blank=True, default='')
    # NTGRC23 — modèle d'origine (identifiant texte : un questionnaire envoyé
    # ne doit pas changer de contenu parce qu'on a édité son modèle après coup,
    # et il survit à la suppression de celui-ci).
    modele_ref = models.CharField(
        'Modèle d\'origine', max_length=64, blank=True, default='')

    class Meta:
        verbose_name = 'Questionnaire fournisseur'
        verbose_name_plural = 'Questionnaires fournisseurs'
        ordering = ['-date_envoi', '-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='grc_questionnaire_co_st_idx'),
            models.Index(fields=['company', 'fournisseur_ref'],
                         name='grc_questionnaire_co_frn_idx'),
        ]

    def __str__(self):
        return (f'{self.get_type_display()} — fournisseur '
                f'{self.fournisseur_ref or "?"} '
                f'({self.get_statut_display()})')


class ReponseQuestionnaire(TenantModel):
    """NTGRC22 — une question et la réponse du fournisseur.

    ``conforme`` est un booléen NULLABLE à trois états VOULUS : ``True``
    (conforme), ``False`` (non conforme), ``None`` (pas encore évalué). Forcer
    un défaut ``False`` ferait passer une question non évaluée pour un écart —
    et un questionnaire vide afficherait 100 % de non-conformité.
    """

    questionnaire = models.ForeignKey(
        QuestionnaireFournisseur,
        # on_delete: une réponse n'existe que dans SON questionnaire.
        on_delete=models.CASCADE,
        related_name='reponses', verbose_name='Questionnaire')
    ordre = models.PositiveIntegerField('Ordre', default=0)
    question = models.TextField('Question')
    obligatoire = models.BooleanField('Obligatoire', default=True)
    reponse = models.TextField('Réponse', blank=True, default='')
    conforme = models.BooleanField(
        'Conforme', null=True, blank=True,
        help_text='Vide = pas encore évalué (surtout pas « non conforme »).')
    commentaire = models.TextField('Commentaire', blank=True, default='')
    piece_key = models.CharField(
        'Pièce justificative', max_length=255, blank=True, default='',
        help_text='Clé de stockage (MinIO/GED) de la preuve fournie.')

    class Meta:
        verbose_name = 'Réponse de questionnaire'
        verbose_name_plural = 'Réponses de questionnaire'
        ordering = ['ordre', 'id']
        indexes = [
            models.Index(fields=['company', 'questionnaire'],
                         name='grc_reponseq_co_quest_idx'),
        ]

    @property
    def est_repondue(self):
        """Une question est répondue dès qu'elle porte un texte non vide."""
        return bool((self.reponse or '').strip())

    def __str__(self):
        return f'Q{self.ordre} — {self.question[:60]}'


class ModeleQuestionnaire(TenantModel):
    """NTGRC23 — trame réutilisable d'un questionnaire fournisseur.

    Personne ne réécrit trente questions RGPD à chaque nouveau sous-traitant :
    on instancie une trame. Les questions vivent dans un champ JSON — une
    liste de ``{intitule, obligatoire, type_reponse}`` — parce qu'un modèle
    est un DOCUMENT, pas un mini-schéma relationnel : on l'édite d'un bloc et
    on ne requête jamais « toutes les questions de tous les modèles ».

    L'instanciation COPIE les questions dans le questionnaire (NTGRC22) :
    éditer le modèle après coup ne doit pas réécrire un questionnaire déjà
    envoyé — le fournisseur aurait répondu à autre chose que ce qu'on lit.
    """

    TYPE_CHOICES = QuestionnaireFournisseur.TYPE_CHOICES

    code = models.CharField(
        'Code', max_length=80,
        help_text='Clé stable du modèle (seed idempotent).')
    nom = models.CharField('Nom', max_length=200)
    type = models.CharField(
        'Type', max_length=10, choices=TYPE_CHOICES,
        default=QuestionnaireFournisseur.TYPE_RGPD)
    questions = models.JSONField(
        'Questions', default=list, blank=True,
        help_text='Liste de {intitule, obligatoire, type_reponse} — ex. '
                  '[{"intitule": "Où hébergez-vous les données ?", '
                  '"obligatoire": true, "type_reponse": "texte"}].')
    actif = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Modèle de questionnaire'
        verbose_name_plural = 'Modèles de questionnaire'
        ordering = ['nom', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='grc_modelequestionnaire_co_code'),
        ]

    def __str__(self):
        return f'{self.nom} ({self.get_type_display()})'
