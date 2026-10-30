"""Sonde AANA50 (acceptation live du groupe AANA). Rejoue C-AANA-015 (audit analyse du 05/10, §6) : FastAPI ignorait la société active.
Le constat vit dans le service FastAPI (backend/fastapi_ia) : scripts/sonde.py ne cible que le conteneur django_core,
la preuve est donc rejouée en lecture seule dans le conteneur erp-agentique-fastapi_ia-1 et collée en trace.
"""
SONDE = {
    'constat': 'C-AANA-015',
    'sha': '5908d43bb',
    'attendu': "défaut absent : require_company_id({company_id:1, active_company_id:2}) = 2",
}


def sonde(ctx):
    return ("STATIQUE — constat côté FastAPI, hors portée du lanceur (conteneur django_core) ; rejoué en lecture seule "
            "dans erp-agentique-fastapi_ia-1 le 2026-10-30 : docs/audits/acceptation/AANA/traces/2026-10-30/fastapi-garde-sql.txt")
