# NTPLT33 — index PARTIEL des lignes de ``ticket`` pas encore indexées en
# plein-texte (``search_vector`` NULL) : le repli icontains de la recherche
# globale (``… OR (search_vector IS NULL AND …)``) passe par lui au lieu d'un
# balayage de table ; vide une fois ``rebuild_search_index`` passé. Posé
# CONCURREMMENT (``atomic = False`` + lock_timeout borné, YOPSB6). Réversible.
from django.db.models import Q

from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    'sav',
    [('sav', '0076_ntplt33_equipement_fts_null')],
    'ticket',
    ['id'],
    'sav_ticket_fts_null',
    condition=Q(search_vector__isnull=True),
)
