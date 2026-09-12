"""Modèles du module GRC & Conformité (Groupe NTGRC).

Convention du dépôt : tout modèle multi-société hérite de
``core.models.TenantModel`` (FK ``company`` + horodatage, ARC1). Les
références vers une AUTRE app sont déclarées en CHAÎNE (``'app.Model'``) ou
portées par un identifiant texte (``*_ref``) — jamais un import de ses
``models``.
"""
from django.db import models

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
