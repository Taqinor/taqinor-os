"""NTPRT13 — index ``(client)`` sur ``ged_aclged``.

Posé EN CONCURRENT (YOPSB6, ``core.migrations_utils``) et non dans 0049 :
``ged_aclged`` est une table vivante (chaque partage/override écrit). L'index
sert le sélecteur portail « mes documents » (toutes les ACL d'un client).
"""
from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    app_label='ged',
    dependencies=[('ged', '0049_ntprt13_aclged_client_portail')],
    model_name='aclged',
    fields=['client'],
    index_name='ged_acl_client_idx',
)
