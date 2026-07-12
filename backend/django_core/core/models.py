import secrets

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


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


# ---------------------------------------------------------------------------
# ARC1 — Socle multi-tenant : ``TenantModel`` (FK company + timestamps).
#
# Constat (audit noyau) : la paire « FK ``company`` posée à la main + horodatage
# ``created_at``/``updated_at`` » est réécrite dans des dizaines de fichiers
# alors qu'aucune classe abstraite ne la regroupait. ``TenantModel`` factorise
# EXACTEMENT ce socle :
#   * hérite de ``TimestampedModel`` (``created_at`` / ``updated_at``) ;
#   * ajoute une FK ``company`` vers ``authentication.Company`` (app de
#     FONDATION — ``core`` reste une couche de base, contrat import-linter
#     ``core-foundation-is-a-base-layer`` ; aucun import d'app métier).
#
# RÈGLE PLAYBOOK (à respecter pour tout NOUVEAU modèle) :
#   Tout NOUVEAU modèle métier multi-société hérite de ``core.models.TenantModel``
#   plutôt que de redéclarer à la main la FK ``company`` + les timestamps. Il
#   suffit alors de définir ses propres champs (et un ``related_name`` explicite
#   si l'accesseur inverse par défaut ne convient pas — voir ci-dessous).
#
# ACCESSEUR INVERSE (``related_name``) — NE JAMAIS renommer un accesseur existant.
#   Le ``related_name`` par défaut ``'%(app_label)s_%(class)s_set'`` garantit
#   que deux modèles concrets distincts n'entrent jamais en collision sur
#   ``company.<...>`` (chaque sous-classe reçoit un accesseur unique). Un modèle
#   CONVERTI depuis une FK ``company`` écrite à la main DOIT conserver son
#   ``related_name`` EXACT : pour cela il REDÉCLARE simplement le champ
#   ``company`` dans son propre corps (Django autorise une sous-classe concrète à
#   redéfinir un champ hérité d'une base abstraite) tout en gagnant les
#   timestamps de la base — jamais un renommage d'accesseur (qui casserait le
#   code appelant ``company.<ancien_related_name>``).
#
# Le garde-fou de complétude de la conversion de masse reste YDATA2 (nommé, non
# dupliqué ici) : ARC1 ne fait que poser la classe + convertir des pilotes dont
# la migration générée est vide/state-only.
# ---------------------------------------------------------------------------


class TenantModel(TimestampedModel):
    """Socle abstrait multi-tenant : FK ``company`` + horodatage (ARC1).

    Hériter de ce mixin donne, en une ligne, la paire multi-société standard :
      * ``company`` — FK obligatoire vers ``authentication.Company`` ;
      * ``created_at`` / ``updated_at`` — hérités de ``TimestampedModel``.

    GÉNÉRIQUE : ne référence AUCUNE app métier (seulement ``authentication``,
    une app de fondation) — ``core`` reste une couche de base.

    ``related_name`` par défaut ``'%(app_label)s_%(class)s_set'`` : chaque
    sous-classe concrète reçoit un accesseur inverse unique. Un modèle converti
    qui doit garder un ``related_name`` historique redéclare le champ ``company``
    dans son propre corps (voir la note PLAYBOOK ci-dessus) — jamais de
    renommage d'accesseur.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_set',
        verbose_name='Société',
    )

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# FG388 — Corbeille / restauration (soft-delete + undo), standard partagé.
#
# Fondation GÉNÉRIQUE : ``SoftDeleteModel`` est un mixin ABSTRAIT que n'importe
# quelle app métier peut faire hériter pour gagner un soft-delete uniforme
# (``is_deleted`` + ``deleted_at`` + ``deleted_by``) + un manager qui masque les
# supprimés par défaut. ``core`` reste fondation : ce mixin ne référence aucune
# app métier (le ``deleted_by`` pointe ``authentication.CustomUser``, une app de
# fondation). Le journal concret de corbeille/undo est ``DeletionRecord``
# (plus bas), keyé via ``contenttypes`` — toujours sans import métier.
#
# ── ARC15 — Inventaire d'adoption (recensement du 2026-07-10) ──────────────
# Adoption réelle du mixin ``SoftDeleteModel`` par les modèles métier :
#   NOMBRE DE MODÈLES QUI EN HÉRITENT : 0 (aucune app, sur les 35+ recensées).
# Les seules références dans le dépôt sont l'INFRASTRUCTURE, pas de l'adoption :
#   * ``core/models.py`` — définition du mixin + ``DeletionRecord`` (ce fichier) ;
#   * ``core/trash.py``  — service corbeille/undo qui consomme l'interface
#     DYNAMIQUEMENT (``obj.restore()`` / ``hasattr``), sans importer d'app ;
#   * ``core/tests/test_trash.py`` — teste la STRUCTURE du mixin lui-même ;
#   * un commentaire dans ``core/models.py`` (YOPSB3, ~l.1574) et la migration
#     ``core/migrations/0021_...`` qui notent EXPLICITEMENT un soft-delete
#     « léger » distinct (champ direct, PAS ce mixin).
# Le socle est donc construit + testé + prêt, mais VOLONTAIREMENT non encore
# adopté par le domaine.
#
# DÉCISION ARC15 : la vague d'adoption du soft-delete (YDATA17) s'implémente sur
# CE mixin ``core.SoftDeleteModel`` (ne JAMAIS en créer un nouveau). Les modèles
# pilotes d'adoption appartiennent à YDATA17, pas à ARC1/ARC15 : ici on se
# contente d'acter le socle + de recenser l'adoption (nulle à ce jour).
# ---------------------------------------------------------------------------


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet avec helpers de soft-delete (masque les supprimés par défaut)."""

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """Manager par défaut : ne renvoie QUE les enregistrements vivants.

    Le manager ``all_objects`` (déclaré sur le mixin) permet d'accéder aussi
    aux supprimés (corbeille). ``get_queryset`` filtre ``is_deleted=False``.
    """

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(
            is_deleted=False)


class SoftDeleteModel(models.Model):
    """Mixin abstrait de soft-delete réutilisable (FG388).

    Hériter de ce mixin donne :
      * ``is_deleted`` / ``deleted_at`` / ``deleted_by`` ;
      * ``objects`` — vivants uniquement (corbeille masquée) ;
      * ``all_objects`` — tout (pour la corbeille) ;
      * ``soft_delete(user=None)`` / ``restore()`` — bascule + journal undo.

    GÉNÉRIQUE : aucun import d'app métier. ``soft_delete`` écrit aussi un
    ``DeletionRecord`` (corbeille par société + fenêtre d'undo) via
    contenttypes.
    """

    is_deleted = models.BooleanField('Supprimé', default=False, db_index=True)
    deleted_at = models.DateTimeField('Supprimé le', null=True, blank=True)
    deleted_by = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Supprimé par')

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self, user=None, *, record=True):
        """Marque l'objet supprimé (sans le détruire) + journalise pour l'undo.

        ``record=True`` matérialise un ``DeletionRecord`` (corbeille/undo) si
        l'objet porte une ``company`` (multi-tenant). Idempotent.
        """
        if self.is_deleted:
            return self
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])
        company = getattr(self, 'company', None)
        if record and company is not None:
            DeletionRecord.objects.create(
                company=company,
                content_type=ContentType.objects.get_for_model(type(self)),
                object_id=self.pk,
                label=str(self)[:255],
                deleted_by=user,
            )
        return self

    def restore(self):
        """Restaure un objet soft-supprimé + ferme l'entrée de corbeille."""
        if not self.is_deleted:
            return self
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])
        ct = ContentType.objects.get_for_model(type(self))
        (DeletionRecord.objects
         .filter(content_type=ct, object_id=self.pk, restored_at__isnull=True)
         .update(restored_at=timezone.now()))
        return self


