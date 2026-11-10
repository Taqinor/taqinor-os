# NTPLT32 — index GIN du plein-texte de ``devis``, posé CONCURREMMENT
# (``atomic = False`` + lock_timeout borné, YOPSB6) : aucun verrou d'écriture
# bloquant sur la table vivante. Réversible.
from django.contrib.postgres.indexes import GinIndex

from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    'ventes',
    [('ventes', '0155_ntplt32_devis_search_vector')],
    'devis',
    ['search_vector'],
    'ventes_devis_fts_gin',
    index_class=GinIndex,
)
