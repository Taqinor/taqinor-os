# ACAL118 — index (société, archive_le) du sélecteur ``calepinages_actifs``,
# posé CONCURREMMENT (``atomic = False`` + lock_timeout borné, YOPSB6) : aucun
# verrou d'écriture bloquant sur la table vivante. Réversible (DROP INDEX).
from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    'calepinage',
    [('calepinage', '0022_acal118_archive_le')],
    'calepinage',
    ['company', 'archive_le'],
    'cal_cal_co_archive_idx',
)