class DeletionRecord(TimestampedModel):
    """Entrée de corbeille / journal d'undo (FG388).

    GÉNÉRIQUE : pointe l'objet supprimé via ``contenttypes`` (aucun import
    métier). Une entrée par soft-delete, par société (multi-tenant). ``restore``
    sur l'objet d'origine ferme l'entrée (``restored_at``). La « fenêtre d'undo »
    globale est portée par ``DeletionRecord.objects.dans_fenetre(...)``
    (service ``core.trash``).
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='deletion_records', verbose_name='Société')

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+',
        verbose_name='Type de document')
    object_id = models.PositiveIntegerField('Identifiant du document')
    target = GenericForeignKey('content_type', 'object_id')

    label = models.CharField('Libellé', max_length=255, blank=True, default='')
    deleted_by = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Supprimé par')
    restored_at = models.DateTimeField('Restauré le', null=True, blank=True)

    class Meta:
        verbose_name = 'Entrée de corbeille'
        verbose_name_plural = 'Entrées de corbeille'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['company', 'restored_at'],
                         name='core_trash_co_restored_idx'),
            models.Index(fields=['content_type', 'object_id'],
                         name='core_trash_target_idx'),
        ]

    def __str__(self):
        return f'Corbeille #{self.pk} — {self.label}'


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

    # YHARD5 — gouvernance des secrets & suivi de rotation (additif). Aucune
    # valeur de secret n'est jamais stockée ici : seulement des métadonnées de
    # suivi (échéance, propriétaire) ; ``secret_ref`` reste la seule
    # indirection vers la valeur réelle.
    secret_last_rotated_at = models.DateTimeField(
        'Dernière rotation du secret', null=True, blank=True)
    rotation_period_days = models.PositiveIntegerField(
        'Période de rotation (jours)', null=True, blank=True,
        help_text='Échéance = dernière rotation + cette période. Vide = pas de suivi.')
    secret_owner = models.CharField(
        'Propriétaire du secret', max_length=120, blank=True, default='',
        help_text='Texte libre (personne/équipe responsable de la rotation).')

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
# QX37 (2026-07-10) — SUPPRIMÉ. Ce ``core.WebhookSubscription`` /
# ``core.webhooks.dispatch_event`` était un DOUBLON MORT de la couche webhook
# vivante ``apps.publicapi`` (``publicapi.Webhook`` + ``publicapi.delivery``) :
# aucun câblage ne le déclenchait, ses abonnements ne partaient jamais. On garde
# UNE seule surface d'abonnement (publicapi). Le modèle est retiré par la
# migration ``0027`` (destructive mais réversible). Voir PLAN2 QX37.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# FG383 — Extraits planifiés vers entrepôt / SFTP / S3.
#
# Modèle de FONDATION GÉNÉRIQUE : planifie un extrait de données (dataset FG382
# + spec opaque) au format CSV/parquet vers une destination externe (SFTP/S3).
# ``core`` ne sait RIEN des modèles extraits (datasets enregistrés par les apps
# métier) ni de l'infra de destination (connecteur enregistré) — aucun import
# d'app métier (contrat import-linter ``core-foundation-is-a-base-layer``).
# ---------------------------------------------------------------------------


class ScheduledExport(TimestampedModel):
    """Extrait de données planifié vers une destination externe (FG383).

    GÉNÉRIQUE : ``dataset`` + ``spec`` désignent les données (explorateur FG382) ;
    ``format`` = CSV/parquet ; ``destination`` = connecteur enregistré (SFTP/S3).
    ``cron`` porte la planification (interprétée par l'infra Celery Beat, hors
    core). Multi-tenant : ``company`` obligatoire, imposée côté serveur.

    ⚠ AUTH : la livraison réelle exige des credentials provisionnés par le
    fondateur ; sans eux le runner reste en no-op (``dernier_statut`` =
    « non_configure »).
    """

    FORMAT_CSV = 'csv'
    FORMAT_PARQUET = 'parquet'
    FORMAT_CHOICES = [
        (FORMAT_CSV, 'CSV'),
        (FORMAT_PARQUET, 'Parquet'),
    ]

    DEST_SFTP = 'sftp'
    DEST_S3 = 's3'
    DEST_CHOICES = [
        (DEST_SFTP, 'SFTP'),
        (DEST_S3, 'Bucket S3'),
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='scheduled_exports', verbose_name='Société')

    titre = models.CharField('Titre', max_length=160)
    dataset = models.CharField(
        'Dataset', max_length=80,
        help_text='Nom du dataset enregistré (core.data_explorer).')
    spec = models.JSONField(
        'Spécification', default=dict, blank=True,
        help_text='Sélection/filtres (opaque pour core).')
    format = models.CharField(
        'Format', max_length=10, choices=FORMAT_CHOICES, default=FORMAT_CSV)
    destination = models.CharField(
        'Destination', max_length=20, choices=DEST_CHOICES, default=DEST_SFTP)
    cron = models.CharField(
        'Planification (cron)', max_length=120, blank=True, default='',
        help_text='Expression cron interprétée par Celery Beat (hors core).')
    actif = models.BooleanField('Actif', default=True)

    derniere_execution_le = models.DateTimeField(
        'Dernière exécution', null=True, blank=True)
    dernier_statut = models.CharField(
        'Dernier statut', max_length=20, blank=True, default='')
    dernier_detail = models.JSONField('Dernier détail', default=dict, blank=True)

    class Meta:
        verbose_name = 'Extrait planifié'
        verbose_name_plural = 'Extraits planifiés'
        ordering = ['titre', 'id']
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='core_schedexp_co_actif_idx'),
        ]

    def __str__(self):
        return f'{self.titre} → {self.destination}'


# ---------------------------------------------------------------------------
# FG391 — Flags de fonctionnalités / modules par tenant (société).
#
# Modèle de FONDATION GÉNÉRIQUE : active/désactive un module par société.
# ``module`` est une CLÉ LIBRE (chaîne, ex. « sav », « flotte ») — ``core`` ne
# connaît AUCUN module métier (contrat import-linter
# ``core-foundation-is-a-base-layer``). L'absence de ligne = comportement par
# défaut (activé) ; une ligne ``actif=False`` désactive le module pour la
# société. Le service ``core.feature_flags.module_actif`` lit cette table.
# ---------------------------------------------------------------------------


class ModuleToggle(TimestampedModel):
    """Activation/désactivation d'un module par société (FG391).

    GÉNÉRIQUE : ``module`` est une clé libre (aucun import métier). Unique par
    ``(company, module)``. ``actif`` porte l'état ; ``raison`` documente une
    coupure éventuelle. Multi-tenant : ``company`` obligatoire, imposée côté
    serveur.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='module_toggles', verbose_name='Société')

    module = models.CharField(
        'Module', max_length=60,
        help_text='Clé du module, ex. « sav », « flotte » (libre).')
    actif = models.BooleanField('Actif', default=True)
    raison = models.CharField(
        'Raison', max_length=255, blank=True, default='',
        help_text='Note optionnelle (ex. « hors offre », « en pilote »).')

    class Meta:
        verbose_name = 'Activation de module'
        verbose_name_plural = 'Activations de modules'
        ordering = ['module', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'module'],
                name='core_moduletoggle_co_mod'),
        ]
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='core_modtog_co_actif_idx'),
        ]

    def __str__(self):
        etat = 'activé' if self.actif else 'désactivé'
        return f'{self.module} ({etat}) — société {self.company_id}'


