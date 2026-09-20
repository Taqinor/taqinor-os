"""NTPRT7 — index ``(company, via_portail, -timestamp)`` sur ``audit_auditlog``.

Posé EN CONCURRENT (YOPSB6, ``core.migrations_utils``) et non dans 0007 :
``audit_auditlog`` est une table VIVANTE — chaque action métier y écrit. Un
``AddIndex`` nu la verrouillerait en écriture pendant toute la construction.
L'index sert l'onglet « Accès portail » (filtre via_portail + tri temporel).
"""
from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    app_label='audit',
    dependencies=[('audit', '0007_ntprt7_via_portail')],
    model_name='auditlog',
    fields=['company', 'via_portail', '-timestamp'],
    index_name='audit_via_portail_idx',
)
