"""Sonde AANA50 (acceptation live du groupe AANA). Rejoue C-AANA-033 (audit analyse du 05/10, §6) : claim `permissions` mort lu par FastAPI (prix_achat_voir jamais honoré).
Le constat vit dans le service FastAPI (backend/fastapi_ia) : scripts/sonde.py ne cible que le conteneur django_core,
la preuve est donc rejouée en lecture seule dans le conteneur erp-agentique-fastapi_ia-1 et collée en trace.
"""
SONDE = {
    'constat': 'C-AANA-033',
    'sha': '5908d43bb',
    'attendu': "défaut absent : permissions lues à /api/django/auth/me/ depuis fastapi_ia (Host autorisé, AANA52) — demo_admin non superutilisateur ⇒ prix_achat_voir = True ; jeton invalide ⇒ [] (fail-closed)",
}


def sonde(ctx):
    return ("STATIQUE — constat côté FastAPI, hors portée du lanceur (conteneur django_core) ; rejoué en lecture seule "
            "dans erp-agentique-fastapi_ia-1 le 2026-10-30 : docs/audits/acceptation/AANA/traces/2026-10-30/fastapi-garde-sql.txt")