# ---------------------------------------------------------------------------
# FG392 — Thème white-label par tenant (société).
#
# Modèle de FONDATION GÉNÉRIQUE : porte le branding par société (logo,
# couleurs, domaine personnalisé) appliqué à la SPA et aux PDF, AU-DELÀ des
# bases ``CompanyProfile`` (app parametres — JAMAIS importée ici : ``core`` reste
# fondation, contrat import-linter ``core-foundation-is-a-base-layer``). Une
# seule ligne par société (OneToOne).
# ---------------------------------------------------------------------------


class TenantTheme(TimestampedModel):
    """Thème white-label d'une société (FG392).

    GÉNÉRIQUE : aucun import métier. Logo (chemin/URL de stockage), couleurs
    primaires/secondaires (hex), domaine personnalisé, et un blob ``extra`` JSON
    pour des jetons de thème additionnels (police, rayon…). Multi-tenant :
    ``company`` obligatoire, OneToOne, imposée côté serveur.
    """

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='tenant_theme', verbose_name='Société')

    logo_url = models.CharField(
        'Logo (URL/chemin)', max_length=500, blank=True, default='',
        help_text='URL ou chemin de stockage du logo white-label.')
    couleur_primaire = models.CharField(
        'Couleur primaire', max_length=9, blank=True, default='',
        help_text='Code couleur hex (ex. « #1a3b8c »).')
    couleur_secondaire = models.CharField(
        'Couleur secondaire', max_length=9, blank=True, default='')
    domaine = models.CharField(
        'Domaine personnalisé', max_length=255, blank=True, default='',
        help_text='Domaine white-label (ex. « erp.client.ma »).')
    nom_affichage = models.CharField(
        'Nom affiché', max_length=160, blank=True, default='',
        help_text='Nom de marque affiché (sinon la raison sociale).')
    extra = models.JSONField(
        'Jetons additionnels', default=dict, blank=True,
        help_text='Jetons de thème additionnels (opaque pour core).')

    class Meta:
        verbose_name = 'Thème white-label'
        verbose_name_plural = 'Thèmes white-label'
        ordering = ['id']

    def __str__(self):
        return f'Thème société {self.company_id}'


# ---------------------------------------------------------------------------
# FG393 — Éditeur de modèles imprimables / brandés (PDF / email / WhatsApp).
#
# Modèle de FONDATION GÉNÉRIQUE : persiste des modèles brandés éditables
# (PDF/email/WhatsApp) avec des placeholders ``{{ variable }}`` rendus par un
# moteur SÛR (``core.templating`` — substitution littérale, pas d'exécution de
# code). ``core`` ne connaît AUCUN modèle métier (contrat import-linter
# ``core-foundation-is-a-base-layer``) : les variables sont fournies par
# l'appelant au moment du rendu. Nommé ``BrandedTemplate`` (et non
# ``MessageTemplate``) pour ne PAS entrer en collision avec le
# ``parametres.MessageTemplate`` WhatsApp existant (FR/Darija) — les deux
# coexistent : celui-ci généralise l'éditeur multi-canal.
# ---------------------------------------------------------------------------


class BrandedTemplate(TimestampedModel):
    """Modèle brandé éditable par société (FG393).

    GÉNÉRIQUE : ``kind`` = pdf/email/whatsapp ; ``code`` identifie l'usage (ex.
    « relance_devis ») ; ``sujet`` + ``corps`` portent le texte avec des
    placeholders ``{{ variable }}``. Multi-tenant : ``company`` obligatoire,
    imposée côté serveur. Unique par ``(company, kind, code)``.
    """

    KIND_PDF = 'pdf'
    KIND_EMAIL = 'email'
    KIND_WHATSAPP = 'whatsapp'
    KIND_CHOICES = [
        (KIND_PDF, 'PDF'),
        (KIND_EMAIL, 'Email'),
        (KIND_WHATSAPP, 'WhatsApp'),
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='branded_templates', verbose_name='Société')

    kind = models.CharField('Type', max_length=12, choices=KIND_CHOICES)
    code = models.CharField(
        'Code', max_length=80,
        help_text="Identifiant d'usage, ex. « relance_devis » (libre).")
    nom = models.CharField('Nom', max_length=160)
    sujet = models.CharField(
        'Sujet', max_length=255, blank=True, default='',
        help_text='Objet (email) ou titre — supporte les placeholders.')
    corps = models.TextField(
        'Corps', blank=True, default='',
        help_text='Texte avec placeholders ``{{ variable }}``.')
    actif = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Modèle brandé'
        verbose_name_plural = 'Modèles brandés'
        ordering = ['kind', 'code', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'kind', 'code'],
                name='core_brandtpl_co_kind_code'),
        ]
        indexes = [
            models.Index(fields=['company', 'kind', 'actif'],
                         name='core_brandtpl_co_kind_idx'),
        ]

    def __str__(self):
        return f'{self.kind}:{self.code} — {self.nom}'


# ---------------------------------------------------------------------------
# FG394 — Consentement & DSR (loi 09-08 / CNDP).
#
# Modèles de FONDATION GÉNÉRIQUES : registre de consentement + demandes de
# personnes concernées (accès / effacement). La personne concernée est désignée
# par un IDENTIFIANT générique (email ou téléphone) — ``core`` ne référence
# AUCUN modèle métier (contrat import-linter
# ``core-foundation-is-a-base-layer``). L'export/effacement réel des données
# métier est délégué à des « fournisseurs DSR » que les apps enregistrent
# (``core.dsr.register_dsr_provider``) — core orchestre sans rien importer.
# ---------------------------------------------------------------------------


