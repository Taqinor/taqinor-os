# ACRM32 — index (société, whatsapp_normalise) de la dédup par WhatsApp,
# posé CONCURREMMENT (``atomic = False`` + lock_timeout borné, YOPSB6) : aucun
# verrou d'écriture bloquant sur la table vivante des leads. Réversible.
from core.migrations_utils import concurrent_index_migration

Migration = concurrent_index_migration(
    'crm',
    [('crm', '0131_acrm32_lead_whatsapp_normalise')],
    'lead',
    ['company', 'whatsapp_normalise'],
    'crm_lead_wa_norm_idx',
)
