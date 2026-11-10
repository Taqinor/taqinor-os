# NTPLT32 — index GIN du plein-texte de ``lead``, posé CONCURREMMENT
# (``atomic = False`` + lock_timeout borné, YOPSB6) : aucun verrou d'écriture
# bloquant sur la table vivante. Réversible.
from django.contrib.postgres.indexes import GinIndex

from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    'crm',
    [('crm', '0158_ntplt32_search_vector')],
    'lead',
    ['search_vector'],
    'crm_lead_fts_gin',
    index_class=GinIndex,
)