class ConsentRecord(TimestampedModel):
    """Entrée du registre de consentement (FG394, loi 09-08 / CNDP).

    GÉNÉRIQUE : ``subject_identifier`` = email ou téléphone de la personne
    concernée (aucun import métier). ``purpose`` = finalité (ex. « marketing »,
    « whatsapp »). ``granted`` porte l'état ; ``source`` documente l'origine du
    consentement. Multi-tenant : ``company`` obligatoire, imposée côté serveur.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='consent_records', verbose_name='Société')

    subject_identifier = models.CharField(
        'Identifiant de la personne', max_length=255,
        help_text='Email ou téléphone de la personne concernée.')
    purpose = models.CharField(
        'Finalité', max_length=80,
        help_text='Finalité du traitement, ex. « marketing », « whatsapp ».')
    granted = models.BooleanField('Consentement donné', default=True)
    source = models.CharField(
        'Source', max_length=120, blank=True, default='',
        help_text='Origine du consentement (ex. « formulaire site », « devis »).')
    occurred_at = models.DateTimeField(
        'Horodatage', null=True, blank=True,
        help_text='Date/heure du consentement (sur le consent_timestamp '
                  'existant côté métier).')
    # ── XMKT4 — version du texte + preuve de double opt-in (loi 09-08/CNDP) ──
    version_texte = models.CharField(
        'Version du texte de consentement', max_length=40, blank=True,
        default='', help_text='Version du texte présenté à la personne '
                              '(ex. « v1-2026-07 »).')
    ip_confirmation = models.GenericIPAddressField(
        'IP de confirmation', null=True, blank=True,
        help_text='IP du clic de confirmation (double opt-in), preuve '
                  'loi 09-08.')

    class Meta:
        verbose_name = 'Consentement'
        verbose_name_plural = 'Registre de consentement'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['company', 'subject_identifier'],
                         name='core_consent_co_subj_idx'),
            models.Index(fields=['company', 'purpose', 'granted'],
                         name='core_consent_co_purp_idx'),
        ]

    def __str__(self):
        etat = 'accordé' if self.granted else 'retiré'
        return f'{self.subject_identifier} — {self.purpose} ({etat})'


class DataSubjectRequest(TimestampedModel):
    """Demande de personne concernée — accès ou effacement (FG394).

    GÉNÉRIQUE : ``subject_identifier`` désigne la personne (email/téléphone).
    ``kind`` = accès (export) ou effacement. ``statut`` suit le cycle de vie ;
    ``resultat`` porte le payload d'export (accès) ou le compte-rendu
    d'effacement. Multi-tenant : ``company`` obligatoire, imposée côté serveur.
    L'exécution réelle passe par les fournisseurs DSR enregistrés (``core.dsr``).
    """

    KIND_ACCESS = 'acces'
    KIND_ERASURE = 'effacement'
    # XPLT23 — rectification (loi 09-08) : workflow manuel de correction des
    # données d'une personne concernée (champs demandés + trace de traitement).
    KIND_RECTIFICATION = 'rectification'
    KIND_CHOICES = [
        (KIND_ACCESS, "Accès (export)"),
        (KIND_ERASURE, 'Effacement'),
        (KIND_RECTIFICATION, 'Rectification'),
    ]

    STATUT_RECUE = 'recue'
    STATUT_TRAITEE = 'traitee'
    STATUT_REFUSEE = 'refusee'
    STATUT_CHOICES = [
        (STATUT_RECUE, 'Reçue'),
        (STATUT_TRAITEE, 'Traitée'),
        (STATUT_REFUSEE, 'Refusée'),
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='dsr_requests', verbose_name='Société')

    subject_identifier = models.CharField(
        'Identifiant de la personne', max_length=255,
        help_text='Email ou téléphone de la personne concernée.')
    kind = models.CharField('Type', max_length=20, choices=KIND_CHOICES)
    statut = models.CharField(
        'Statut', max_length=12, choices=STATUT_CHOICES, default=STATUT_RECUE)
    resultat = models.JSONField(
        'Résultat', default=dict, blank=True,
        help_text="Payload d'export (accès) ou compte-rendu d'effacement.")
    traitee_le = models.DateTimeField('Traitée le', null=True, blank=True)

    class Meta:
        verbose_name = 'Demande de personne concernée'
        verbose_name_plural = 'Demandes de personnes concernées'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='core_dsr_co_statut_idx'),
            models.Index(fields=['company', 'subject_identifier'],
                         name='core_dsr_co_subj_idx'),
        ]

    def __str__(self):
        return f'DSR {self.kind} — {self.subject_identifier} ({self.statut})'


class RegistreTraitement(TimestampedModel):
    """XPLT23 — registre des traitements CNDP (loi 09-08).

    GÉNÉRIQUE (couche fondation, aucun import métier) : une ligne = une
    déclaration de traitement de données personnelles auprès de la CNDP.
    Multi-tenant : ``company`` obligatoire, imposée côté serveur. Pré-remplie
    par une commande seed idempotente des traitements types du produit.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='registres_traitement', verbose_name='Société')

    # Clé stable (seed idempotent) — ex. « leads_clients », « rh_paie ».
    code = models.CharField(
        'Code', max_length=80,
        help_text='Clé stable du traitement (seed idempotent).')
    finalite = models.CharField(
        'Finalité', max_length=255,
        help_text='Finalité du traitement (ex. « gestion des prospects »).')
    base_legale = models.CharField(
        'Base légale', max_length=255, blank=True, default='',
        help_text='Consentement, contrat, obligation légale, intérêt légitime…')
    categories_donnees = models.TextField(
        'Catégories de données', blank=True, default='',
        help_text='Identité, contact, données de facturation, données RH…')
    categories_personnes = models.TextField(
        'Catégories de personnes', blank=True, default='',
        help_text='Prospects, clients, salariés, candidats…')
    destinataires = models.TextField(
        'Destinataires', blank=True, default='',
        help_text='Services internes et sous-traitants destinataires.')
    duree_conservation = models.CharField(
        'Durée de conservation', max_length=255, blank=True, default='',
        help_text='Durée légale/contractuelle de conservation.')
    numero_recepisse = models.CharField(
        'N° de récépissé CNDP', max_length=120, blank=True, default='')
    date_recepisse = models.DateField(
        'Date de récépissé CNDP', null=True, blank=True)
    actif = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Traitement CNDP'
        verbose_name_plural = 'Registre des traitements (CNDP)'
        ordering = ['code', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='core_registretraitement_co_code'),
        ]

    def __str__(self):
        return f'{self.code} — {self.finalite} (société {self.company_id})'


# ---------------------------------------------------------------------------
# FG395 — Sauvegarde / restauration en libre-service (par société).
#
# Modèle de FONDATION GÉNÉRIQUE : trace une opération de sauvegarde (export) ou
# de restauration (restore) d'un bundle de données société, à la demande ou
# planifiée. ``core`` ne connaît AUCUN modèle métier (contrat import-linter
# ``core-foundation-is-a-base-layer``) : les apps métier fournissent leurs
# datasets via le registre ``core.data_explorer`` ; ce modèle ne porte que les
# MÉTADONNÉES de l'opération (jamais le contenu métier). Le runner réel
# (``core.backup``) matérialise/restaure le bundle ; sans destination
# configurée il reste en no-op propre.
# ---------------------------------------------------------------------------


