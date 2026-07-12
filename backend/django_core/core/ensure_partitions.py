"""NTPLT36 — Maintenance des partitions à l'avance (logique du beat).

``ensure_all(now, months_ahead)`` parcourt le registre des tables
partitionnées (``core.partitioning``) et garantit que chaque table a ses
partitions du mois courant + des ``months_ahead`` mois suivants. Idempotent :
ré-exécuter ne recrée rien. Une table qui échoue (partition impossible) ne
bloque pas les autres (best-effort, journalisé).

La tâche Celery ``core.ensure_partitions`` (dans ``core/tasks.py``) n'est
qu'une fine enveloppe autour de ``ensure_all`` — toute la logique est ici,
testable sans Celery. ``core`` reste fondation : aucun import d'app métier.
"""
from __future__ import annotations

import logging

from . import partitioning

logger = logging.getLogger(__name__)


def ensure_all(now=None, months_ahead: int = 2) -> dict:
    """Garantit les partitions futures de TOUTES les tables enregistrées.

    Renvoie ``{table: [partitions_garanties]}``. Une table en échec est
    journalisée et renvoie ``[]`` sans arrêter les autres.
    """
    results = {}
    for table in sorted(partitioning.registered_tables().keys()):
        try:
            results[table] = partitioning.ensure_partitions(
                table, months_ahead=months_ahead, now=now)
        except Exception:  # noqa: BLE001 — une table KO ne bloque pas le reste
            logger.exception('ensure_partitions: table %r a échoué', table)
            results[table] = []
    return results
