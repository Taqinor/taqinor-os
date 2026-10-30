"""Sonde AANA50 (acceptation live du groupe AANA). Rejoue C-AANA-002 (audit analyse du 05/10, §6) : aucune liste blanche de fonctions ; rôle DB propriétaire en repli.
Le constat vit dans le service FastAPI (backend/fastapi_ia) : scripts/sonde.py ne cible que le conteneur django_core,
la preuve est donc rejouée en lecture seule dans le conteneur erp-agentique-fastapi_ia-1 et collée en trace.
"""
SONDE = {
    'constat': 'C-AANA-002',
    'sha': '5908d43bb',
    'attendu': "défaut absent : query_to_xml / pg_read_file / lo_export / set_config / pg_sleep REJETÉES ; DJANGO_DEBUG=False sans SQL_AGENT_DB_USER ⇒ agent désactivé (raison nommant la variable), repli seulement en développement",
}


def sonde(ctx):
    return ("STATIQUE — constat côté FastAPI, hors portée du lanceur (conteneur django_core) ; rejoué en lecture seule "
            "dans erp-agentique-fastapi_ia-1 le 2026-10-30 : docs/audits/acceptation/AANA/traces/2026-10-30/fastapi-garde-sql.txt")
