from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class TimestampedModel(models.Model):
    """
    Modèle abstrait de base — ajoute created_at
    / updated_at à tout modèle qui en hérite.
    Usage : class MonModele(TimestampedModel): ...
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AnomalyFlag(TimestampedModel):
    """FG360 — Signalement d'anomalie détectée (stock / paiements / fraude).

    Modèle de FONDATION, volontairement GÉNÉRIQUE : il ne référence AUCUN modèle
    métier (core doit rester une couche de base — contrat import-linter
    ``core-foundation-is-a-base-layer``). Le sujet de l'anomalie est désigné par
    une paire ``subject_type`` (libellé d'app/modèle, ex. ``'stock.Produit'``) +
    ``subject_id`` (chaîne) au lieu d'une vraie ForeignKey — pas d'import métier.

    Multi-tenant : ``company`` est obligatoire et toujours imposé côté serveur ;
    les querysets doivent filtrer par société (voir ``core.mixins.TenantMixin``).
    Un scan planifié (``core.anomaly.scan_for_outliers`` + ``record_anomaly``)
    repère les valeurs aberrantes et matérialise un ``AnomalyFlag`` par cas.
    """

    CATEGORY_STOCK = 'stock'
    CATEGORY_PAIEMENT = 'paiement'
    CATEGORY_FRAUDE = 'fraude'
    CATEGORY_AUTRE = 'autre'
    CATEGORY_CHOICES = [
        (CATEGORY_STOCK, 'Stock'),
        (CATEGORY_PAIEMENT, 'Paiement'),
        (CATEGORY_FRAUDE, 'Fraude'),
        (CATEGORY_AUTRE, 'Autre'),
    ]

    SEVERITY_INFO = 'info'
    SEVERITY_AVERTISSEMENT = 'avertissement'
    SEVERITY_CRITIQUE = 'critique'
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, 'Information'),
        (SEVERITY_AVERTISSEMENT, 'Avertissement'),
        (SEVERITY_CRITIQUE, 'Critique'),
    ]

    STATUS_OUVERT = 'ouvert'
    STATUS_EXAMINE = 'examine'
    STATUS_IGNORE = 'ignore'
    STATUS_RESOLU = 'resolu'
    STATUS_CHOICES = [
        (STATUS_OUVERT, 'Ouvert'),
        (STATUS_EXAMINE, 'En cours d\'examen'),
        (STATUS_IGNORE, 'Ignoré'),
        (STATUS_RESOLU, 'Résolu'),
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='anomaly_flags', verbose_name='Société')

    category = models.CharField(
        'Catégorie', max_length=20, choices=CATEGORY_CHOICES,
        default=CATEGORY_AUTRE)
    severity = models.CharField(
        'Gravité', max_length=20, choices=SEVERITY_CHOICES,
        default=SEVERITY_AVERTISSEMENT)
    status = models.CharField(
        'Statut', max_length=20, choices=STATUS_CHOICES,
        default=STATUS_OUVERT)

    # Désignation générique du sujet (PAS de FK métier — core reste fondation).
    subject_type = models.CharField(
        'Type de sujet', max_length=100, blank=True,
        help_text='Libellé app.Modèle, ex. « stock.Produit » (générique).')
    subject_id = models.CharField('Identifiant du sujet', max_length=64, blank=True)

    # Métrique qui a déclenché l'alerte.
    metric = models.CharField('Métrique', max_length=80, blank=True)
    value = models.FloatField('Valeur observée', null=True, blank=True)
    expected = models.FloatField('Valeur attendue', null=True, blank=True)
    score = models.FloatField(
        'Score d\'aberration', null=True, blank=True,
        help_text='Écart standardisé (z-score) ou amplitude relative.')

    message = models.CharField('Message', max_length=255)
    detail = models.JSONField('Détail', default=dict, blank=True)

    detected_at = models.DateTimeField('Détecté le', auto_now_add=True)

    class Meta:
        verbose_name = 'Anomalie détectée'
        verbose_name_plural = 'Anomalies détectées'
        ordering = ['-detected_at']
        indexes = [
            # Noms courts (≤30) et déterministes — pas de hash divergent.
            models.Index(fields=['company', 'status'], name='anomaly_company_status_idx'),
            models.Index(fields=['company', 'category'], name='anomaly_company_cat_idx'),
        ]

    def __str__(self):
        return f'[{self.get_severity_display()}] {self.message}'


# ---------------------------------------------------------------------------
# FG366 — Moteur de workflow multi-étapes (BPM) + SLA / escalades.
#
# Composant d'architecture GÉNÉRIQUE et de FONDATION : il permet à n'importe
# quel modèle métier de faire tourner une chaîne d'approbation multi-étapes
# (avec minuteries SLA) SANS que ``core`` n'importe une seule app métier
# (contrat import-linter ``core-foundation-is-a-base-layer``). La cible d'une
# instance est désignée via ``contenttypes`` (couche de fondation Django) —
# ``content_type`` + ``object_id`` + ``GenericForeignKey`` — donc on peut
# attacher un workflow à un Devis, un Contrat, un BonCommande… sans aucun
# import descendant interdit.
#
# Deux niveaux :
#   * Le MODÈLE (template) — ``WorkflowDefinition`` + ``WorkflowStepDefinition``
#     décrit les étapes d'une chaîne (ordre, type d'approbation, SLA, rôle
#     requis, cible d'escalade).
#   * L'EXÉCUTION (runtime) — ``WorkflowInstance`` (rattachée à une cible
#     générique) + ``WorkflowStepInstance`` (une par étape, avec échéance SLA
#     calculée et décision).
#
# Multi-tenant : ``company`` est obligatoire sur les quatre modèles. La logique
# d'avancement et de calcul SLA vit dans ``core.workflow`` (services purs où le
# « maintenant » est toujours passé explicitement — déterminisme testable).
# ---------------------------------------------------------------------------


class WorkflowDefinition(TimestampedModel):
    """Template d'une chaîne d'approbation multi-étapes (FG366).

    GÉNÉRIQUE : ne référence aucun modèle métier. Identifié par un ``code``
    stable par société (ex. ``'validation_devis'``) ; ses étapes ordonnées
    vivent dans ``WorkflowStepDefinition``.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='core_workflow_definitions', verbose_name='Société')

    code = models.CharField(
        'Code', max_length=64,
        help_text='Identifiant stable par société, ex. « validation_devis ».')
    nom = models.CharField('Nom', max_length=120)
    description = models.TextField('Description', blank=True, default='')
    actif = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Définition de workflow'
        verbose_name_plural = 'Définitions de workflow'
        ordering = ['nom', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='core_wf_def_company_code_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='core_wf_def_co_actif_idx'),
        ]

    def __str__(self):
        return f'{self.nom} ({self.code})'


