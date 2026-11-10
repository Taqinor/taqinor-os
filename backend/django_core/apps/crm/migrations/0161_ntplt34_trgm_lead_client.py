# NTPLT34 — autocomplétion tolérante aux fautes : index GIN trigramme (pg_trgm)
# sur Lead.nom et Client.nom, posés CONCURREMMENT. La migration ne peut pas
# échouer : sans droit de créer l'extension, rien n'est posé (avertissement
# journalisé) et ``reporting/search/suggest/`` retombe sur icontains. Aucun état
# de modèle ne bouge (index hors ``Meta.indexes``, comme STKCAT27). Réversible.
from core.migrations_utils import trigram_index_migration

Migration = trigram_index_migration(
    'crm',
    [('crm', '0160_ntplt32_client_fts_gin')],
    [('lead', 'nom', 'crm_lead_nom_trgm'),
     ('client', 'nom', 'crm_client_nom_trgm')],
)