class BackupRun(TimestampedModel):
    """Opération de sauvegarde/restauration d'une société (FG395).

    GÉNÉRIQUE : ``kind`` = export (sauvegarde) ou restore (restauration) ;
    ``mode`` = manuel ou planifié ; ``statut`` suit le cycle de vie. ``cron``
    porte une planification éventuelle (interprétée par Celery Beat, hors core).
    ``manifest`` résume le bundle (datasets + comptes de lignes) sans contenu
    métier. Multi-tenant : ``company`` obligatoire, imposée côté serveur.
    """

    KIND_EXPORT = 'export'
    KIND_RESTORE = 'restore'
    # YOPSB1/2 — dump Postgres réel (pg_dump vers MinIO) et drill de
    # restauration (pg_restore vers une base JETABLE). Système-wide : PAS de
    # société unique concernée (toute l'instance), d'où ``company`` nullable
    # ci-dessous réservé à CES deux kinds.
    KIND_DB_DUMP = 'db_dump'
    KIND_RESTORE_DRILL = 'restore_drill'
    KIND_CHOICES = [
        (KIND_EXPORT, 'Sauvegarde'),
        (KIND_RESTORE, 'Restauration'),
        (KIND_DB_DUMP, 'Dump base (pg_dump)'),
        (KIND_RESTORE_DRILL, 'Drill de restauration'),
    ]

    MODE_MANUEL = 'manuel'
    MODE_PLANIFIE = 'planifie'
    MODE_CHOICES = [
        (MODE_MANUEL, 'À la demande'),
        (MODE_PLANIFIE, 'Planifié'),
    ]

    STATUT_EN_ATTENTE = 'en_attente'
    STATUT_EN_COURS = 'en_cours'
    STATUT_TERMINE = 'termine'
    STATUT_ECHEC = 'echec'
    STATUT_NON_CONFIGURE = 'non_configure'
    STATUT_CHOICES = [
        (STATUT_EN_ATTENTE, 'En attente'),
        (STATUT_EN_COURS, 'En cours'),
        (STATUT_TERMINE, 'Terminé'),
        (STATUT_ECHEC, 'Échec'),
        (STATUT_NON_CONFIGURE, 'Non configuré'),
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='backup_runs', verbose_name='Société',
        null=True, blank=True,
        help_text="Nulle UNIQUEMENT pour les kinds système "
                  "db_dump/restore_drill (toute l'instance, pas une société).")

    kind = models.CharField(
        'Type', max_length=14, choices=KIND_CHOICES, default=KIND_EXPORT)
    mode = models.CharField(
        'Déclenchement', max_length=10, choices=MODE_CHOICES,
        default=MODE_MANUEL)
    statut = models.CharField(
        'Statut', max_length=14, choices=STATUT_CHOICES,
        default=STATUT_EN_ATTENTE)

    datasets = models.JSONField(
        'Datasets', default=list, blank=True,
        help_text='Liste des datasets inclus (noms du registre data_explorer). '
                  'Vide = tous les datasets de la société.')
    cron = models.CharField(
        'Planification (cron)', max_length=120, blank=True, default='',
        help_text='Expression cron interprétée par Celery Beat (hors core).')
    artifact_ref = models.CharField(
        "Référence de l'artefact", max_length=500, blank=True, default='',
        help_text='Chemin/URL de stockage du bundle (jamais le contenu).')
    object_key = models.CharField(
        'Clé objet MinIO', max_length=500, blank=True, default='',
        help_text='YOPSB1 — clé de l\'objet .dump dans le bucket erp-backups.')
    bytes_taille = models.BigIntegerField(
        'Taille (octets)', null=True, blank=True,
        help_text='YOPSB1 — taille du dump pg_dump produit.')
    manifest = models.JSONField(
        'Manifeste', default=dict, blank=True,
        help_text='Résumé du bundle (datasets + comptes), sans contenu métier.')

    declenche_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Déclenché par')
    termine_le = models.DateTimeField('Terminé le', null=True, blank=True)
    detail = models.JSONField(
        'Détail', default=dict, blank=True,
        help_text="Compte-rendu d'exécution (erreurs, durées).")

    # YOPSB3 — soft-delete LÉGER (champ direct, PAS SoftDeleteModel : le
    # manager par défaut de BackupRun reste inchangé pour ne pas affecter les
    # querysets existants). La purge GFS marque ``purge_is_deleted`` avant de
    # retirer l'objet MinIO ; les runs purgés restent visibles pour l'audit
    # via ``all_objects``-style filtre explicite si besoin.
    purge_is_deleted = models.BooleanField(
        'Purgé (rétention GFS)', default=False,
        help_text='YOPSB3 — vrai une fois retiré par la purge GFS (soft-delete).')
    purge_deleted_at = models.DateTimeField(
        'Purgé le', null=True, blank=True)

    class Meta:
        verbose_name = 'Sauvegarde/restauration'
        verbose_name_plural = 'Sauvegardes/restaurations'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['company', 'kind', 'statut'],
                         name='core_backup_co_kind_st_idx'),
        ]

    def __str__(self):
        return f'{self.get_kind_display()} société {self.company_id} ' \
               f'({self.statut})'


# ---------------------------------------------------------------------------
# FG398 — Plans de tarif API & analytics d'usage (par clé d'API).
#
# Modèles de FONDATION GÉNÉRIQUES : un plan de quota par société et un journal
# d'usage agrégé par clé d'API. La clé d'API vit dans l'app SATELLITE
# ``publicapi`` — ``core`` ne l'IMPORTE JAMAIS (contrat import-linter
# ``core-foundation-is-a-base-layer``) : le lien est une string-FK
# ``'publicapi.ApiKey'`` (référence paresseuse, aucun import de module). ``core``
# fournit le quota et le compteur ; ``publicapi`` les consomme via
# ``core.api_usage`` (sélecteur/enregistreur), pas l'inverse.
# ---------------------------------------------------------------------------


class ApiUsagePlan(TimestampedModel):
    """Plan de tarif/quota API d'une société (FG398).

    GÉNÉRIQUE : porte des limites de débit (par minute) et de volume (par jour/
    mois) appliquées aux clés d'API de la société. Multi-tenant : ``company``
    obligatoire (OneToOne), imposée côté serveur. ``code`` nomme le palier
    (libre, ex. « gratuit », « pro »).
    """

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='api_usage_plan', verbose_name='Société')

    code = models.CharField(
        'Palier', max_length=40, blank=True, default='gratuit',
        help_text='Nom du palier (libre, ex. « gratuit », « pro »).')
    quota_par_minute = models.PositiveIntegerField(
        'Quota / minute', default=60,
        help_text='Requêtes max par minute et par clé (0 = illimité).')
    quota_par_jour = models.PositiveIntegerField(
        'Quota / jour', default=10000,
        help_text='Requêtes max par jour et par société (0 = illimité).')
    quota_par_mois = models.PositiveIntegerField(
        'Quota / mois', default=300000,
        help_text='Requêtes max par mois et par société (0 = illimité).')
    actif = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = "Plan d'usage API"
        verbose_name_plural = "Plans d'usage API"
        ordering = ['id']

    def __str__(self):
        return f'Plan API « {self.code} » — société {self.company_id}'


