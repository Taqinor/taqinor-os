"""Récepteurs d'événements métier (M6) — Gestion de projet (XPRJ9).

Abonne ``gestion_projet`` aux événements du cœur métier exposés par
``core.events``, pour réagir à des changements d'état déclenchés par d'autres
apps (ex. ``rh``) sans que celles-ci importent ``gestion_projet``. Câblé au
démarrage par ``GestionProjetConfig.ready`` — même patron que
``apps/crm/receivers.py`` (abonnement à ``devis_accepted``/``devis_sent``).
"""
from django.dispatch import receiver

from core.events import conge_approuve


@receiver(conge_approuve, dispatch_uid="gestion_projet_indispo_on_conge_approuve")
def _synchroniser_indisponibilite_on_conge_approuve(
        sender, demande, user, annule, **kwargs):
    """Synchronise l'``Indisponibilite`` planning à la validation d'un congé.

    À la validation (``annule=False``) : crée/étend l'``Indisponibilite`` de
    type CONGÉ de la ``RessourceProfil`` liée au même utilisateur que
    ``demande.employe.user`` (idempotent — un ``update_or_create`` sur la
    fenêtre exacte de la demande ne duplique jamais). À l'annulation
    (``annule=True``) : ferme (supprime) l'indisponibilité correspondante si
    elle existe encore.

    Un employé sans compte utilisateur, ou un utilisateur sans
    ``RessourceProfil`` liée dans ce module, est ignoré PROPREMENT (aucune
    exception ne doit jamais remonter au bus — un abonné qui casse ne doit
    jamais casser l'émetteur).
    """
    try:
        from .services import synchroniser_indisponibilite_conge
        synchroniser_indisponibilite_conge(demande, annule=annule)
    except Exception:  # pragma: no cover - défensif, un abonné isolé
        pass