class WorkflowStepDefinition(TimestampedModel):
    """Une étape ordonnée d'un ``WorkflowDefinition`` (FG366).

    ``type_approbation`` décrit comment l'étape se franchit ; ``sla_heures``
    (nullable) fixe la minuterie SLA ; ``role_requis`` (texte libre, aligné sur
    ``roles.Role.nom`` mais SANS FK pour rester découplé) et ``escalade_vers``
    (étape ou destinataire visé en cas de dépassement) restent optionnels.
    """

    APPROBATION_MANUELLE = 'manuelle'
    APPROBATION_AUTO = 'auto'
    APPROBATION_ROLE = 'role'
    APPROBATION_CHOICES = [
        (APPROBATION_MANUELLE, 'Manuelle'),
        (APPROBATION_AUTO, 'Automatique'),
        (APPROBATION_ROLE, 'Par rôle'),
    ]

    definition = models.ForeignKey(
        WorkflowDefinition, on_delete=models.CASCADE,
        related_name='steps', verbose_name='Définition')

    ordre = models.PositiveIntegerField('Ordre', default=0)
    nom = models.CharField('Nom', max_length=120)
    type_approbation = models.CharField(
        "Type d'approbation", max_length=16,
        choices=APPROBATION_CHOICES, default=APPROBATION_MANUELLE)
    sla_heures = models.PositiveIntegerField(
        'SLA (heures)', null=True, blank=True,
        help_text='Délai cible avant escalade ; vide = pas de minuterie SLA.')
    role_requis = models.CharField(
        'Rôle requis', max_length=80, blank=True, default='',
        help_text='Libellé de rôle attendu pour franchir (générique, sans FK).')
    escalade_vers = models.CharField(
        'Escalade vers', max_length=120, blank=True, default='',
        help_text='Destinataire/rôle visé si le SLA est dépassé (générique).')

    class Meta:
        verbose_name = 'Étape de workflow (modèle)'
        verbose_name_plural = 'Étapes de workflow (modèle)'
        ordering = ['definition', 'ordre', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['definition', 'ordre'],
                name='core_wf_step_def_ordre_uniq'),
        ]
        indexes = [
            models.Index(fields=['definition', 'ordre'],
                         name='core_wf_stepdef_ord_idx'),
        ]

    def __str__(self):
        return f'{self.ordre}. {self.nom}'


