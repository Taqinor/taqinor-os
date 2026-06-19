"""Moteur d'automatisations sans code (N72 / N73).

Une règle ``AutomationRule`` est un « si ceci → alors cela » que le founder
compose dans Paramètres. Elle réagit aux ÉVÉNEMENTS PROPRES de l'application
(signaux Django ``post_save`` sur les modèles existants : Lead, Devis, Facture,
chantier, équipement, stock), trouve les règles activées de la même société qui
correspondent au déclencheur, et exécute leurs actions EN PROCESSUS — aucun
courtier de messages, aucun n8n.

Tout est ADDITIF et OPT-IN : sans règle, rien ne change. Chaque exécution est
journalisée dans ``AutomationRun``. Quand une action est marquée « nécessite
approbation » (N73), une ``AutomationApproval`` en attente est créée au lieu de
lancer l'action ; l'approbation par un palier propriétaire (admin/responsable)
relance l'action différée.

Les envois (WhatsApp / email / SMS) RÉUTILISENT les canaux existants et restent
sans effet (no-op journalisé) quand ils ne sont pas configurés. Jamais de prix
d'achat ni de marge exposés.
"""
from django.conf import settings
from django.db import models


class TriggerType(models.TextChoices):
    """Événements internes de l'application qu'une règle peut écouter."""
    LEAD_STAGE_CHANGE = 'lead_stage_change', "Changement d'étape d'un lead"
    DEVIS_ACCEPTED = 'devis_accepted', 'Devis accepté'
    CHANTIER_STATUS = 'chantier_status', "Chantier atteint un statut"
    FACTURE_OVERDUE = 'facture_overdue', 'Facture en retard'
    WARRANTY_EXPIRING = 'warranty_expiring', 'Garantie proche expiration'
    MAINTENANCE_DUE = 'maintenance_due', 'Visite de maintenance due'
    STOCK_BELOW_THRESHOLD = 'stock_below_threshold', 'Stock sous le seuil'


class ActionType(models.TextChoices):
    """Actions qu'une règle peut exécuter en réaction au déclencheur."""
    SEND_WHATSAPP = 'send_whatsapp', 'Envoyer un WhatsApp'
    SEND_EMAIL = 'send_email', 'Envoyer un email'
    SEND_SMS = 'send_sms', 'Envoyer un SMS'
    CREATE_ACTIVITY = 'create_activity', 'Créer une activité / tâche'
    ASSIGN_RECORD = 'assign_record', 'Assigner un enregistrement'
    SET_FIELD = 'set_field', 'Mettre à jour un champ'
    CREATE_SAV_TICKET = 'create_sav_ticket', 'Créer un ticket SAV'


class AutomationRule(models.Model):
    """Règle d'automatisation éditable (N72), par société.

    ``trigger_config`` et ``action_config`` sont des dictionnaires JSON libres
    interprétés par le moteur selon ``trigger_type`` / ``action_type`` (ex.
    ``trigger_config={'stage': 'SIGNED'}`` ou
    ``action_config={'field': 'priorite', 'value': 'haute'}``).

    ``requires_approval`` (N73) : quand vrai, la correspondance crée une
    approbation en attente au lieu de lancer l'action ; l'approbation relance
    l'action différée.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='automation_rules')
    nom = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)

    trigger_type = models.CharField(
        max_length=40, choices=TriggerType.choices)
    trigger_config = models.JSONField(default=dict, blank=True)

    action_type = models.CharField(
        max_length=40, choices=ActionType.choices)
    action_config = models.JSONField(default=dict, blank=True)

    # N73 — l'action passe par une étape d'approbation propriétaire.
    requires_approval = models.BooleanField(default=False)
    # Seuil configurable au-delà duquel l'approbation s'applique (ex. remise %).
    # Vide = l'approbation s'applique inconditionnellement quand
    # requires_approval est vrai.
    approval_threshold = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)

    ordre = models.PositiveIntegerField(default=0)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Règle d'automatisation"
        verbose_name_plural = "Règles d'automatisation"
        ordering = ['ordre', 'id']
        indexes = [
            models.Index(fields=['company', 'enabled', 'trigger_type']),
        ]

    def __str__(self):
        return self.nom


class AutomationRun(models.Model):
    """Journal d'UNE exécution de règle (N72) — chaque tentative est tracée."""

    class Status(models.TextChoices):
        SUCCESS = 'success', 'Réussi'
        SKIPPED = 'skipped', 'Ignoré'
        FAILED = 'failed', 'Échec'
        PENDING_APPROVAL = 'pending_approval', "En attente d'approbation"
        NOOP = 'noop', 'Sans effet'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='automation_runs')
    rule = models.ForeignKey(
        AutomationRule, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='runs')
    # Référence libre vers l'objet déclencheur (label + id), sans FK rigide :
    # le moteur écoute des modèles hétérogènes.
    target_model = models.CharField(max_length=120, blank=True, default='')
    target_id = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SUCCESS)
    message = models.TextField(blank=True, default='')

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Exécution d'automatisation"
        verbose_name_plural = "Exécutions d'automatisation"
        ordering = ['-timestamp', '-id']
        indexes = [
            models.Index(fields=['company', '-timestamp']),
        ]

    def __str__(self):
        return f'{self.rule_id}:{self.status}@{self.timestamp:%Y-%m-%d %H:%M}'


class AutomationApproval(models.Model):
    """Étape d'approbation propriétaire (N73) pour une action différée.

    Quand une règle correspond mais que son action exige une approbation, on
    crée une approbation EN ATTENTE au lieu de lancer l'action. Un palier
    propriétaire (admin/responsable) approuve — ce qui relance l'action
    différée — ou rejette.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'En attente'
        APPROVED = 'approved', 'Approuvé'
        REJECTED = 'rejected', 'Rejeté'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='automation_approvals')
    rule = models.ForeignKey(
        AutomationRule, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approvals')

    # Référence vers l'objet concerné (label + id) — l'action différée s'y
    # rapplique à l'approbation.
    target_model = models.CharField(max_length=120, blank=True, default='')
    target_id = models.PositiveIntegerField(null=True, blank=True)

    # Description lisible de l'action en attente + son contexte gelé.
    description = models.CharField(max_length=255, blank=True, default='')
    context = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='automation_approvals_requested')
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='automation_approvals_decided')
    decided_at = models.DateTimeField(null=True, blank=True)

    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Approbation d'automatisation"
        verbose_name_plural = "Approbations d'automatisation"
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(fields=['company', 'status']),
        ]

    def __str__(self):
        return f'{self.rule_id}:{self.status}'
