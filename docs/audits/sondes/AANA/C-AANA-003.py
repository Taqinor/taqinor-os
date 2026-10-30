"""Sonde AANA50 (acceptation live du groupe AANA). Rejoue C-AANA-003 (audit analyse du 05/10, §6) : row_to_json(u) / p.* exposaient hash, TOTP, prix_achat.
Le constat vit dans le service FastAPI (backend/fastapi_ia) : scripts/sonde.py ne cible que le conteneur django_core,
la preuve est donc rejouée en lecture seule dans le conteneur erp-agentique-fastapi_ia-1 et collée en trace.
"""
SONDE = {
    'constat': 'C-AANA-003',
    'sha': '5908d43bb',
    'attendu': "défaut absent : row_to_json(u) et SELECT p.* FROM stock_produit REJETÉES ; _references_forbidden_column('SELECT p.* FROM stock_produit p …') = True",
}


def sonde(ctx):
    return ("STATIQUE — constat côté FastAPI, hors portée du lanceur (conteneur django_core) ; rejoué en lecture seule "
            "dans erp-agentique-fastapi_ia-1 le 2026-10-30 : docs/audits/acceptation/AANA/traces/2026-10-30/fastapi-garde-sql.txt")
