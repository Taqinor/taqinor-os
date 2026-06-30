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


# ---------------------------------------------------------------------------
# FG372 — Demande d'e-signature (Yousign/DocuSign…), suivi de statut.
#
# Modèle de FONDATION GÉNÉRIQUE : suit une demande de signature électronique
# pour N'IMPORTE QUEL document métier (Devis, contrat…) SANS importer l'app qui
# le produit (contrat import-linter ``core-foundation-is-a-base-layer``). La
# cible est désignée via ``contenttypes`` (content_type + object_id +
# GenericForeignKey) — fondation Django — donc aucun import descendant.
# ---------------------------------------------------------------------------


class EsignRequest(TimestampedModel):
    """Demande de signature électronique d'un document (FG372).

    GÉNÉRIQUE : cible via ``contenttypes`` (aucun import métier). ``provider``
    nomme le connecteur e-sign (``core.esign``) ; ``external_id`` garde la
    référence retournée par le fournisseur ; ``statut`` suit le cycle de vie.
    Multi-tenant : ``company`` obligatoire, imposée côté serveur.
    """

    STATUT_BROUILLON = 'brouillon'
    STATUT_ENVOYE = 'envoye'
    STATUT_SIGNE = 'signe'
    STATUT_REFUSE = 'refuse'
    STATUT_EXPIRE = 'expire'
    STATUT_ERREUR = 'erreur'
    STATUT_CHOICES = [
        (STATUT_BROUILLON, 'Brouillon'),
        (STATUT_ENVOYE, 'Envoyé'),
        (STATUT_SIGNE, 'Signé'),
        (STATUT_REFUSE, 'Refusé'),
        (STATUT_EXPIRE, 'Expiré'),
        (STATUT_ERREUR, 'Erreur'),
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='esign_requests', verbose_name='Société')

    # Cible générique — AUCUN import métier (contenttypes = fondation).
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True,
        related_name='+', verbose_name='Type de document')
    object_id = models.PositiveIntegerField(
        'Identifiant du document', null=True, blank=True)
    target = GenericForeignKey('content_type', 'object_id')

    provider = models.CharField('Fournisseur', max_length=60)
    external_id = models.CharField(
        'Référence externe', max_length=128, blank=True, default='',
        help_text='Identifiant retourné par le fournisseur e-sign.')
    statut = models.CharField(
        'Statut', max_length=16, choices=STATUT_CHOICES,
        default=STATUT_BROUILLON)

    signataire_email = models.EmailField('Email signataire', blank=True, default='')
    signataire_nom = models.CharField(
        'Nom signataire', max_length=160, blank=True, default='')
    signed_url = models.URLField('URL document signé', blank=True, default='')

    sent_le = models.DateTimeField('Envoyé le', null=True, blank=True)
    signed_le = models.DateTimeField('Signé le', null=True, blank=True)
    detail = models.JSONField('Détail', default=dict, blank=True)

    class Meta:
        verbose_name = 'Demande de signature électronique'
        verbose_name_plural = 'Demandes de signature électronique'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='core_esign_co_statut_idx'),
            models.Index(fields=['provider', 'external_id'],
                         name='core_esign_ext_idx'),
        ]

    def __str__(self):
        return f'E-sign {self.provider} #{self.pk} ({self.get_statut_display()})'


# ---------------------------------------------------------------------------
# FG374 — Sync calendrier Google/Outlook (2-way) : table de correspondance.
#
# Modèle de FONDATION GÉNÉRIQUE : associe l'identité d'un événement LOCAL
# (pose/intervention/visite — désigné de façon générique par
# ``local_kind`` + ``local_id``, JAMAIS par une FK métier) à son équivalent
# dans un calendrier externe (``provider`` + ``external_event_id``). ``core``
# n'importe donc aucune app métier (contrat import-linter
# ``core-foundation-is-a-base-layer``) : l'app ``reporting`` qui agrège les
# événements passera de simples dicts au moteur de sync.
# ---------------------------------------------------------------------------


