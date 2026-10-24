"""Sonde C-AGQ-045 — phase 3 de l'audit du devis agricole (rejeu live du 24/10/2026). Vérification STATIQUE exécutable.

Observé (devis automatique, forage 25 m³/h, besoin 250 m³/j) : la production heure par heure couvre le besoin
(champ 3,2× la pompe, 250 m³ livrés chaque mois, contrôle « conforme »), mais l'alerte `plafond_forage` du noyau
reste et la page 2 imprime « le besoin du mois le plus défavorable n'est pas entièrement couvert ».
Attendu : l'alerte « ne sera pas couvert » n'existe que si la couverture mois par mois est insuffisante.

Exécution : `python docs/audits/sondes/AGQ/C-AGQ-045.py` depuis la racine du dépôt ; code 1 = constat reproduit.
"""
import pathlib
import sys

src = pathlib.Path("backend/django_core/core/pompage/conception.py").read_text(encoding="utf-8")
src = src.replace("\r\n", "\n")
filtre = ('if production_m3_jour_mois and controle["statut"] in (\n'
          '            "conforme", "surdimensionnement"):\n'
          '        alertes = [a for a in alertes if a["code"] != "plafond_forage"]')
print("alerte « non couvert » retirée quand la production couvre :", filtre in src)
sys.exit(0 if filtre in src else 1)