class ApiUsageRecord(TimestampedModel):
    """Compteur d'usage API agrégé par clé et par jour (FG398).

    GÉNÉRIQUE : une ligne par ``(api_key, jour)`` agrège le nombre de requêtes
    et d'erreurs. La clé est désignée par string-FK ``'publicapi.ApiKey'``
    (aucun import). Multi-tenant : ``company`` obligatoire, imposée côté serveur
    par l'enregistreur (``core.api_usage``).
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='api_usage_records', verbose_name='Société')
    api_key = models.ForeignKey(
        'publicapi.ApiKey', on_delete=models.CASCADE,
        related_name='usage_records', verbose_name='Clé API')

    jour = models.DateField('Jour', help_text="Jour d'agrégation (UTC).")
    nb_requetes = models.PositiveIntegerField('Requêtes', default=0)
    nb_erreurs = models.PositiveIntegerField('Erreurs', default=0)

    class Meta:
        verbose_name = 'Usage API'
        verbose_name_plural = 'Usages API'
        ordering = ['-jour', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['api_key', 'jour'],
                name='core_apiusage_key_jour'),
        ]
        indexes = [
            models.Index(fields=['company', 'jour'],
                         name='core_apiusage_co_jour_idx'),
        ]

    def __str__(self):
        return f'Usage clé {self.api_key_id} le {self.jour} ' \
               f'({self.nb_requetes} req.)'


# ---------------------------------------------------------------------------
# FG399 — Journal des nouveautés in-app (changelog) + suivi de lecture.
#
# Modèles de FONDATION GÉNÉRIQUES : un fil de notes de version (changelog)
# GLOBAL au produit (pas de portée société — c'est l'éditeur du produit qui
# publie) et un suivi de lecture PAR UTILISATEUR (multi-tenant via l'utilisateur
# qui porte sa société). ``core`` ne connaît AUCUN modèle métier (contrat
# import-linter ``core-foundation-is-a-base-layer``).
# ---------------------------------------------------------------------------


class ChangelogEntry(TimestampedModel):
    """Note de version publiée dans le journal des nouveautés (FG399).

    GLOBALE au produit (aucune portée société) : c'est l'éditeur qui publie. Le
    suivi de lecture est porté par ``ChangelogRead`` (par utilisateur).
    ``categorie`` classe la note (nouveauté/amélioration/correctif).
    """

    CAT_NOUVEAUTE = 'nouveaute'
    CAT_AMELIORATION = 'amelioration'
    CAT_CORRECTIF = 'correctif'
    CAT_CHOICES = [
        (CAT_NOUVEAUTE, 'Nouveauté'),
        (CAT_AMELIORATION, 'Amélioration'),
        (CAT_CORRECTIF, 'Correctif'),
    ]

    titre = models.CharField('Titre', max_length=200)
    corps = models.TextField('Contenu', blank=True, default='')
    version = models.CharField(
        'Version', max_length=40, blank=True, default='',
        help_text='Étiquette de version, ex. « 2026.06 ».')
    categorie = models.CharField(
        'Catégorie', max_length=14, choices=CAT_CHOICES,
        default=CAT_NOUVEAUTE)
    publie = models.BooleanField(
        'Publié', default=False,
        help_text="Une note non publiée n'apparaît pas dans le fil.")
    publie_le = models.DateTimeField('Publié le', null=True, blank=True)

    class Meta:
        verbose_name = 'Note de version'
        verbose_name_plural = 'Notes de version'
        ordering = ['-publie_le', '-id']
        indexes = [
            models.Index(fields=['publie', 'publie_le'],
                         name='core_changelog_pub_idx'),
        ]

    def __str__(self):
        return f'{self.titre} ({self.version or "—"})'


class ChangelogRead(TimestampedModel):
    """Accusé de lecture d'une note de version par un utilisateur (FG399).

    Une ligne par ``(user, entry)``. Permet d'afficher un badge « nouveautés non
    lues » par utilisateur. ``user`` porte implicitement sa société.
    """

    user = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.CASCADE,
        related_name='changelog_reads', verbose_name='Utilisateur')
    entry = models.ForeignKey(
        ChangelogEntry, on_delete=models.CASCADE,
        related_name='reads', verbose_name='Note de version')

    class Meta:
        verbose_name = 'Lecture de note de version'
        verbose_name_plural = 'Lectures de notes de version'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'entry'],
                name='core_changelogread_user_entry'),
        ]

    def __str__(self):
        return f'Note {self.entry_id} lue par utilisateur {self.user_id}'


# ---------------------------------------------------------------------------
# XPLT10 — Partage de dashboard : lien public tokenisé + partage interne fin.
#
# ``Dashboard.partage`` (FG381) reste un booléen société-entière INCHANGÉ.
# ``PartageDashboard`` ajoute un lien PUBLIC tokenisé (calqué sur
# ``ged.PartageGed`` / ``ventes.ShareLink`` — même schéma de sécurité : le
# jeton est l'UNIQUE clé, jamais de confiance dans une identité venue de la
# requête). ``DashboardPartageInterne`` ajoute un partage interne à des
# utilisateurs/rôles CHOISIS (lecture/édition), plus fin que le booléen.
# ---------------------------------------------------------------------------

def _default_dashboard_partage_token():
    """Jeton de partage dashboard — même générateur que ``ged.PartageGed``
    (``secrets.token_urlsafe(32)``, cryptographiquement fort)."""
    return secrets.token_urlsafe(32)


class PartageDashboard(TimestampedModel):
    """XPLT10 — Lien public tokenisé LECTURE SEULE vers un ``Dashboard``.

    Ne sert JAMAIS de listes nominatives ni de ``prix_achat``/marges internes
    — uniquement les AGRÉGATS déjà rendus par le dashboard (le layout est déjà
    un JSON de widgets agrégés, cf. ``Dashboard.layout``). Révocation
    immédiate via ``actif=False`` (kill-switch) ; ``expires_at`` optionnel.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='dashboard_partages', verbose_name='Société')
    dashboard = models.ForeignKey(
        Dashboard, on_delete=models.CASCADE, related_name='partages_publics',
        verbose_name='Dashboard')
    token = models.CharField(
        max_length=64, unique=True, default=_default_dashboard_partage_token,
        editable=False)
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name='expire le')
    actif = models.BooleanField(default=True, verbose_name='actif')
    created_by = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='dashboard_partages_crees')

    class Meta:
        verbose_name = 'Partage public de dashboard'
        verbose_name_plural = 'Partages publics de dashboard'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'dashboard'],
                         name='core_dashpartage_co_dash_idx'),
        ]

    def __str__(self):
        return f'Partage {self.token[:8]}… → dashboard {self.dashboard_id}'

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_accessible(self):
        """True si le lien est actuellement servable publiquement."""
        return self.actif and not self.is_expired