class CalendarSyncMapping(TimestampedModel):
    """Correspondance événement local ↔ événement de calendrier externe (FG374).

    GÉNÉRIQUE : ``local_kind`` (ex. « intervention ») + ``local_id`` (chaîne)
    identifient l'événement local SANS FK métier. ``last_hash`` détecte les
    changements pour ne pousser que les diffs (sync 2-way idempotente).
    Multi-tenant : ``company`` obligatoire. Unique par
    ``(company, provider, local_kind, local_id)``.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='calendar_sync_mappings', verbose_name='Société')

    provider = models.CharField('Fournisseur', max_length=60)
    local_kind = models.CharField(
        "Type local", max_length=40,
        help_text="Catégorie d'événement local, ex. « intervention ».")
    local_id = models.CharField("Identifiant local", max_length=64)
    external_event_id = models.CharField(
        "Identifiant externe", max_length=255, blank=True, default='')
    external_calendar_id = models.CharField(
        "Calendrier externe", max_length=255, blank=True, default='')

    last_hash = models.CharField(
        "Empreinte", max_length=64, blank=True, default='',
        help_text='Hash du dernier état synchronisé (détection de diff).')
    last_synced_le = models.DateTimeField(
        'Dernière synchro', null=True, blank=True)

    class Meta:
        verbose_name = 'Correspondance calendrier'
        verbose_name_plural = 'Correspondances calendrier'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'provider', 'local_kind', 'local_id'],
                name='core_calsync_co_prov_local'),
        ]
        indexes = [
            models.Index(fields=['company', 'provider'],
                         name='core_calsync_co_prov_idx'),
            models.Index(fields=['provider', 'external_event_id'],
                         name='core_calsync_ext_idx'),
        ]

    def __str__(self):
        return f'{self.provider}:{self.local_kind}/{self.local_id}'


# ---------------------------------------------------------------------------
# FG376 — Connecteur Zapier / Make : abonnements webhook (REST hooks) sortants.
#
# Modèle de FONDATION GÉNÉRIQUE : un outil no-code (Zapier/Make) s'abonne à un
# nom d'événement (chaîne libre, ex. « devis_accepted ») en enregistrant une URL
# cible. Quand l'événement se produit, ``core.webhooks.dispatch_event`` POSTe le
# payload à chaque URL abonnée. AUCUN import d'app métier (contrat import-linter
# ``core-foundation-is-a-base-layer``) : les apps émettrices passent un dict.
# ---------------------------------------------------------------------------


class WebhookSubscription(TimestampedModel):
    """Abonnement webhook sortant (REST hook) pour Zapier/Make (FG376).

    GÉNÉRIQUE : ``event`` est un nom d'événement en texte libre ; ``target_url``
    reçoit le payload en POST. ``secret`` (optionnel) sert à signer le payload
    (HMAC) pour que l'abonné vérifie l'authenticité. Multi-tenant : ``company``
    obligatoire. Unique par ``(company, event, target_url)``.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='webhook_subscriptions', verbose_name='Société')

    event = models.CharField(
        'Événement', max_length=80,
        help_text='Nom d\'événement, ex. « devis_accepted ».')
    target_url = models.URLField('URL cible', max_length=500)
    secret = models.CharField(
        'Secret de signature', max_length=120, blank=True, default='',
        help_text='Optionnel : clé HMAC pour signer le payload (en-tête '
                  'X-Taqinor-Signature).')
    actif = models.BooleanField('Actif', default=True)

    last_delivery_le = models.DateTimeField(
        'Dernière livraison', null=True, blank=True)
    last_status = models.IntegerField(
        'Dernier statut HTTP', null=True, blank=True)

    class Meta:
        verbose_name = 'Abonnement webhook'
        verbose_name_plural = 'Abonnements webhook'
        ordering = ['event', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'event', 'target_url'],
                name='core_webhook_co_evt_url'),
        ]
        indexes = [
            models.Index(fields=['company', 'event', 'actif'],
                         name='core_webhook_co_evt_idx'),
        ]

    def __str__(self):
        return f'{self.event} → {self.target_url}'


