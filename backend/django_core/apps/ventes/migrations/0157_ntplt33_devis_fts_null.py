# NTPLT33 — index PARTIEL des lignes de ``devis`` pas encore indexées en
# plein-texte (``search_vector`` NULL) : le repli icontains de la recherche
# globale (``… OR (search_vector IS NULL AND …)``) passe par lui au lieu d'un
# balayage de table ; vide une fois ``rebuild_search_index`` passé. Posé
# CONCURREMMENT (``atomic = False`` + lock_timeout borné, YOPSB6). Réversible.
from django.db.models import Q

from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    'ventes',
    [('ventes', '0156_ntplt32_devis_fts_gin')],
    'devis',
    ['id'],
    'ventes_devis_fts_null',
    condition=Q(search_vector__isnull=True),
)
