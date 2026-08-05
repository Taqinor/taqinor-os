"""apps.adminops.receivers — récepteurs internes (best-effort, jamais
bloquants), câblés depuis `apps.py::ready()`.

NTADM22 — marquage d'audit des sessions d'impersonation
--------------------------------------------------------
Pendant une session support, TOUTE ligne d'audit écrite par la requête doit
porter la marque « via impersonation » + l'identité du support. Le marquage est
posé en ``pre_save`` — donc AVANT l'INSERT et avant le chaînage
d'inviolabilité NTSEC17 (``recorder._chain_entry`` hache la ligne telle
qu'enregistrée, ``detail`` compris) : la chaîne reste valide, jamais réécrite
après coup.

Le marqueur vit dans ``detail`` (TextField, toujours présent, couvert par le
hachage) et NON dans ``changes`` : ce dernier porte un diff structuré
``[{field, old, new}]`` consommé par ``audit.selectors.reconstruct_as_of`` —
y injecter une forme différente casserait la relecture. Le détail structuré
complet (qui, pour qui, pourquoi, quand) vit de toute façon dans la ligne
``SessionImpersonation`` référencée par le marqueur.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Préfixe stable du marqueur — greppable en base et testé.
MARQUEUR_IMPERSONATION = '[IMPERSONATION'


def marquer_ligne_audit_impersonation(sender, instance, **kwargs):
    """``pre_save`` sur ``AuditLog`` : suffixe ``detail`` si la requête courante
    est une session d'impersonation active.

    Best-effort absolu : toute erreur est avalée — le journal d'audit ne doit
    jamais faire échouer la requête de l'utilisateur."""
    try:
        if getattr(instance, 'pk', None):
            return  # mise à jour d'une ligne existante : jamais re-marquée
        detail = instance.detail or ''
        if MARQUEUR_IMPERSONATION in detail:
            return  # idempotent

        from apps.audit.recorder import current_request

        request = current_request()
        if request is None:
            return

        from .impersonation_service import session_depuis_requete

        session = session_depuis_requete(request)
        if session is None:
            return

        support = getattr(session.initiee_par, 'username', '') or '?'
        marque = (f'{MARQUEUR_IMPERSONATION} session={session.pk} '
                  f'support={support}]')
        instance.detail = f'{detail} {marque}'.strip()
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.debug('adminops: marquage impersonation échoué', exc_info=True)


def register_receivers():
    """Branche les récepteurs de cette app (idempotent via ``dispatch_uid``)."""
    try:
        from django.db.models.signals import pre_save

        from apps.audit.models import AuditLog

        pre_save.connect(
            marquer_ligne_audit_impersonation,
            sender=AuditLog,
            dispatch_uid='adminops.marquer_ligne_audit_impersonation',
        )
    except Exception:  # noqa: BLE001 — une app d'audit absente ne casse rien
        logger.debug('adminops: câblage du marquage audit impossible',
                     exc_info=True)


register_receivers()
