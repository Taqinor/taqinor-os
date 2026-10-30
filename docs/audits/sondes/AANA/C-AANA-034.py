"""Sonde AANA50 (acceptation live du groupe AANA). Rejoue C-AANA-034 (audit analyse du 05/10, §6) : agent SQL sans borne (longueur, débit, timeout).
Le constat vit dans le service FastAPI (backend/fastapi_ia) : scripts/sonde.py ne cible que le conteneur django_core,
la preuve est donc rejouée en lecture seule dans le conteneur erp-agentique-fastapi_ia-1 et collée en trace.
"""
SONDE = {
    'constat': 'C-AANA-034',
    'sha': '5908d43bb',
    'attendu': "défaut absent : question de 1 Mo refusée (422 string_too_long, max 2 000) ; statement_timeout 15 s sur le moteur de l'agent ; limiteur Redis présent",
}


def sonde(ctx):
    return ("STATIQUE — constat côté FastAPI, hors portée du lanceur (conteneur django_core) ; rejoué en lecture seule "
            "dans erp-agentique-fastapi_ia-1 le 2026-10-30 : docs/audits/acceptation/AANA/traces/2026-10-30/fastapi-garde-sql.txt")
