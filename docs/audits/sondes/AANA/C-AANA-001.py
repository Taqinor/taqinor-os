"""Sonde AANA50 (acceptation live du groupe AANA). Rejoue C-AANA-001 (audit analyse du 05/10, §6) : garde SQL : la société « prouvée » par regex (NOT / IS NOT NULL / arithmétique / projection / littéral passaient).
Le constat vit dans le service FastAPI (backend/fastapi_ia) : scripts/sonde.py ne cible que le conteneur django_core,
la preuve est donc rejouée en lecture seule dans le conteneur erp-agentique-fastapi_ia-1 et collée en trace.
"""
SONDE = {
    'constat': 'C-AANA-001',
    'sha': '5908d43bb',
    'attendu': "défaut absent : les 5 requêtes à prédicat société neutralisé sont RÉÉCRITES (chaque table lue = sous-requête company_id = <jeton>) ; exécutées sur la base locale à 3 sociétés, 0 ligne d'une autre société",
}


def sonde(ctx):
    return ("STATIQUE — constat côté FastAPI, hors portée du lanceur (conteneur django_core) ; rejoué en lecture seule "
            "dans erp-agentique-fastapi_ia-1 le 2026-10-30 : docs/audits/acceptation/AANA/traces/2026-10-30/fastapi-garde-sql.txt")
