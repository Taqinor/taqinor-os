"""NTDOC15 — index ``(company, source_type, source_id)`` sur les salles.

Posé EN CONCURRENT (YOPSB6, ``core.migrations_utils``) et non dans 0003 : cet
index sert le LIEN RETOUR affiché sur la fiche d'un lead / chantier / contrat
(« quelles salles de données viennent de cet objet ? »), donc une requête
appelée à chaque ouverture de fiche — et un ``AddIndex`` nu verrouillerait la
table en écriture pendant toute sa construction.
"""
from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    app_label='datarooms',
    dependencies=[('datarooms', '0003_ntdoc15_salle_source')],
    model_name='sallededonnees',
    fields=['company', 'source_type', 'source_id'],
    index_name='dataroom_co_source_idx',
)
