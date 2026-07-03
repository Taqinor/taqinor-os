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
    # XPRJ23 — étapes du projet (gestion_projet), émis DEPUIS le module (jamais
    # via un signal Django cross-app) ; config {'statut': …} avec les enums
    # PROPRES à gestion_projet (jamais STAGES.py, règle #2).
    PROJET_STATUS_CHANGE = (
        'projet_status_change', 'Changement de statut de projet')
    PROJET_PHASE_CHANGE = (
        'projet_phase_change', 'Changement de phase de projet')


class ActionType(models.TextChoices):
    """Actions qu'une règle peut exécuter en réaction au déclencheur."""
    SEND_WHATSAPP = 'send_whatsapp', 'Envoyer un WhatsApp'
    SEND_EMAIL = 'send_email', 'Envoyer un email'
    SEND_SMS = 'send_sms', 'Envoyer un SMS'
    CREATE_ACTIVITY = 'create_activity', 'Créer une activité / tâche'
    ASSIGN_RECORD = 'assign_record', 'Assigner un enregistrement'
    SET_FIELD = 'set_field', 'Mettre à jour un champ'
    CREATE_SAV_TICKET = 'create_sav_ticket', 'Créer un ticket SAV'


class CanalMessage(models.TextChoices):
    """Canal d'envoi d'un modèle de message d'automatisation."""
    EMAIL = 'email', 'Email'
    WHATSAPP = 'whatsapp', 'WhatsApp'
    DOC = 'doc', 'Document'


# Sujet/corps par défaut par canal. Tant qu'aucun ``ModeleMessage`` n'est
# enregistré pour la société + le canal, ces valeurs s'appliquent — le
# comportement reste IDENTIQUE à l'ancien sujet codé en dur
# « Notification Taqinor ». Le corps reste vide par défaut (l'action retombe
# alors sur ``action_config['body']`` ou un modèle Paramètres, inchangé).
MODELE_MESSAGE_DEFAULTS = {
    CanalMessage.EMAIL: {'objet': 'Notification Taqinor', 'corps': ''},
    CanalMessage.WHATSAPP: {'objet': '', 'corps': ''},
    CanalMessage.DOC: {'objet': 'Notification Taqinor', 'corps': ''},
}


class ModeleMessage(models.Model):
    """Modèle de message éditable par société et par canal (DC18).

    Remplace le sujet d'email codé en dur (« Notification Taqinor ») par un
    modèle stocké et modifiable : un ``objet`` (sujet) et un ``corps`` par
    canal (email / WhatsApp / doc). Tant qu'aucun modèle n'est enregistré pour
    la société + le canal, ``resolve`` retombe sur ``MODELE_MESSAGE_DEFAULTS``
    — le comportement reste donc identique à l'ancien sujet codé en dur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='automation_modeles_message')
    canal = models.CharField(
        max_length=20, choices=CanalMessage.choices)
    objet = models.CharField(max_length=255, blank=True, default='')
    corps = models.TextField(blank=True, default='')
    enabled = models.BooleanField(default=True)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Modèle de message"
        verbose_name_plural = "Modèles de message"
        ordering = ['canal', 'id']
        unique_together = [('company', 'canal')]
        indexes = [
            models.Index(
                fields=['company', 'canal', 'enabled'],
                name='automation_modmsg_idx'),
        ]

    def __str__(self):
        return f'{self.company_id}:{self.canal}'

    @classmethod
    def resolve(cls, company, canal):
        """Renvoie ``(objet, corps)`` pour (société, canal).

        Retombe sur ``MODELE_MESSAGE_DEFAULTS`` quand aucun modèle ACTIVÉ n'est
        enregistré (ou que ses champs sont vides) — comportement préservé.
        """
        default = MODELE_MESSAGE_DEFAULTS.get(
            canal, {'objet': '', 'corps': ''})
        row = None
        if company is not None:
            try:
                row = cls.objects.filter(
                    company=company, canal=canal, enabled=True).first()
            except Exception:  # pragma: no cover - défensif
                row = None
        if row is None:
            return default['objet'], default['corps']
        objet = (row.objet or '').strip() or default['objet']
        corps = (row.corps or '').strip() or default['corps']
        return objet, corps


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
