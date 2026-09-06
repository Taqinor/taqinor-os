"""MRY5 — index ``(company, lead, cadence, statut)`` sur ``crm_relanceetape``.

Posé EN CONCURRENT (YOPSB6, ``core.migrations_utils``) et non dans 0090 :
``crm_relanceetape`` est une table VIVANTE — le moteur de relances y écrit à
chaque touche traitée et à chaque cadence initialisée. Un ``AddIndex`` nu la
verrouillerait en ÉCRITURE pendant toute la construction, donc pendant que le
webhook du site continue de créer des leads et leurs cadences.

L'index sert les deux requêtes les plus fréquentes du moteur : la FRISE de la
fiche lead (toutes les touches d'un lead) et l'idempotence PAR CADENCE de
``initialiser_plan_relance`` (« ce lead a-t-il déjà cette cadence ? »),
appelée à CHAQUE arrivée de lead.
"""
from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    app_label='crm',
    dependencies=[('crm', '0091_leadactivity_kind_whatsapp')],
    model_name='relanceetape',
    fields=['company', 'lead', 'cadence', 'statut'],
    index_name='crm_relance_lead_cad_idx',
)
