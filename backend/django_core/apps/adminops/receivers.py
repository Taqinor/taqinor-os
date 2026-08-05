"""apps.adminops.receivers — récepteurs internes (best-effort, jamais
bloquants), câblés depuis `apps.py::ready()`.

NTADM8 — alerte de franchissement du quota de sièges : à chaque création d'un
CustomUser ACTIF, si le nombre de sièges utilisés atteint/dépasse
``CompanyProfile.nb_sieges_max``, notifie chaque Administrateur actif de la
société. JAMAIS BLOQUANT : la création du compte a déjà réussi quand ce
récepteur s'exécute (``post_save``) — aucune exception ici ne peut l'annuler.
``authentication`` est une app de FONDATION (exempte de la frontière
cross-app inter-domaines métier) : l'import direct de son modèle est
autorisé.

NTADM41 — le même franchissement déclenche AUSSI le webhook sortant
``sieges.quota_atteint`` (``apps.publicapi``), payload {company_id,
sieges_utilises, sieges_max} — JAMAIS de donnée client.

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

from django.db.models.signals import post_save, pre_save

logger = logging.getLogger(__name__)

#: Préfixe stable du marqueur — greppable en base et testé.
MARQUEUR_IMPERSONATION = '[IMPERSONATION'


# ---------------------------------------------------------------------------
# NTADM8/NTADM41 — quota de sièges
# ---------------------------------------------------------------------------

def _statut_sieges(company):
    from apps.parametres.models import CompanyProfile
    from authentication.services import sieges_utilises

    # JAMAIS ``CompanyProfile.get`` ici : ce classmethod get-or-CREATE, et un
    # signal ne doit jamais écrire une ligne en effet de bord (collision
    # « profile existe déjà » dans tout test qui crée le sien explicitement).
    profile = CompanyProfile.objects.filter(company=company).first()
    if profile is None:
        return None  # pas de profil = pas de quota configuré
    max_sieges = profile.nb_sieges_max
    if not max_sieges:
        return None  # illimité (défaut) — rien à signaler
    utilises = sieges_utilises(company)
    if utilises < max_sieges:
        return None  # sous le quota — rien à signaler
    return utilises, max_sieges


def _alerter_administrateurs(company, utilises, max_sieges):
    try:
        from authentication.models import CustomUser
        from apps.notifications.models import EventType
        from apps.notifications.services import notify_many
        admins = list(CustomUser.admins_actifs_qs(company))
        notify_many(
            admins, EventType.DIGEST, 'Quota de sièges atteint',
            body=(f'Vous avez atteint votre quota de {max_sieges} sièges — '
                  'contactez-nous pour l\'augmenter.'),
            company=company)
    except Exception:  # noqa: BLE001 — jamais bloquant
        pass


def _dispatch_webhook_quota(company, utilises, max_sieges):
    """NTADM41 — webhook sortant `sieges.quota_atteint`. Jamais de donnée
    client dans le payload."""
    try:
        from apps.publicapi import delivery
        from apps.publicapi.constants import EVENT_SIEGES_QUOTA_ATTEINT
        delivery.dispatch_event(company.id, EVENT_SIEGES_QUOTA_ATTEINT, {
            'event': EVENT_SIEGES_QUOTA_ATTEINT,
            'company_id': company.id,
            'sieges_utilises': utilises,
            'sieges_max': max_sieges,
        })
    except Exception:  # noqa: BLE001 — jamais bloquant
        pass


def user_post_save_quota_sieges(sender, instance, created, **kwargs):
    if not created or not instance.is_active:
        return
    company = getattr(instance, 'company', None)
    if company is None:
        return
    try:
        resultat = _statut_sieges(company)
    except Exception:  # noqa: BLE001 — jamais bloquant
        return
    if resultat is None:
        return
    utilises, max_sieges = resultat
    _alerter_administrateurs(company, utilises, max_sieges)
    _dispatch_webhook_quota(company, utilises, max_sieges)


# ---------------------------------------------------------------------------
# NTADM22 — marquage d'audit des sessions d'impersonation
# ---------------------------------------------------------------------------

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


def connect():
    """Branche TOUS les récepteurs de l'app. Appelé depuis AppConfig.ready()
    (idempotent via ``dispatch_uid``)."""
    from authentication.models import CustomUser
    post_save.connect(
        user_post_save_quota_sieges, sender=CustomUser,
        dispatch_uid='adminops_quota_sieges')
    try:
        from apps.audit.models import AuditLog
        pre_save.connect(
            marquer_ligne_audit_impersonation,
            sender=AuditLog,
            dispatch_uid='adminops.marquer_ligne_audit_impersonation',
        )
    except Exception:  # noqa: BLE001 — une app d'audit absente ne casse rien
        logger.debug('adminops: câblage du marquage audit impossible',
                     exc_info=True)
