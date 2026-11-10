# NTPLT32 — index GIN du plein-texte de ``equipement``, posé CONCURREMMENT
# (``atomic = False`` + lock_timeout borné, YOPSB6) : aucun verrou d'écriture
# bloquant sur la table vivante. Réversible.
from django.contrib.postgres.indexes import GinIndex

from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    'sav',
    [('sav', '0073_ntplt32_search_vector')],
    'equipement',
    ['search_vector'],
    'sav_equipement_fts_gin',
    index_class=GinIndex,
)
