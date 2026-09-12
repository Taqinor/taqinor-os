"""Abonnements de ``apps.juridique`` au bus d'événements ``core.events`` (M6).

Branché depuis ``JuridiqueConfig.ready()`` (import fonction-local, aucun cycle
au chargement des apps).

NTJUR26 — à la clôture d'un dossier, l'événement ``dossier_juridique_clos``
lève la bannière « reprendre la provision » (NTJUR15) **sans aucune action
manuelle préalable**. C'est une PROPOSITION : aucune écriture comptable n'est
postée ici, ni nulle part ailleurs sans confirmation explicite.
"""
from __future__ import annotations

from django.dispatch import receiver

from core import events


@receiver(events.dossier_juridique_clos,
          dispatch_uid='juridique_proposer_reprise_provision')
def proposer_reprise_provision(sender, dossier=None, **kwargs):
    """Lève la bannière de reprise si le dossier clos porte une provision.

    Idempotent : une bannière déjà traitée (reprise effectuée OU abandon
    explicite) n'est jamais relevée — la proposition ne revient pas hanter
    l'écran à chaque rechargement.
    """
    if dossier is None:
        return
    if not dossier.provision_comptable_id:
        return
    if dossier.reprise_provision_traitee or dossier.reprise_provision_proposee:
        return
    dossier.reprise_provision_proposee = True
    dossier.save(update_fields=['reprise_provision_proposee', 'updated_at'])
