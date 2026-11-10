# NTPLT32 — index GIN du plein-texte de ``facture``, posé CONCURREMMENT
# (``atomic = False`` + lock_timeout borné, YOPSB6) : aucun verrou d'écriture
# bloquant sur la table vivante. Réversible.
from django.contrib.postgres.indexes import GinIndex

from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    'facturation',
    [('facturation', '0030_ntplt32_facture_search_vector')],
    'facture',
    ['search_vector'],
    'facturation_fac_fts_gin',
    index_class=GinIndex,
)
