# NTPLT32 — index GIN du plein-texte de ``client``, posé CONCURREMMENT
# (``atomic = False`` + lock_timeout borné, YOPSB6) : aucun verrou d'écriture
# bloquant sur la table vivante. Réversible.
from django.contrib.postgres.indexes import GinIndex

from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    'crm',
    [('crm', '0159_ntplt32_lead_fts_gin')],
    'client',
    ['search_vector'],
    'crm_client_fts_gin',
    index_class=GinIndex,
)
