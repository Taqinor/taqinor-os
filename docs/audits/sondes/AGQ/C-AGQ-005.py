"""Sonde C-AGQ-005 — audit L3 du devis agricole (23/10/2026).

Observé → attendu : choisir_variateur(cv=3, mono) → None, 'aucun_variateur' → variateur 2,2 kW retenu, refus si aucun

Exécution : la sonde partagée `_noyau_catalogue.py` (même dossier) tourne dans le conteneur
django en transaction ANNULÉE (`docker cp` puis `python manage.py shell < fichier`)
pour les sondes `_bout_en_bout` / `_cas_limites` / `_catalogue_prod` (prod : lecture
seule, SSH) ; les sondes `_noyau_*` / `_economie` tournent sur l'hôte
(`cd backend/django_core && python <fichier>`, noyau pur sans Django).
"""
import pathlib

exec(compile((pathlib.Path(__file__).parent / "_noyau_catalogue.py").read_text(encoding="utf-8"),
             "_noyau_catalogue.py", "exec"))
