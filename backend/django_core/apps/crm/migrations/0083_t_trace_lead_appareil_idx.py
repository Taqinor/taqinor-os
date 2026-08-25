"""T-TRACE — index ``(company, appareil_id)`` sur la table PEUPLÉE ``crm_lead``.

Posé EN CONCURRENT (YOPSB6, ``core.migrations_utils``) parce que ``crm_lead``
est une table à forte croissance déjà peuplée en production : un ``AddIndex``
nu la verrouillerait en ÉCRITURE pendant toute la construction de l'index —
donc pendant que le webhook du site continue d'y insérer des leads.

L'index sert la question posée à CHAQUE création de lead : « quels AUTRES
leads de cette société partagent cet appareil ? » (alerte rouge « possible
doublon/concurrent »). Sans lui, c'est un scan complet de la table leads sur
le chemin critique du webhook public.
"""
from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    app_label='crm',
    dependencies=[('crm', '0082_t_trace_visite_externe')],
    model_name='lead',
    fields=['company', 'appareil_id'],
    index_name='crm_lead_appareil_idx',
)
