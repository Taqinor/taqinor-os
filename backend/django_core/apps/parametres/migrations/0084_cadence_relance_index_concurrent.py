"""MRY4 — index ``(company, cadence, actif)`` sur ``parametres_cadencerelanceetape``.

Posé EN CONCURRENT (YOPSB6, ``core.migrations_utils``) et non dans 0081 : un
``AddIndex`` nu prend un verrou d'ÉCRITURE sur la table pendant toute la
construction. Le gabarit est petit, mais la règle ne dépend pas de la taille
du jour J — elle dépend de ce que la table devient.

L'index sert la lecture la plus fréquente du moteur : ``cadence_pour(company,
cadence)``, appelée à CHAQUE initialisation de plan de relance, donc à chaque
arrivée de lead et à chaque devis envoyé.
"""
from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    app_label='parametres',
    dependencies=[('parametres', '0083_messagetemplate_cles_relance')],
    model_name='cadencerelanceetape',
    fields=['company', 'cadence', 'actif'],
    index_name='param_cad_co_cad_act_idx',
)
