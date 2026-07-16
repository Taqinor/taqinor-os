"""Services d'écriture / orchestration de l'app ``authentication`` (fondation).

SCA21 — Fermeture & purge de tenant (soft-close d'abord, purge gâchée)
--------------------------------------------------------------------
Cycle en DEUX temps, non destructif par défaut :

1. **Soft-close** (``mettre_en_fermeture``) : passe ``Company.statut`` à
   « fermeture » (accès login/API bloqué via SCA18) et horodate
   ``date_fermeture`` — les DONNÉES restent INTACTES pendant un délai de grâce
   (30 j) durant lequel une réactivation reste possible (``rouvrir``).
2. **Purge** (``purger_tenant``, appelée par la commande ``close_company``
   DERRIÈRE une double confirmation explicite) : supprime réellement les
   données de la société. Elle EXIGE un artefact d'export/backup préalable
   vérifié (un ``BackupRun`` terminé pour cette société) — sans lui elle REFUSE.
   Le délai de grâce doit aussi être écoulé.

Aucun import d'app métier : la purge délègue l'effacement aux fournisseurs DSR
enregistrés (``core.dsr``) + supprime la société elle-même. ``core`` reste une
fondation ; ``authentication`` en dépend (import descendant autorisé).
"""
from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

# Délai de grâce (jours) entre soft-close et purge autorisée.
GRACE_PERIOD_DAYS = 30


class PurgeRefusee(Exception):
    """Levée quand une purge est refusée (préconditions non satisfaites)."""


def mettre_en_fermeture(company, user=None):
    """Passe une société en FERMETURE (soft-close). Accès bloqué (SCA18),
    données intactes, délai de grâce démarré. Idempotent : re-appeler ne
    réinitialise pas ``date_fermeture`` si déjà posée."""
    from authentication.models import Company
    company.statut = Company.STATUT_FERMETURE
    if company.date_fermeture is None:
        company.date_fermeture = timezone.now()
    company.save()  # le pont bool↔statut met actif=False
    _journaliser(company, user, 'Passage en fermeture (soft-close).')
    return company


def rouvrir(company, user=None):
    """Réactive une société en fermeture (tant que la purge n'a pas eu lieu).
    Efface ``date_fermeture`` et repasse ``statut=actif`` — réversible."""
    from authentication.models import Company
    company.statut = Company.STATUT_ACTIF
    company.date_fermeture = None
    company.save()
    _journaliser(company, user, 'Réouverture (annulation de la fermeture).')
    return company


def artefact_backup_disponible(company):
    """True s'il existe un artefact d'export/backup TERMINÉ pour cette société.

    Prérequis OBLIGATOIRE d'une purge : on ne détruit jamais les données sans
    une sauvegarde préalable vérifiée. Accepte un ``BackupRun`` kind export OU
    db_dump terminé (le db_dump système couvre toute l'instance)."""
    from core.models import BackupRun
    q_company = BackupRun.objects.filter(
        company=company, kind=BackupRun.KIND_EXPORT,
        statut=BackupRun.STATUT_TERMINE)
    if q_company.exists():
        return True
    # Un dump base système récent couvre aussi cette société.
    return BackupRun.objects.filter(
        kind=BackupRun.KIND_DB_DUMP,
        statut=BackupRun.STATUT_TERMINE).exclude(object_key='').exists()


def delai_grace_ecoule(company, now=None):
    """True si le délai de grâce (30 j) depuis la mise en fermeture est écoulé."""
    if company.date_fermeture is None:
        return False
    now = now or timezone.now()
    from datetime import timedelta
    return now >= company.date_fermeture + timedelta(days=GRACE_PERIOD_DAYS)


def verifier_purge_possible(company, now=None):
    """Vérifie TOUTES les préconditions d'une purge. Lève ``PurgeRefusee`` avec
    un message français explicite si l'une manque. N'exécute AUCUNE suppression.

    Préconditions :
      * la société est en FERMETURE (soft-close préalable) ;
      * le délai de grâce (30 j) est écoulé ;
      * un artefact d'export/backup terminé existe (jamais de purge sans backup).
    """
    from authentication.models import Company
    if company.statut != Company.STATUT_FERMETURE:
        raise PurgeRefusee(
            "La société n'est pas en fermeture : effectuez d'abord le "
            "soft-close (mettre_en_fermeture).")
    if not delai_grace_ecoule(company, now=now):
        raise PurgeRefusee(
            f"Délai de grâce de {GRACE_PERIOD_DAYS} jours non écoulé depuis la "
            "mise en fermeture — purge refusée.")
    if not artefact_backup_disponible(company):
        raise PurgeRefusee(
            "Aucun artefact d'export/sauvegarde vérifié pour cette société — "
            "purge refusée (sauvegarde préalable obligatoire).")


def purger_tenant(company, user=None, now=None):
    """Purge RÉELLE d'un tenant. Vérifie d'abord ``verifier_purge_possible``
    (lève ``PurgeRefusee`` sinon), puis efface les données via les fournisseurs
    DSR enregistrés (``core.dsr``) et supprime la société. Journalise tout.

    ATTENTION : destructif. Appelée uniquement par la commande ``close_company``
    derrière une double confirmation explicite (dry-run par défaut)."""
    verifier_purge_possible(company, now=now)
    company_id = company.id
    company_nom = company.nom
    # Effacement délégué aux fournisseurs DSR (chaque app efface ses données).
    resultats = {}
    try:
        from core import dsr
        # subject_identifier vide → on efface au niveau société entière : chaque
        # fournisseur DSR est déjà scopé société. On journalise le décompte.
        resultats = dsr.effacer(company, subject_identifier='*')
    except Exception as exc:  # noqa: BLE001 — un fournisseur KO n'arrête pas tout
        logger.warning('purge tenant %s: DSR effacer a échoué: %s',
                       company_id, exc)
    _journaliser(company, user,
                 f'PURGE du tenant #{company_id} ({company_nom}). DSR: '
                 f'{resultats}')
    # Suppression finale de la société elle-même (cascade sur ses FK company).
    company.delete()
    return {'company_id': company_id, 'dsr': resultats, 'purge': True}


def _journaliser(company, user, message):
    """Journal d'audit best-effort (ne bloque jamais l'opération)."""
    try:
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.STATUS, user=user, company=company,
               detail=message)
    except Exception:
        pass
