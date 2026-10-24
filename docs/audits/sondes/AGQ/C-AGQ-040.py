"""Sonde C-AGQ-040 — phase 2 de l'audit du devis agricole (24/10/2026). Vérification STATIQUE exécutable.

Observé (rejeu live du 24/10/2026) : pompe existante sans kW de plaque, « variateur non
choisi », et « Auto-remplir » pose un kit SANS variateur (20 300 MAD) ; l'aperçu ne sert pas les
rôles du kit minimum manquants que le devis automatique refuse. Attendu : refus nommé.

Exécution : `python docs/audits/sondes/AGQ/C-AGQ-040.py` depuis la racine du dépôt ; code 1 = constat reproduit.
"""
import pathlib
import sys

vue = pathlib.Path("backend/django_core/apps/ventes/etude_pompage_view.py").read_text(encoding="utf-8")
hook = pathlib.Path("frontend/src/pages/ventes/generator/hooks/useCompositionEcran.js").read_text(encoding="utf-8")
servi = "roles_minimum_manquants" in vue
refus = "refusAutoRemplirPompage" in hook
print("aperçu sert roles_minimum_manquants :", servi)
print("Auto-remplir refuse un kit incomplet :", refus)
sys.exit(1 if not (servi and refus) else 0)
