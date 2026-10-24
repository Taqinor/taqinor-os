"""Sonde C-AGQ-031 — audit L3 du devis agricole (23/10/2026). Vérification STATIQUE exécutable.

Observé → attendu : `apps/web/src/lib/proposition.ts::nextSteps()` n'a aucun argument de mode et
imprime « 48–72 h » / « 7–14 jours » pour tout devis ; `objectionFaq` ne branche que le C&I.
Attendu (D-AGQ-11) : une frise agricole sans délai chiffré et une FAQ agricole.

Exécution : `python docs/audits/sondes/AGQ/C-AGQ-031.py` depuis la racine du dépôt ; code 1 = constat reproduit.
"""
import pathlib
import re
import sys

src = pathlib.Path("apps/web/src/lib/proposition.ts").read_text(encoding="utf-8")
sans_mode = re.search(r"export function nextSteps\(\s*\)", src) is not None
delais = bool(re.search(r"48\s*[–-]\s*72\s*h", src)) and bool(re.search(r"7\s*[–-]\s*14\s*jours", src))
faq_agricole = "agricole" in (re.search(r"function objectionFaq[\s\S]{0,1500}", src) or re.match(r"", "")).group(0)
print("nextSteps sans argument de mode :", sans_mode)
print("délais chiffrés présents :", delais)
print("FAQ agricole présente :", faq_agricole)
sys.exit(1 if (sans_mode and delais and not faq_agricole) else 0)
