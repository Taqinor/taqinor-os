# NTPLT34 — autocomplétion tolérante aux fautes : index GIN trigramme (pg_trgm)
# sur Produit.nom (la « désignation » du catalogue), posé CONCURREMMENT. Ne
# remplace pas l'index STKCAT27 (sur ``f_unaccent(lower(nom))``, servi par
# ``?search=`` du catalogue) : celui-ci sert l'opérateur ``%`` sur ``nom`` brut.
# La migration ne peut pas échouer (pg_trgm absente : rien n'est posé,
# avertissement journalisé). Aucun état de modèle ne bouge. Réversible.
from core.migrations_utils import trigram_index_migration

Migration = trigram_index_migration(
    'stock',
    [('stock', '0180_ntplt17_produit_lock_version')],
    [('produit', 'nom', 'stock_produit_nom_trgm')],
)
