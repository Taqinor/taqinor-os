"""NTEXT20/NTEXT21 — points d'extension UI déclaratifs (boutons + onglets
custom sur une fiche).

Modèles définis ICI (même patron d'éclatement que ``core/sharing.py`` /
``core/field_permissions.py`` — évite l'import circulaire avec
``core.models``) et réexportés en fin de ``core/models.py`` pour la
découverte Django (app_label ``core``, migrations).

``core`` reste une couche de FONDATION : ``cible`` est une CHAÎNE opaque
(``'crm.lead'``, ``'ventes.devis'``…), jamais une FK ni un import de modèle
métier (contrat import-linter ``core-foundation-is-a-base-layer``). Le
DÉCLENCHEMENT réel d'un bouton (NTEXT20) est délégué à un gestionnaire
ENREGISTRÉ par l'app propriétaire du ``type_action`` — même patron que
``core.workflow.register_delegation_resolver`` (``apps.automation`` s'y
branche depuis son propre ``ready()``) — jamais un import direct
``core -> apps.*``.
"""
from __future__ import annotations

import logging

from django.db import models

logger = logging.getLogger(__name__)


class UiActionBouton(models.Model):
    """NTEXT20 — bouton d'action custom posé sur une fiche."""

    class TypeAction(models.TextChoices):
        AUTOMATION = 'automation', 'Automatisation'
        WEBHOOK = 'webhook', 'Webhook'
        SERVER_ACTION = 'server_action', 'Action serveur'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ui_action_boutons', verbose_name='Société')
    cible = models.CharField(
        'Cible', max_length=80,
        help_text="Nom de fiche visé, ex. « crm.lead », « ventes.devis ».")
    libelle = models.CharField('Libellé', max_length=120)
    icone = models.CharField('Icône', max_length=40, blank=True, default='')
    type_action = models.CharField(
        max_length=20, choices=TypeAction.choices)
    ref = models.PositiveIntegerField(
        'Référence',
        help_text="Id de la règle d'automatisation / de l'abonnement "
                  "webhook / de l'action serveur lié(e).")
    role_tier = models.CharField(
        'Palier de rôle', max_length=40, blank=True, default='',
        help_text='Vide = visible de tous les paliers.')
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Bouton personnalisé'
        verbose_name_plural = 'Boutons personnalisés'
        ordering = ['cible', 'ordre', 'id']
        indexes = [
            models.Index(fields=['company', 'cible', 'actif'],
                         name='core_uiactionbouton_idx'),
        ]

    def __str__(self):
        return f'{self.cible}:{self.libelle}'


_TRIGGER_HANDLERS: dict = {}


def register_trigger_handler(type_action, handler):
    """Enregistre le gestionnaire de déclenchement d'UN ``type_action``.

    ``handler(company, ref, target_model, target_id, user) -> (ok, message)``.
    Même patron que ``core.workflow.register_delegation_resolver`` : ``core``
    ne connaît AUCUNE app métier, c'est l'app propriétaire du type d'action
    (ex. ``apps.automation``) qui s'enregistre depuis son propre ``ready()``.
    """
    if not type_action or not callable(handler):
        raise ValueError(
            'Gestionnaire de déclenchement UI : type + fonction requis.')
    _TRIGGER_HANDLERS[type_action] = handler


def trigger_handlers():
    """Copie du registre (inspection/tests)."""
    return dict(_TRIGGER_HANDLERS)


def declencher_bouton(bouton, target_model, target_id, user=None):
    """Déclenche l'action liée à ``bouton`` sur ``target_model``:``target_id``.

    Renvoie ``(ok: bool, message: str)``. Un ``type_action`` sans gestionnaire
    enregistré (app propriétaire pas encore branchée) est un NO-OP FR propre,
    jamais une exception — pas plus qu'un gestionnaire qui en lève une."""
    handler = _TRIGGER_HANDLERS.get(bouton.type_action)
    if handler is None:
        return False, (
            f'Type d\'action « {bouton.type_action} » non pris en charge '
            '(aucun gestionnaire enregistré).')
    try:
        return handler(
            bouton.company, bouton.ref, target_model, target_id, user)
    except Exception as exc:  # pragma: no cover - défensif
        logger.exception(
            'ui_extensions: déclenchement du bouton %s échoué', bouton.pk)
        return False, str(exc)


class UiOngletCustom(models.Model):
    """NTEXT21 — onglet custom posé sur une fiche."""

    class TypeContenu(models.TextChoices):
        OBJET_CUSTOM_LIE = 'objet_custom_lie', 'Objet personnalisé lié'
        RAPPORT = 'rapport', 'Rapport'
        HTML = 'html', 'HTML'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='ui_onglets_custom', verbose_name='Société')
    cible = models.CharField('Cible', max_length=80)
    titre = models.CharField('Titre', max_length=120)
    type_contenu = models.CharField(
        max_length=20, choices=TypeContenu.choices)
    ref = models.CharField(
        'Référence', max_length=120, blank=True, default='',
        help_text="Code de l'objet personnalisé lié / id du rapport / "
                  "contenu HTML selon type_contenu.")
    # NTEXT21 — arbre core.rules OPTIONNEL : l'onglet n'est proposé que si
    # cette condition est vraie sur le contexte de la fiche (même moteur
    # FG367 que les conditions de champ XPLT15 et de step NTEXT5).
    condition = models.JSONField(null=True, blank=True)
    ordre = models.PositiveIntegerField(default=0)
    role_tier = models.CharField(
        'Palier de rôle', max_length=40, blank=True, default='')
    actif = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Onglet personnalisé'
        verbose_name_plural = 'Onglets personnalisés'
        ordering = ['cible', 'ordre', 'id']
        indexes = [
            models.Index(fields=['company', 'cible', 'actif'],
                         name='core_uiongletcustom_idx'),
        ]

    def __str__(self):
        return f'{self.cible}:{self.titre}'


_ONGLET_RESOLVERS: dict = {}


def register_onglet_resolver(type_contenu, resolver):
    """Enregistre le résolveur de CONTENU d'un ``type_contenu`` d'onglet.

    ``resolver(company, ref, target_model, target_id) -> list[dict]``. Même
    patron de registre que ``register_trigger_handler`` ci-dessus : l'app
    propriétaire du type de contenu (ex. ``apps.customfields`` pour
    ``objet_custom_lie``) s'enregistre depuis son propre ``ready()``.
    """
    if not type_contenu or not callable(resolver):
        raise ValueError(
            "Résolveur de contenu d'onglet : type + fonction requis.")
    _ONGLET_RESOLVERS[type_contenu] = resolver


def onglet_resolvers():
    """Copie du registre (inspection/tests)."""
    return dict(_ONGLET_RESOLVERS)


def resoudre_contenu_onglet(onglet, target_model, target_id):
    """Contenu de ``onglet`` (NTEXT21) pour ``target_model``:``target_id``.

    Renvoie une liste (vide si aucun résolveur enregistré pour son
    ``type_contenu``, ou si la résolution échoue) — jamais une exception."""
    resolver = _ONGLET_RESOLVERS.get(onglet.type_contenu)
    if resolver is None:
        return []
    try:
        return resolver(
            onglet.company, onglet.ref, target_model, target_id) or []
    except Exception:  # pragma: no cover - défensif
        logger.exception(
            "ui_extensions: contenu de l'onglet %s illisible", onglet.pk)
        return []
