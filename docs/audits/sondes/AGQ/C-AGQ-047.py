"""Sonde C-AGQ-047 — phase 3 de l'audit du devis agricole (rejeu live du 24/10/2026). Vérification STATIQUE exécutable.

Observé (lead au débit du forage relevé par le foreur, puis à l'essai de pompage) : le PDF et la page
/proposition impriment « 36 m³/h — mesuré par TAQINOR … le 24/10/2026 » pour un relevé du FOREUR (la société
n'a rien mesuré), et un débit relevé à l'ESSAI reste « déclaré par vous » et « à confirmer par la visite ».
Attendu : « relevé par votre foreur (saisi le …) » / « relevé à l'essai de pompage (saisi le …) », l'essai compté
comme une mesure ; seule la visite est « mesuré par » la société.

Exécution : `python docs/audits/sondes/AGQ/C-AGQ-047.py` depuis la racine du dépôt ; code 1 = constat reproduit.
"""
import pathlib
import sys

base = pathlib.Path("backend/django_core/apps/ventes/quote_engine/agricole")
mentions = (base / "mentions.py").read_text(encoding="utf-8")
synthese = (base / "synthese.py").read_text(encoding="utf-8")
web = pathlib.Path("apps/web/src/lib/proposition.ts").read_text(encoding="utf-8")
foreur_pdf = '"mesure_foreur": {"fr": "relevé par votre foreur (saisi le {date})"' in mentions
essai_mesure = '"essai"' in synthese.split("DETAILS_MESURES = ", 1)[1].split("\n", 1)[0]
foreur_web = "foreur: 'mesure_foreur'" in web
print("PDF : relevé du foreur dit tel quel :", foreur_pdf)
print("essai de pompage compté comme une mesure :", essai_mesure)
print("page : relevé du foreur dit tel quel :", foreur_web)
sys.exit(0 if (foreur_pdf and essai_mesure and foreur_web) else 1)