class WorkflowInstance(TimestampedModel):
    """Exécution en cours d'un ``WorkflowDefinition`` sur une cible (FG366).

    La cible est GÉNÉRIQUE (``content_type`` + ``object_id`` +
    ``GenericForeignKey``) : n'importe quel modèle peut porter un workflow sans
    que ``core`` ne l'importe. ``etape_courante`` pointe l'index (1-based) de
    l'étape active ; ``statut`` suit le cycle de vie global.
    """

    STATUT_EN_COURS = 'en_cours'
    STATUT_TERMINE = 'termine'
    STATUT_ANNULE = 'annule'
    STATUT_CHOICES = [
        (STATUT_EN_COURS, 'En cours'),
        (STATUT_TERMINE, 'Terminé'),
        (STATUT_ANNULE, 'Annulé'),
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='core_workflow_instances', verbose_name='Société')
    definition = models.ForeignKey(
        WorkflowDefinition, on_delete=models.PROTECT,
        related_name='instances', verbose_name='Définition')

    # Cible générique — AUCUN import métier (contenttypes = fondation).
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE,
        related_name='+', verbose_name='Type de cible')
    object_id = models.PositiveIntegerField('Identifiant de la cible')
    target = GenericForeignKey('content_type', 'object_id')

    statut = models.CharField(
        'Statut', max_length=16, choices=STATUT_CHOICES,
        default=STATUT_EN_COURS)
    etape_courante = models.PositiveIntegerField(
        'Étape courante', default=1,
        help_text="Position (1-based) de l'étape active.")

    started_le = models.DateTimeField('Démarré le', null=True, blank=True)
    ended_le = models.DateTimeField('Terminé le', null=True, blank=True)

    class Meta:
        verbose_name = 'Instance de workflow'
        verbose_name_plural = 'Instances de workflow'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='core_wf_inst_co_statut_idx'),
            models.Index(fields=['content_type', 'object_id'],
                         name='core_wf_inst_target_idx'),
        ]

    def __str__(self):
        return f'{self.definition.code} #{self.pk} ({self.get_statut_display()})'


class WorkflowStepInstance(TimestampedModel):
    """Étape concrète d'une ``WorkflowInstance`` (FG366).

    Reçoit une copie figée de la définition d'étape (``step_def``), calcule son
    échéance SLA (``sla_echeance = started + sla_heures``) et garde la décision
    (``statut``, ``assignee``, ``decided_le``, ``commentaire``).
    """

    STATUT_EN_ATTENTE = 'en_attente'
    STATUT_APPROUVE = 'approuve'
    STATUT_REJETE = 'rejete'
    STATUT_ESCALADE = 'escalade'
    STATUT_CHOICES = [
        (STATUT_EN_ATTENTE, 'En attente'),
        (STATUT_APPROUVE, 'Approuvé'),
        (STATUT_REJETE, 'Rejeté'),
        (STATUT_ESCALADE, 'Escaladé'),
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='core_workflow_step_instances', verbose_name='Société')
    instance = models.ForeignKey(
        WorkflowInstance, on_delete=models.CASCADE,
        related_name='step_instances', verbose_name='Instance')
    step_def = models.ForeignKey(
        WorkflowStepDefinition, on_delete=models.PROTECT,
        related_name='step_instances', verbose_name="Définition d'étape")

    ordre = models.PositiveIntegerField('Ordre', default=0)
    statut = models.CharField(
        'Statut', max_length=16, choices=STATUT_CHOICES,
        default=STATUT_EN_ATTENTE)
    assignee = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='core_workflow_steps',
        verbose_name='Assigné')

    sla_echeance = models.DateTimeField(
        'Échéance SLA', null=True, blank=True,
        help_text='started + sla_heures ; vide si l\'étape n\'a pas de SLA.')
    decided_le = models.DateTimeField('Décidé le', null=True, blank=True)
    commentaire = models.TextField('Commentaire', blank=True, default='')

    class Meta:
        verbose_name = 'Étape de workflow (instance)'
        verbose_name_plural = 'Étapes de workflow (instance)'
        ordering = ['instance', 'ordre', 'id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='core_wf_si_co_statut_idx'),
            models.Index(fields=['instance', 'ordre'],
                         name='core_wf_si_inst_ord_idx'),
            models.Index(fields=['statut', 'sla_echeance'],
                         name='core_wf_si_sla_idx'),
        ]

    def __str__(self):
        return f'{self.instance_id}/{self.ordre} ({self.get_statut_display()})'


