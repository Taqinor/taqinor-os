"""Signaux du bus du SAV (propriétaire sav).

SPL290 — extrait de ``core/events/__init__.py`` (move only). Ré-exporté
par ``from .sav import *`` dans ``core/events/__init__.py`` :
les émetteurs et abonnés continuent d'importer ``core.events``.

Événements
----------

``ticket_resolu``
    Émis quand un ``sav.Ticket`` bascule vers RESOLU (ARC37) — aux DEUX sites
    où cette bascule peut être atteinte : l'action gardée ``resoudre``
    (``apps/sav/views.py``, via ``sav.services.emettre_ticket_resolu``) et
    l'avancement automatique sur intervention terminée
    (``apps/sav/receivers.py``, YSERV2). Émis SYNCHRONE, best-effort,
    uniquement sur le FRANCHISSEMENT (un ticket déjà RESOLU/CLOTURE ne réémet
    rien — même garde que les autres transitions SAV). Ne change AUCUN statut
    lui-même (l'émission suit la bascule déjà actée). Arguments du signal :

    * ``ticket`` — l'instance ``sav.Ticket`` désormais RESOLU ;
    * ``company`` — la société (posée côté serveur) ;
    * ``user`` — l'utilisateur qui a déclenché la transition (peut être
      ``None`` pour une résolution automatique) ;
    * ``ancien_statut`` — le statut avant la transition.

    Abonnés dans ce repo (ARC37) : ``notifications``
    (``apps/notifications/signals.py`` — notifie le technicien assigné, repli
    managers, ``EventType.SAV_TICKET_RESOLU``) et ``crm``
    (``apps/crm/receivers.py`` — note chatter ARC8 sur le ``crm.Client`` du
    ticket, sans jamais importer ``apps.sav``).

``equipement_remplace``
    Émis quand un ``sav.Equipement`` est marqué REMPLACE suite au retrait
    d'une pièce (ARC37, ``sav.services.retirer_piece``). Émis SYNCHRONE,
    best-effort, à l'unique site de la bascule. Ne change AUCUN statut
    lui-même. Arguments du signal :

    * ``equipement`` — l'instance ``sav.Equipement`` désormais REMPLACE ;
    * ``ticket`` — le ``sav.Ticket`` dont le retrait de pièce a déclenché le
      remplacement ;
    * ``company`` — la société (posée côté serveur) ;
    * ``user`` — l'utilisateur qui a retiré la pièce (peut être ``None``).

    Abonné dans ce repo (ARC37) : ``notifications``
    (``apps/notifications/signals.py`` — notifie les managers,
    ``EventType.SAV_EQUIPEMENT_REMPLACE``).
"""
import django.dispatch


# Émis quand un Ticket SAV bascule vers RESOLU (ARC37). Arguments : ticket,
# company, user (peut être None), ancien_statut. Abonnés dans ce repo :
# notifications (EventType.SAV_TICKET_RESOLU) et crm (chatter ARC8 sur le
# Client lié) — voir docstring du module ci-dessus.
ticket_resolu = django.dispatch.Signal()

# Émis quand un Equipement SAV est marqué REMPLACE suite au retrait d'une
# pièce (ARC37). Arguments : equipement, ticket, company, user (peut être
# None). Abonné dans ce repo : notifications (EventType.
# SAV_EQUIPEMENT_REMPLACE) — voir docstring du module ci-dessus.
equipement_remplace = django.dispatch.Signal()

__all__ = [
    'ticket_resolu',
    'equipement_remplace',
]
