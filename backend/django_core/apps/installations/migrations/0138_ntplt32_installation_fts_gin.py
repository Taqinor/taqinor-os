# NTPLT32 — index GIN du plein-texte de ``installation``, posé CONCURREMMENT
# (``atomic = False`` + lock_timeout borné, YOPSB6) : aucun verrou d'écriture
# bloquant sur la table vivante. Réversible.
from django.contrib.postgres.indexes import GinIndex

from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    'installations',
    [('installations', '0137_ntplt32_installation_search_vector')],
    'installation',
    ['search_vector'],
    'installations_inst_fts_gin',
    index_class=GinIndex,
)
