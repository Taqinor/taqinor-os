"""Sonde C-AGQ-037 — phase 2 de l'audit du devis agricole (24/10/2026). Vérification STATIQUE exécutable.

Observé (rejeu live du 24/10/2026, devis DEV-202610-0003) : le générateur pose une ligne au
`prix_vente` du produit, même quand le produit porte un barème par panneau (`prix_fixe_ht` +
`prix_par_panneau_ht`) que le serveur applique à l'écriture (`catalogue.py::prix_forfait_ht`) :
écran 31 900 MAD, devis écrit 37 300 MAD. Attendu : l'écran pose le prix du barème.

Exécution : `python docs/audits/sondes/AGQ/C-AGQ-037.py` depuis la racine du dépôt ; code 1 = constat reproduit.
"""
import pathlib
import sys

solar = pathlib.Path("frontend/src/features/ventes/solar.js").read_text(encoding="utf-8")
front = [p for p in pathlib.Path("frontend/src/features/ventes").rglob("*.js") if ".test." not in p.name]
bareme_lu = any("prix_par_panneau_ht" in p.read_text(encoding="utf-8") for p in front)
prix_vente_seul = "ttcExactFromHt(p.prix_vente, taux)" in solar
print("ligneProduitCatalogue au prix_vente :", prix_vente_seul)
print("barème par panneau lu par le générateur :", bareme_lu)
sys.exit(1 if (prix_vente_seul and not bareme_lu) else 0)
