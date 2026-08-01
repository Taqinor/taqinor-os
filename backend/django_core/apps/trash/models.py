"""NTUX7 — Corbeille transverse 30 jours (`ElementSupprime`).

FONDATION cross-cutting : UNE seule table de corbeille pour TOUT le repo, au
lieu d'un modèle « éléments supprimés » par app. Les apps qui pratiquent déjà le
soft-delete (`is_archived` / `annule` / `core.SoftDeleteModel`) émettent
l'événement `core.events.record_soft_deleted` ; `apps.trash` s'y abonne dans son
`ready()` (voir `receivers.py`) et journalise ici.

GÉNÉRIQUE : la cible est pointée par `contenttypes` (`content_type` +
`object_id`) — jamais un import des `models` d'une autre app (frontière
inter-apps, CLAUDE.md). La restauration passe par le `services.py` de l'app
cible, enregistré dans `registry.py`.

MULTI-TENANT : hérite de `core.models.TenantModel` (FK `company` + timestamps),
jamais une paire company/timestamps réécrite à la main (garde CI SCA4).

DISTINCT de `core.DeletionRecord` (FG388), qui reste la fenêtre d'« annuler »
COURTE (30 minutes) attachée au mixin `core.SoftDeleteModel` : `ElementSupprime`
est la corbeille UTILISATEUR à rétention LONGUE (30 jours) alimentée par
l'événement, avec snapshot d'affichage, expiration et purge planifiée. Les deux
couches cohabitent sans se remplacer.
"""
from datetime import timedelta

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from core.models import TenantModel

# Rétention de la corbeille, en jours (NTUX7). Au-delà, `purger_corbeille`
# (management command, planifiée par NTUX29) supprime définitivement l'entrée.
RETENTION_JOURS = 30


class ElementSupprime(TenantModel):
    """Une entrée de corbeille : un enregistrement soft-supprimé, restaurable
    pendant `RETENTION_JOURS` jours puis purgé définitivement."""

    content_type = models.ForeignKey(
        ContentType,
        # on_delete: composition — sans son type, l'entrée n'a plus de cible
        # résoluble (une entrée orpheline ne serait ni affichable ni restaurable).
        on_delete=models.CASCADE,
        related_name='+', verbose_name='Type de document',
    )
    object_id = models.PositiveIntegerField('Identifiant du document')
    cible = GenericForeignKey('content_type', 'object_id')

    # Libellé de TYPE lisible, posé par l'émetteur (ex. « Devis », « Lead ») —
    # sert le filtre `?type=` de l'écran corbeille sans résoudre la cible.
    type_libelle = models.CharField('Type', max_length=80, blank=True, default='')
    # Snapshot du libellé au moment de la suppression : la cible peut avoir
    # disparu (purge dure) quand on affiche le journal.
    libelle_snapshot = models.CharField('Libellé', max_length=255, blank=True, default='')
    # Best-effort, AFFICHAGE SEUL — jamais réinjecté à la restauration (celle-ci
    # passe toujours par le service de l'app cible, qui reste seul maître de
    # l'état métier).
    donnees_snapshot = models.JSONField('Données (affichage seul)', default=dict, blank=True)

    supprime_par = models.ForeignKey(
        'authentication.CustomUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Supprimé par',
    )
    supprime_le = models.DateTimeField('Supprimé le', default=timezone.now, db_index=True)
    expire_le = models.DateTimeField('Expire le', db_index=True)
    # Renseigné par `services.restaurer` : l'entrée sort de la corbeille active
    # mais RESTE au journal (audit de rétention — NTUX24).
    restaure_le = models.DateTimeField('Restauré le', null=True, blank=True)

    class Meta:
        verbose_name = 'Élément supprimé'
        verbose_name_plural = 'Éléments supprimés'
        ordering = ['-supprime_le', '-id']
        indexes = [
            models.Index(fields=['company', 'restaure_le'],
                         name='trash_co_restaure_idx'),
            models.Index(fields=['company', 'expire_le'],
                         name='trash_co_expire_idx'),
            models.Index(fields=['content_type', 'object_id'],
                         name='trash_cible_idx'),
        ]

    def __str__(self):
        return f'{self.type_libelle or "Élément"} — {self.libelle_snapshot}'.strip(' —')

    def save(self, *args, **kwargs):
        # `expire_le` est TOUJOURS dérivé de `supprime_le` : jamais fourni par
        # un client (la rétention est une règle serveur, pas un paramètre).
        if not self.supprime_le:
            self.supprime_le = timezone.now()
        if not self.expire_le:
            self.expire_le = self.supprime_le + timedelta(days=RETENTION_JOURS)
        return super().save(*args, **kwargs)

    @property
    def cle_modele(self):
        """Clé du modèle cible, ex. ``'crm.lead'`` — la clé du registre de
        restaurateurs (`registry.py`). Chaîne vide si le type a disparu."""
        if self.content_type_id is None:
            return ''
        ct = self.content_type
        return f'{ct.app_label}.{ct.model}'