class DashboardPartageInterne(TimestampedModel):
    """XPLT10 — Partage interne FIN d'un dashboard à des utilisateurs/rôles
    CHOISIS, avec un niveau lecture vs édition.

    Plus fin que ``Dashboard.partage`` (booléen société-entière, INCHANGÉ) :
    un dashboard personnel (``owner`` non nul, ``partage=False``) peut quand
    même être partagé à des tiers précis via cette table, sans devenir visible
    à toute la société."""

    class Niveau(models.TextChoices):
        LECTURE = 'lecture', 'Lecture'
        EDITION = 'edition', 'Édition'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='dashboard_partages_internes', verbose_name='Société')
    dashboard = models.ForeignKey(
        Dashboard, on_delete=models.CASCADE,
        related_name='partages_internes', verbose_name='Dashboard')
    utilisateur = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.CASCADE,
        null=True, blank=True, related_name='dashboard_partages_recus')
    # Rôle legacy (texte libre aligné sur CustomUser.role_legacy) — SANS FK,
    # pour rester cohérent avec le reste du partage par rôle dans le repo.
    role = models.CharField(max_length=20, blank=True, default='')
    niveau = models.CharField(
        max_length=10, choices=Niveau.choices, default=Niveau.LECTURE)

    class Meta:
        verbose_name = 'Partage interne de dashboard'
        verbose_name_plural = 'Partages internes de dashboard'
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['dashboard', 'utilisateur'],
                condition=models.Q(utilisateur__isnull=False),
                name='core_dashpartage_interne_dash_user_uniq'),
            models.UniqueConstraint(
                fields=['dashboard', 'role'],
                condition=~models.Q(role=''),
                name='core_dashpartage_interne_dash_role_uniq'),
        ]

    def __str__(self):
        cible = self.utilisateur_id or self.role or '—'
        return f'Dashboard {self.dashboard_id} → {cible} ({self.niveau})'


# ---------------------------------------------------------------------------
# YOPSB10 — Registre de rétention partagé + sweep beat unifié.
#
# ``RetentionRun`` journalise CHAQUE exécution d'une politique de rétention
# enregistrée (``core.retention.register_retention_policy``). Une politique
# balaie généralement TOUTES les sociétés (elle scope elle-même en interne),
# d'où ``company`` NULLABLE (balayage système, transverse) — comme
# ``BackupRun.company`` pour ses kinds système (YOPSB1/2). ``core`` reste
# fondation : aucune app domaine n'est importée ici, ``policy_name`` est un
# simple identifiant texte (pas de FK vers une politique métier).
# ---------------------------------------------------------------------------


class RetentionRun(TimestampedModel):
    """Journal d'exécution d'une politique de rétention (YOPSB10)."""

    STATUT_OK = 'ok'
    STATUT_ECHEC = 'echec'
    STATUT_CHOICES = [
        (STATUT_OK, 'OK'),
        (STATUT_ECHEC, 'Échec'),
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='retention_runs', verbose_name='Société',
        null=True, blank=True,
        help_text='Nulle pour un balayage système transverse à toutes les '
                  'sociétés (la politique scope elle-même en interne).')

    policy_name = models.CharField(
        'Politique', max_length=100,
        help_text="Nom enregistré via register_retention_policy (pas de FK "
                  "— core ne connaît aucune app domaine).")
    dry_run = models.BooleanField(
        'Dry-run', default=True,
        help_text='Vrai si la politique a tourné en mode simulation '
                  '(RETENTION_AUTO_APPLY inactif).')
    count = models.IntegerField(
        'Compte', default=0,
        help_text="Nombre d'éléments supprimés/anonymisés (0 en dry-run si "
                  "la politique ne fait que compter).")
    statut = models.CharField(
        'Statut', max_length=10, choices=STATUT_CHOICES, default=STATUT_OK)
    erreur = models.TextField('Erreur', blank=True, default='')
    executed_at = models.DateTimeField('Exécuté le', default=timezone.now)

    class Meta:
        verbose_name = 'Exécution de rétention'
        verbose_name_plural = 'Exécutions de rétention'
        ordering = ['-executed_at', '-id']
        indexes = [
            models.Index(fields=['policy_name', '-executed_at'],
                         name='core_retentionrun_policy_idx'),
        ]

    def __str__(self):
        return f'{self.policy_name} ({self.statut}, {self.count})'


# ---------------------------------------------------------------------------
# YHARD4 — traduction du CONTENU saisi (i18n des données MAÎTRES, ≠ i18n de
# l'UI, déjà livrée par N93/N94 via frontend/src/i18n/ + parametres.
# TranslationOverride).
#
# ``ContentTranslation`` est un modèle GÉNÉRIQUE réutilisable : n'importe
# quelle app métier peut y stocker une variante de langue d'un de ses champs
# texte (désignation produit, article KB, clause de contrat…) SANS que
# ``core`` importe la moindre app de domaine — la cible est désignée par
# ``content_type`` + ``object_id`` (contenttypes, fondation Django) exactement
# comme ``AuditLog``/``EsignRequest``. Traduction MANUELLE stockée (aucun
# appel machine ici) ; l'aide de lecture ``core.i18n_content.translated_value``
# fait le fallback vers la langue par défaut (FR) quand la variante demandée
# est absente.
# ---------------------------------------------------------------------------


class ContentTranslation(TimestampedModel):
    """Variante de langue d'un champ texte d'un objet métier quelconque.

    Multi-tenant : ``company`` forcée côté serveur. Une seule variante par
    ``(company, content_type, object_id, locale, field)`` — un upsert écrase
    la précédente plutôt que d'en accumuler des doublons.
    """

    class Locale(models.TextChoices):
        FR = 'fr', 'Français'
        EN = 'en', 'English'
        AR = 'ar', 'العربية'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='content_translations', verbose_name='Société')

    content_type = models.ForeignKey(
        'contenttypes.ContentType', on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64)
    content_object = GenericForeignKey('content_type', 'object_id')

    locale = models.CharField(
        'Langue', max_length=5, choices=Locale.choices)
    field = models.CharField(
        'Champ', max_length=100,
        help_text='Nom du champ traduit (ex. « nom », « description », « titre », « corps »).')
    value = models.TextField('Valeur traduite')

    class Meta:
        verbose_name = 'Traduction de contenu'
        verbose_name_plural = 'Traductions de contenu'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'content_type', 'object_id', 'locale', 'field'],
                name='core_contenttranslation_unique'),
        ]
        indexes = [
            models.Index(fields=['company', 'content_type', 'object_id'],
                         name='core_contenttrans_obj_idx'),
        ]

    def __str__(self):
        return f'{self.content_type}#{self.object_id} [{self.locale}] {self.field}'


# ---------------------------------------------------------------------------
# NTPLT6 — Compteurs d'usage par tenant (metering).
#
# Photographie NOCTURNE, par société et par jour, de la consommation :
# nombre de lignes par grosse table, octets MinIO du préfixe société, nombre
# de requêtes API du jour, nombre de tâches Celery. FONDATION technique que
# N100 (plans/billing, volontairement différé) consommera plus tard sans
# re-travail. ``core`` reste FONDATION : aucune app métier n'est importée — les
# comptages passent par le registre Django (get_models) et des string-FK.
# ---------------------------------------------------------------------------


