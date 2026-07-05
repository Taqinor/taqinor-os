"""YHARD2 — journal des actions IA confirmées + rollback.

Contexte : le registre ``apps.agent.registry`` (AG1) est un catalogue PUR
(metadonnees en memoire, aucune ecriture) — l'execution effective d'une action
proposee par l'agent reste le relais FastAPI + les endpoints Django existants
(chaque endpoint re-verifie sa propre permission/societe). Ce module ajoute la
PERSISTANCE qui manquait : une trace durable de CHAQUE action confirmee par un
utilisateur (par opposition a une ecriture manuelle "normale"), avec assez
d'information pour l'annuler si l'action est reversible.

``AgentActionLog`` est rempli au moment de la CONFIRMATION (pas de la simple
proposition, qui reste ephemere/HMAC cote agent) via
``apps.agent.services.log_confirmed_action``. La cible resultante est designee
par content_type + object_id (fondation, aucun import d'app metier) — cette
app reste un satellite technique, jamais importe par une app de domaine.
"""
from django.conf import settings
from django.db import models


class AgentActionLog(models.Model):
    class RiskLevel(models.TextChoices):
        INTERNAL = 'internal', 'Interne'
        OUTWARD = 'outward', 'Effet externe'
        IRREVERSIBLE = 'irreversible', 'Irréversible'

    # Société forcée côté serveur (jamais depuis le corps de requête).
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='agent_action_logs', verbose_name='Société')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='agent_action_logs')

    action_key = models.CharField(
        "Clé de l'action", max_length=100,
        help_text="Clé stable du registre (apps.agent.registry.AgentAction.key).")
    risk_level = models.CharField(
        'Niveau de risque', max_length=20, choices=RiskLevel.choices)
    proposal_hash = models.CharField(
        'Empreinte de la proposition', max_length=128, blank=True, default='',
        help_text='Empreinte HMAC de la proposition confirmée (traçabilité, non secrète).')
    inputs_json = models.JSONField(
        'Paramètres', default=dict, blank=True,
        help_text="Paramètres fournis par l'utilisateur au moment de la confirmation.")

    proposed_at = models.DateTimeField('Proposée le', null=True, blank=True)
    confirmed_at = models.DateTimeField('Confirmée le', auto_now_add=True)
    executed_at = models.DateTimeField('Exécutée le', null=True, blank=True)

    # Objet résultant (générique — jamais d'import d'app métier).
    content_type = models.ForeignKey(
        'contenttypes.ContentType', on_delete=models.SET_NULL,
        null=True, blank=True)
    object_id = models.CharField(max_length=64, blank=True, default='')
    object_repr = models.CharField(max_length=255, blank=True, default='')

    undone_at = models.DateTimeField('Annulée le', null=True, blank=True)
    undo_detail = models.TextField('Détail annulation', blank=True, default='')

    class Meta:
        ordering = ['-confirmed_at']
        verbose_name = 'Action IA confirmée'
        verbose_name_plural = 'Actions IA confirmées'
        indexes = [
            models.Index(fields=['company', '-confirmed_at']),
            models.Index(fields=['company', 'action_key']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f'{self.action_key} ({self.risk_level}) @ {self.confirmed_at:%Y-%m-%d %H:%M}'

    @property
    def is_undone(self):
        return self.undone_at is not None

    @property
    def is_undoable(self):
        """Seules les actions à effet réversible sont candidates à
        l'annulation — une action irréversible ne l'est jamais, même si un
        handler existait."""
        return (
            self.risk_level != self.RiskLevel.IRREVERSIBLE
            and self.undone_at is None
        )
