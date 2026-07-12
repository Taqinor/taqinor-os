"""YOPSB10 — Registre de rétention partagé + sweep unifié.

Généralise la rétention réinventée par app (FG26 audit, XRH24 candidats,
XKB32 conversations) : un registre EN MÉMOIRE, en fondation pure (aucune
importation d'app domaine), que chaque app peuple dans son ``apps.py
ready()`` avec sa PROPRE logique de purge.

Conception
----------

* ``register_retention_policy(name, sweep_callable)`` — enregistre une
  politique nommée. ``sweep_callable`` reçoit ``now`` (``datetime``) et
  ``apply_`` (bool) et renvoie un ``int`` (compte d'éléments
  supprimés/anonymisés). Chaque app appelle CETTE fonction dans son
  ``ready()`` avec SA propre fonction de purge (définie dans son
  ``services.py``, jamais importée par ``core``) — ``core`` ne connaît que
  le NOM et le CALLABLE, jamais la logique métier.
* ``run_all_policies(now=None, apply_=False)`` — exécute TOUTES les
  politiques enregistrées, journalise chaque exécution en
  ``core.RetentionRun`` (company=None — balayage système, transverse à
  toutes les sociétés ; chaque politique reste responsable de scoper ELLE-
  MÊME par société en interne). DRY-RUN par défaut (``apply_=False``) : les
  politiques reçoivent ``apply_=False`` et NE DOIVENT rien supprimer (c'est
  la responsabilité de CHAQUE politique de respecter ce contrat) ;
  ``core`` journalise le compte renvoyé quel que soit le mode.

``core`` reste fondation : ce module n'importe AUCUNE app domaine (contrat
import-linter ``core-foundation-is-a-base-layer``). Le registre vit en
mémoire du process (pas de persistance de la LISTE des politiques — seule
l'HISTORIQUE d'exécution est persisté via ``RetentionRun``).
"""
from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

# Registre en mémoire : {name: sweep_callable}. Réinitialisé à chaque
# démarrage process — chaque app le repeuple dans son ``ready()``.
_REGISTRY: dict = {}


def register_retention_policy(name, sweep_callable):
    """Enregistre une politique de rétention nommée.

    ``sweep_callable(now, apply_)`` doit renvoyer un ``int`` (compte
    d'éléments traités). Ré-enregistrer le même ``name`` REMPLACE l'entrée
    (idempotent au rechargement de l'app registry — utile en test)."""
    _REGISTRY[name] = sweep_callable


def unregister_retention_policy(name):
    """Retire une politique (surtout utile en test pour isoler le registre)."""
    _REGISTRY.pop(name, None)


def list_retention_policies():
    """Noms des politiques actuellement enregistrées (triés)."""
    return sorted(_REGISTRY.keys())


def clear_registry():
    """Vide le registre (test uniquement — jamais appelé en usage normal)."""
    _REGISTRY.clear()


def run_all_policies(now=None, apply_=False):
    """Exécute TOUTES les politiques enregistrées et journalise chacune en
    ``core.RetentionRun``. DRY-RUN par défaut : ``apply_=False`` est transmis
    tel quel à chaque politique (c'est à ELLE de ne rien supprimer). Renvoie
    la liste des résultats ``[{name, count, statut, erreur}]``."""
    from .models import RetentionRun

    now = now or timezone.now()
    results = []
    for name in sorted(_REGISTRY.keys()):
        sweep = _REGISTRY[name]
        try:
            count = sweep(now, apply_)
            statut = RetentionRun.STATUT_OK
            erreur = ''
        except Exception as exc:  # noqa: BLE001 — une politique en échec
            # n'arrête jamais les autres ; journalisée en échec.
            logger.exception('run_retention: politique %r a échoué', name)
            count = 0
            statut = RetentionRun.STATUT_ECHEC
            erreur = str(exc)

        RetentionRun.objects.create(
            policy_name=name, dry_run=not apply_, count=count,
            statut=statut, erreur=erreur, executed_at=now,
        )
        results.append({
            'name': name, 'count': count, 'statut': statut, 'erreur': erreur,
        })
    return results


# ---------------------------------------------------------------------------
# NTPLT39 — Purge par DROP PARTITION pilotée par la rétention.
#
# Sur une table PARTITIONNÉE mensuellement (``core.partitioning``), purger par
# ``DETACH PARTITION`` + ``DROP TABLE`` est INSTANTANÉ et sans bloat, là où un
# ``DELETE`` par lots réécrit des millions de lignes. Cette politique se
# branche dans le registre YOPSB10 comme n'importe quelle autre : elle reçoit
# ``apply_`` du sweep (DRY-RUN par défaut) et ne supprime QUE si ``apply_`` est
# vrai — mêmes flags d'activation (``RETENTION_AUTO_APPLY``).
# ---------------------------------------------------------------------------


def _partition_year_month(partition: str, table: str):
    """Extrait ``(year, month)`` du suffixe ``_YYYY_MM`` d'une partition.

    Renvoie ``None`` si le nom ne suit pas la convention (partition par défaut,
    nom hors-format) — une telle partition n'est JAMAIS purgée.
    """
    suffix = partition[len(table) + 1:] if partition.startswith(
        table + '_') else ''
    parts = suffix.split('_')
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def drop_partitions_before(table: str, keep_months: int, now=None,
                           apply_: bool = False) -> int:
    """Purge les partitions mensuelles de ``table`` plus vieilles que la
    fenêtre ``keep_months``.

    DRY-RUN par défaut (``apply_=False``) : compte les partitions ÉLIGIBLES
    sans rien détacher/supprimer. Avec ``apply_=True`` : ``DETACH`` puis
    ``DROP TABLE`` chaque partition éligible (instantané). Renvoie le nombre de
    partitions concernées (comptées en dry-run, réellement purgées sinon).
    """
    from django.db import connection
    from django.utils import timezone
    from . import partitioning

    now = now or timezone.now()
    # Seuil = premier jour du mois, reculé de keep_months.
    year, month = now.year, now.month
    for _ in range(keep_months):
        if month == 1:
            year, month = year - 1, 12
        else:
            month -= 1
    threshold = (year, month)

    eligible = []
    for part in partitioning.list_partitions(table):
        ym = _partition_year_month(part, table)
        if ym is None:
            continue
        if ym < threshold:
            eligible.append(part)

    if apply_:
        with connection.cursor() as cur:
            for part in eligible:
                cur.execute(
                    f'ALTER TABLE "{table}" DETACH PARTITION "{part}";')
                cur.execute(f'DROP TABLE IF EXISTS "{part}";')
    return len(eligible)


def register_partition_retention(name: str, table: str, keep_months: int):
    """Enregistre une politique de rétention par DROP PARTITION pour ``table``.

    À appeler dans le ``ready()`` de l'app propriétaire de la table. La
    politique reçoit ``apply_`` du sweep (DRY-RUN par défaut) et purge les
    partitions plus vieilles que ``keep_months`` mois.
    """
    def sweep(now, apply_):
        return drop_partitions_before(
            table, keep_months, now=now, apply_=apply_)

    register_retention_policy(name, sweep)
