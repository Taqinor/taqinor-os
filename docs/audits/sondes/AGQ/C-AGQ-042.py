"""Sonde C-AGQ-042 — phase 2 de l'audit du devis agricole (24/10/2026). Vérification STATIQUE exécutable.

Observé (rejeu live du 24/10/2026, /proposition d'un devis de pompage) : « kWh / an » en
tête, carte « Sans batterie », badge « Loi 82-21 · Autoconsommation BT », demandes « puissance
(kWc) / option batterie », « étudié sur votre facture ». Attendu : une page qui parle d'eau.

Exécution : `python docs/audits/sondes/AGQ/C-AGQ-042.py` depuis la racine du dépôt ; code 1 = constat reproduit.
"""
import pathlib
import sys

page = pathlib.Path("apps/web/src/pages/proposition/[...token].astro").read_text(encoding="utf-8")
page = page.replace("\r\n", "\n")
badge_toujours = "  'loi8221' as const,\n" in page
kwh_toujours = ('{prodKwh ? (\n                <li class="fig" dir="ltr" '
                'data-figure="production_annuelle_kwh">') in page
revision_eau = 'data-revision-kind="eau"' in page
print("badge Autoconsommation BT pour tout devis :", badge_toujours)
print("kWh / an en tête pour tout devis :", kwh_toujours)
print("demande « volume d'eau ou pompe » :", revision_eau)
sys.exit(1 if (badge_toujours or kwh_toujours or not revision_eau) else 0)
