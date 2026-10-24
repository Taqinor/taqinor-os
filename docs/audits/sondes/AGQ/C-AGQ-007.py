"""Sonde C-AGQ-007 — audit L3 du devis agricole (23/10/2026).

Observé → attendu : kw_min 9,27 kW pour Q 17 / H 70 (η groupe sur la plaque) ; OSP 30/8 7,5 kW livre 24 m³/h → rendements des fiches (D-AGQ-8)

Exécution : la sonde partagée `_noyau_balayage.py` (même dossier) tourne dans le conteneur
django en transaction ANNULÉE (`docker cp` puis `python manage.py shell < fichier`)
pour les sondes `_bout_en_bout` / `_cas_limites` / `_catalogue_prod` (prod : lecture
seule, SSH) ; les sondes `_noyau_*` / `_economie` tournent sur l'hôte
(`cd backend/django_core && python <fichier>`, noyau pur sans Django).
"""
import pathlib

exec(compile((pathlib.Path(__file__).parent / "_noyau_balayage.py").read_text(encoding="utf-8"),
             "_noyau_balayage.py", "exec"))
