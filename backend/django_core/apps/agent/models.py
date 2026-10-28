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

from core.models import TenantModel


class AgentActionLog(models.Model):
    class RiskLevel(models.TextChoices):
        INTERNAL = 'internal', 'Interne'
        OUTWARD = 'outward', 'Effet externe'
        IRREVERSIBLE = 'irreversible', 'Irréversible'

    # Société forcée côté serveur (jamais depuis le corps de requête).
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
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
        """Une action est candidate à l'annulation si son effet est
        réversible (jamais une action IRREVERSIBLE), qu'elle n'est pas déjà
        annulée, ET qu'un handler de rollback est RÉELLEMENT enregistré pour
        sa ``action_key`` (AUDV27 — cette propriété ignorait ce 3e critère :
        elle disait « annulable » pour une action réversible SANS handler,
        le bouton « annuler » du journal apparaissait alors pour une
        annulation qui échouait systématiquement en ``ActionNotUndoableError``
        côté serveur)."""
        from .services import has_undo_handler

        return (
            self.risk_level != self.RiskLevel.IRREVERSIBLE
            and self.undone_at is None
            and has_undo_handler(self.action_key)
        )


class AssistantEvent(TenantModel):
    """AIC6 — une requête de l'assistant des commerciaux = UN événement
    (contrat ``contract_samples/assistant_evenement.json``, AIC1).

    Écrit par le RELAIS SERVEUR (FastAPI, preuve HMAC), jamais par le
    navigateur ; ``company``/``user`` toujours posés côté serveur. Le navigateur
    ne modifie que ``note`` et ``commentaire`` de SON événement. Journal séparé
    d'``AgentActionLog`` (actions confirmées) — jamais fusionné."""

    class Intention(models.TextChoices):
        QUESTION_MANUEL = 'question_manuel', 'Question sur le manuel'
        DONNEE = 'donnee', 'Donnée'
        ACTION = 'action', 'Action'
        BUG = 'bug', 'Bug'
        MANQUE = 'manque', 'Fonction manquante'
        HORS_CHAMP = 'hors_champ', 'Hors champ'

    class Note(models.IntegerChoices):
        NEGATIVE = -1, 'Pouce bas'
        AUCUNE = 0, 'Pas encore noté'
        POSITIVE = 1, 'Pouce haut'

    # ``company`` + ``created_at``/``updated_at`` : hérités de TenantModel (SCA4).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assistant_events')
    intention = models.CharField(
        max_length=20, choices=Intention.choices, default=Intention.DONNEE)
    question = models.TextField('Question', max_length=2000)
    resume_reponse = models.CharField(
        'Résumé de la réponse', max_length=500, blank=True, default='')
    ecran = models.CharField('Écran', max_length=255, blank=True, default='')
    # Lead de la société (résolu via apps.crm.selectors) — entier simple : la
    # frontière cross-app interdit d'importer le modèle crm ici.
    lead_id = models.PositiveIntegerField('Lead', null=True, blank=True)
    outils_appeles = models.JSONField('Outils appelés', default=list, blank=True)
    erreur = models.JSONField('Erreur', null=True, blank=True)
    note = models.SmallIntegerField(choices=Note.choices, default=Note.AUCUNE)
    commentaire = models.CharField(max_length=200, null=True, blank=True)
    modele = models.CharField('Modèle', max_length=64, blank=True, default='')
    repli = models.BooleanField('Repli Groq', default=False)
    manuel_present = models.BooleanField('Manuel présent', default=False)
    tokens = models.JSONField('Tokens', default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Événement de l'assistant"
        verbose_name_plural = "Événements de l'assistant"
        indexes = [
            models.Index(fields=['company', 'created_at'],
                         name='agent_aev_company_created'),
            models.Index(fields=['company', 'intention'],
                         name='agent_aev_company_intent'),
        ]

    def __str__(self):
        return f'{self.intention} @ {self.created_at:%Y-%m-%d %H:%M}'