# ---------------------------------------------------------------------------
# FG381 — Constructeur de graphiques/dashboards sans-code (drag-and-drop).
#
# Modèle de FONDATION GÉNÉRIQUE : persiste un dashboard sauvegardé par
# utilisateur/société. La configuration (widgets, disposition, requêtes de
# données) est un BLOB JSON OPAQUE pour ``core`` — il ne sait RIEN des modèles
# métier interrogés (contrat import-linter ``core-foundation-is-a-base-layer``).
# Le front (Recharts) interprète le JSON ; les données viennent d'endpoints
# existants (reporting / pivot FG380). ``core`` ne fait que stocker/servir.
# ---------------------------------------------------------------------------


class Dashboard(TimestampedModel):
    """Dashboard sans-code sauvegardé (FG381).

    GÉNÉRIQUE : ``layout`` est un JSON opaque (widgets + disposition + specs de
    requête). ``owner`` (optionnel) restreint un dashboard à un utilisateur ;
    ``partage`` rend un dashboard visible à toute la société. Multi-tenant :
    ``company`` obligatoire, imposée côté serveur.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='dashboards', verbose_name='Société')
    owner = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.CASCADE,
        null=True, blank=True, related_name='dashboards',
        verbose_name='Propriétaire',
        help_text='Vide = dashboard de société (non personnel).')

    titre = models.CharField('Titre', max_length=160)
    description = models.TextField('Description', blank=True, default='')
    layout = models.JSONField(
        'Configuration', default=dict, blank=True,
        help_text='Widgets + disposition + specs de données (opaque pour core).')
    partage = models.BooleanField(
        'Partagé', default=False,
        help_text='Visible par toute la société (sinon personnel).')

    class Meta:
        verbose_name = 'Dashboard'
        verbose_name_plural = 'Dashboards'
        ordering = ['titre', 'id']
        indexes = [
            models.Index(fields=['company', 'owner'],
                         name='core_dashboard_co_owner_idx'),
            models.Index(fields=['company', 'partage'],
                         name='core_dashboard_co_part_idx'),
        ]

    def __str__(self):
        return self.titre


# ---------------------------------------------------------------------------
# FG370 — Passerelle de paiement carte en ligne (CMI / Payzone).
#
# Modèle de FONDATION GÉNÉRIQUE : suit une transaction de paiement carte en
# ligne pour N'IMPORTE QUEL document métier facturable (Facture, échéance…)
# SANS importer l'app qui le produit (contrat import-linter
# ``core-foundation-is-a-base-layer``). La cible est désignée via
# ``contenttypes`` (content_type + object_id + GenericForeignKey) — fondation
# Django. Le rapprochement vers ``Paiement`` est laissé à l'app comptable, qui
# réagit à l'événement ``payment_captured`` du bus ``core.events`` — core ne
# crée jamais lui-même un ``Paiement`` métier.
#
# ⚠ AUTH : la capture réelle exige un compte marchand CMI/Payzone + une clé
# provisionnée par le fondateur (variable d'environnement via ``secret_ref`` de
# ``IntegrationConfig``). Sans elle, le connecteur reste en no-op propre.
# ---------------------------------------------------------------------------


class PaymentTransaction(TimestampedModel):
    """Transaction de paiement carte en ligne (FG370 — CMI / Payzone).

    GÉNÉRIQUE : cible via ``contenttypes`` (aucun import métier). ``provider``
    nomme le connecteur de paiement (``core.payment``) ; ``external_ref`` garde
    la référence du PSP ; ``statut`` suit le cycle de vie. Multi-tenant :
    ``company`` obligatoire, imposée côté serveur. Le rapprochement vers le
    ``Paiement`` comptable se fait via l'événement ``payment_captured`` du bus
    d'événements (``core.events``) — core ne touche aucun modèle métier.
    """

    STATUT_INITIE = 'initie'
    STATUT_EN_ATTENTE = 'en_attente'
    STATUT_PAYE = 'paye'
    STATUT_ECHEC = 'echec'
    STATUT_ANNULE = 'annule'
    STATUT_REMBOURSE = 'rembourse'
    STATUT_CHOICES = [
        (STATUT_INITIE, 'Initié'),
        (STATUT_EN_ATTENTE, 'En attente'),
        (STATUT_PAYE, 'Payé'),
        (STATUT_ECHEC, 'Échec'),
        (STATUT_ANNULE, 'Annulé'),
        (STATUT_REMBOURSE, 'Remboursé'),
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='payment_transactions', verbose_name='Société')

    # Cible générique — AUCUN import métier (contenttypes = fondation).
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True,
        related_name='+', verbose_name='Type de document')
    object_id = models.PositiveIntegerField(
        'Identifiant du document', null=True, blank=True)
    target = GenericForeignKey('content_type', 'object_id')

    provider = models.CharField(
        'Fournisseur', max_length=60, default='cmi',
        help_text='Code du connecteur de paiement (ex. « cmi », « payzone »).')
    montant = models.DecimalField(
        'Montant', max_digits=12, decimal_places=2)
    devise = models.CharField('Devise', max_length=3, default='MAD')
    statut = models.CharField(
        'Statut', max_length=16, choices=STATUT_CHOICES,
        default=STATUT_INITIE)

    external_ref = models.CharField(
        'Référence PSP', max_length=128, blank=True, default='',
        help_text='Identifiant retourné par le prestataire de paiement.')
    redirect_url = models.URLField(
        'URL de redirection', max_length=600, blank=True, default='',
        help_text='URL de la page de paiement hébergée du PSP.')
    payeur_email = models.EmailField('Email payeur', blank=True, default='')

    paye_le = models.DateTimeField('Payé le', null=True, blank=True)
    detail = models.JSONField('Détail', default=dict, blank=True)

    class Meta:
        verbose_name = 'Transaction de paiement'
        verbose_name_plural = 'Transactions de paiement'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='core_pay_co_statut_idx'),
            models.Index(fields=['provider', 'external_ref'],
                         name='core_pay_ext_idx'),
        ]

    def __str__(self):
        return (f'Paiement {self.provider} #{self.pk} '
                f'({self.get_statut_display()})')


# ---------------------------------------------------------------------------
# FG382 — BI embarqué : explorateur de données (query builder sans SQL).
#
# Modèle de FONDATION GÉNÉRIQUE : persiste une spec de requête ad-hoc
# (``dataset`` + ``spec`` JSON opaque : champs/filtres/agrégations) pour la
# rejouer. ``core`` ne sait RIEN des modèles interrogés — les datasets sont
# enregistrés par les apps métier (``core.data_explorer.register_dataset``) et
# core n'importe aucune app métier (contrat import-linter
# ``core-foundation-is-a-base-layer``).
# ---------------------------------------------------------------------------


class SavedQuery(TimestampedModel):
    """Requête d'analyse ad-hoc sauvegardée (FG382).

    GÉNÉRIQUE : ``dataset`` nomme un dataset enregistré ; ``spec`` est une spec
    JSON opaque (sélection/filtres/agrégations) interprétée par
    ``core.data_explorer.run_query``. Multi-tenant : ``company`` obligatoire,
    imposée côté serveur. ``owner`` (optionnel) + ``partage`` gèrent la
    visibilité personnelle/société, comme ``Dashboard``.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='saved_queries', verbose_name='Société')
    owner = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.CASCADE,
        null=True, blank=True, related_name='saved_queries',
        verbose_name='Propriétaire',
        help_text='Vide = requête de société (non personnelle).')

    titre = models.CharField('Titre', max_length=160)
    dataset = models.CharField(
        'Dataset', max_length=80,
        help_text='Nom du dataset enregistré (core.data_explorer).')
    spec = models.JSONField(
        'Spécification', default=dict, blank=True,
        help_text='Sélection/filtres/agrégations (opaque pour core).')
    partage = models.BooleanField(
        'Partagée', default=False,
        help_text='Visible par toute la société (sinon personnelle).')

    class Meta:
        verbose_name = 'Requête sauvegardée'
        verbose_name_plural = 'Requêtes sauvegardées'
        ordering = ['titre', 'id']
        indexes = [
            models.Index(fields=['company', 'owner'],
                         name='core_savedq_co_owner_idx'),
            models.Index(fields=['company', 'dataset'],
                         name='core_savedq_co_ds_idx'),
        ]

    def __str__(self):
        return self.titre