class TenantUsageSnapshot(TimestampedModel):
    """Instantané quotidien d'usage d'une société (metering, NTPLT6).

    Une ligne par ``(company, jour)`` (idempotente : ré-exécuter le snapshot du
    jour met à jour la même ligne). Les comptages sont BORNÉS (COUNT plafonné,
    jamais un scan illimité) et l'ensemble par table vit dans un JSON pour
    rester agnostique du schéma (aucune FK vers une app domaine).
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='usage_snapshots', verbose_name='Société')
    jour = models.DateField(
        'Jour', help_text="Jour de l'instantané (UTC).")

    lignes_par_table = models.JSONField(
        'Lignes par table', default=dict, blank=True,
        help_text="{ 'app_label.Model': nombre_de_lignes } pour les grosses "
                  "tables company-scopées (comptage borné).")
    octets_minio = models.BigIntegerField(
        'Octets MinIO', default=0,
        help_text="Total d'octets stockés sous le préfixe société dans MinIO "
                  "(0 si le stockage est indisponible).")
    nb_requetes_api = models.PositiveIntegerField(
        'Requêtes API du jour', default=0,
        help_text="Somme des requêtes API (ApiUsageRecord) de la société ce "
                  "jour-là.")
    nb_taches_celery = models.PositiveIntegerField(
        'Tâches Celery', default=0,
        help_text="Nombre de tâches Celery attribuables à la société ce jour "
                  "(0 si non instrumenté).")

    class Meta:
        verbose_name = "Instantané d'usage"
        verbose_name_plural = "Instantanés d'usage"
        ordering = ['-jour', 'company_id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'jour'],
                name='core_tenantusage_company_jour'),
        ]
        indexes = [
            models.Index(fields=['company', '-jour'],
                         name='core_tenantusage_co_jour_idx'),
        ]

    def __str__(self):
        return f'Usage {self.company_id} le {self.jour}'


class IdempotencyKey(TimestampedModel):
    """NTPLT28 — clé d'idempotence (repli DB du décorateur ``idempotent_task``).

    Utilisée UNIQUEMENT quand Redis est indisponible : la contrainte unique sur
    ``cle`` garantit qu'une exécution logique (identifiée par ``cle``) n'a lieu
    qu'une fois. Aucune FK ``company`` : la clé encode elle-même son périmètre
    (souvent l'``id`` société + le nom de la tâche + la fenêtre). ``created_at``
    (hérité) sert de base au calcul d'expiration (``ttl``).
    """

    cle = models.CharField('Clé', max_length=255, unique=True)

    class Meta:
        verbose_name = "Clé d'idempotence"
        verbose_name_plural = "Clés d'idempotence"
        ordering = ['-created_at']

    def __str__(self):
        return self.cle


class SequenceCounter(TenantModel):
    """NTPLT41 — allocateur de séquence HAUT DÉBIT (opt-in).

    Compteur monotone par ``(company, cle)`` alloué SOUS ``select_for_update``
    par BLOCS de N — pour les volumes élevés (numéros de jobs internes,
    identifiants de chatter…) où le pattern gapless ``core.numbering`` (max +1
    par scan, réservé aux documents FISCAUX) coûterait trop cher. Ici on
    ASSUME les trous : un bloc réservé et non entièrement consommé laisse un
    intervalle non attribué — jamais un doublon.

    ``dernier`` = dernière valeur RÉSERVÉE. ``allocate(company, cle, n)`` verrou
    la ligne, incrémente de ``n`` en une écriture et renvoie la plage
    ``range(debut, debut + n)`` — 1 000 allocations concurrentes ne produisent
    ni doublon ni trou NON documenté (les trous inter-blocs sont assumés).
    """

    cle = models.CharField(
        'Clé', max_length=100,
        help_text="Nom logique de la séquence (ex. 'job', 'chatter').")
    dernier = models.BigIntegerField('Dernier réservé', default=0)

    class Meta:
        verbose_name = 'Compteur de séquence'
        verbose_name_plural = 'Compteurs de séquence'
        ordering = ['company_id', 'cle']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'cle'],
                name='core_sequencecounter_company_cle'),
        ]

    def __str__(self):
        return f'{self.cle}@{self.company_id}={self.dernier}'

    @classmethod
    def allocate(cls, company, cle, n=1):
        """Réserve un bloc de ``n`` valeurs pour ``(company, cle)``.

        Atomique et race-safe : verrou la ligne (``select_for_update``),
        avance ``dernier`` de ``n`` en une écriture, renvoie ``range(debut,
        fin)`` (les ``n`` entiers réservés). Crée la ligne si absente. ``n``
        doit être ≥ 1.
        """
        from django.db import transaction
        n = max(1, int(n))
        with transaction.atomic():
            row, _ = cls.objects.select_for_update().get_or_create(
                company=company, cle=cle, defaults={'dernier': 0})
            debut = row.dernier + 1
            row.dernier = row.dernier + n
            row.save(update_fields=['dernier', 'updated_at'])
            return range(debut, debut + n)

    @classmethod
    def next(cls, company, cle):
        """Réserve et renvoie UNE valeur (raccourci de ``allocate(...,1)``)."""
        return cls.allocate(company, cle, 1).start


class TenantLimit(TenantModel):
    """NTPLT7 — limite douce de consommation par société (enforcement DOUX).

    Une clé parmi ``max_lignes_table`` / ``max_stockage_mo`` /
    ``max_exports_jour`` porte une ``valeur`` (``0`` = illimité). Consultée par
    dataimport / exports / upload via ``core.limits.verifier`` : un dépassement
    NOTIFIE les admins et pose un en-tête ``X-Quota-Warning`` — JAMAIS un blocage
    dur. Vente : les groupes multi-filiales exigent des garde-fous de
    consommation par entité, sans jamais couper le service.
    """

    CLE_MAX_LIGNES = 'max_lignes_table'
    CLE_MAX_STOCKAGE_MO = 'max_stockage_mo'
    CLE_MAX_EXPORTS_JOUR = 'max_exports_jour'
    CLE_CHOICES = [
        (CLE_MAX_LIGNES, 'Lignes maximum par table'),
        (CLE_MAX_STOCKAGE_MO, 'Stockage maximum (Mo)'),
        (CLE_MAX_EXPORTS_JOUR, 'Exports maximum par jour'),
    ]

    cle = models.CharField('Clé', max_length=32, choices=CLE_CHOICES)
    valeur = models.BigIntegerField(
        'Valeur', default=0,
        help_text='Plafond (0 = illimité).')

    class Meta:
        verbose_name = 'Limite tenant'
        verbose_name_plural = 'Limites tenant'
        ordering = ['company_id', 'cle']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'cle'],
                name='core_tenantlimit_company_cle'),
        ]

    def __str__(self):
        return f'{self.cle}={self.valeur} @{self.company_id}'
