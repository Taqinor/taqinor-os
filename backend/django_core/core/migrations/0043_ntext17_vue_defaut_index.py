# NTEXT17 — index de résolution de la vue par défaut, posé SANS verrou
# d'écriture bloquant (YOPSB6 : CREATE INDEX CONCURRENTLY + lock_timeout).

from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    app_label='core',
    dependencies=[('core', '0042_ntext17_vue_defaut')],
    model_name='vuepersonnalisee',
    fields=['company', 'cible', 'est_defaut'],
    index_name='core_vueperso_defaut_idx',
)
