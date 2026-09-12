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