# ---------------------------------------------------------------------------
# FG371+ — Configuration générique des INTÉGRATIONS externes (fondation).
#
# Modèle de FONDATION volontairement GÉNÉRIQUE : il stocke, PAR SOCIÉTÉ, le
# paramétrage d'un connecteur externe (SMS, e-signature, IMAP, calendrier,
# géocodage, Sage/CEGID, Odoo, open banking…) SANS référencer aucune app métier
# (contrat import-linter ``core-foundation-is-a-base-layer``). Le connecteur
# concret est désigné par deux chaînes — ``integration_type`` (ex. « sms ») +
# ``provider`` (ex. « infobip ») — résolues via le registre ``core.integrations``.
#
# Sécurité : le secret réel (clé d'API…) N'EST JAMAIS stocké en clair. Le champ
# ``secret_ref`` nomme une variable d'environnement (ex. « SMS_API_KEY ») d'où
# le secret est lu à l'exécution (cf. ``core.integrations.resolve_secret``). Les
# autres paramètres non sensibles vivent dans ``settings`` (JSON).
# ---------------------------------------------------------------------------


class IntegrationConfig(TimestampedModel):
    """Paramétrage d'un connecteur d'intégration externe, par société (FG371+).

    GÉNÉRIQUE : aucune FK métier. ``integration_type`` + ``provider`` pointent
    un connecteur enregistré dans ``core.integrations`` ; ``settings`` porte les
    paramètres non sensibles (JSON) ; ``secret_ref`` nomme la variable
    d'environnement contenant le secret (jamais en clair). ``actif`` permet de
    couper une intégration sans la supprimer.

    Multi-tenant : ``company`` obligatoire, imposée côté serveur. Unique par
    ``(company, integration_type, provider)``.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='integration_configs', verbose_name='Société')

    integration_type = models.CharField(
        "Type d'intégration", max_length=40,
        help_text='Catégorie, ex. « sms », « esign », « geocoding ».')
    provider = models.CharField(
        'Fournisseur', max_length=60,
        help_text='Code du connecteur enregistré, ex. « infobip ».')
    label = models.CharField('Libellé', max_length=120, blank=True, default='')

    actif = models.BooleanField('Actif', default=True)
    settings = models.JSONField(
        'Paramètres', default=dict, blank=True,
        help_text='Paramètres NON sensibles (JSON). Jamais de secret en clair.')
    secret_ref = models.CharField(
        "Référence du secret", max_length=120, blank=True, default='',
        help_text="Nom de variable d'environnement contenant le secret.")

    class Meta:
        verbose_name = "Configuration d'intégration"
        verbose_name_plural = "Configurations d'intégration"
        ordering = ['integration_type', 'provider', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'integration_type', 'provider'],
                name='core_integration_co_type_prov'),
        ]
        indexes = [
            models.Index(fields=['company', 'integration_type'],
                         name='core_integ_co_type_idx'),
            models.Index(fields=['company', 'actif'],
                         name='core_integ_co_actif_idx'),
        ]

    def __str__(self):
        return (f'{self.integration_type}/{self.provider} '
                f'(société {self.company_id})')
