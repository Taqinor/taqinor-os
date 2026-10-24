"""Sonde C-AGQ-041 — phase 2 de l'audit du devis agricole (24/10/2026). Vérification STATIQUE exécutable.

Observé (rejeu live du 24/10/2026) : pompe existante sans kW de plaque, résumé « Champ
4,95 kWc (9 panneaux) », carte « Recommandée » 5,5 kWc · 10 panneaux : le résumé vient de
`pompe_existante(..., mois_critique=passe 1)`, les tailles de `proposer_tailles` sans ce mois.
Attendu : le résumé lit le champ de la taille retenue.

Exécution : `python docs/audits/sondes/AGQ/C-AGQ-041.py` depuis la racine du dépôt ; code 1 = constat reproduit.
"""
import pathlib
import sys

src = pathlib.Path("backend/django_core/apps/ventes/domain/pompage.py").read_text(encoding="utf-8")
deux_sources = "champ_complet = existante['champ']" in src and "mois_critique=mois_critique" in src
print("résumé et tailles calculés séparément :", deux_sources)
sys.exit(1 if deux_sources else 0)
