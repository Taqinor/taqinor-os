"""Sonde C-AGQ-009 — audit L3 du devis agricole (23/10/2026).

Observé → attendu : economie-pompage : statut omis « jours d'irrigation par semaine non déclarés » sur un lead butane complet → colonne lead (D-AGQ-6)

Exécution : la sonde partagée `_bout_en_bout.py` (même dossier) tourne dans le conteneur
django en transaction ANNULÉE (`docker cp` puis `python manage.py shell < fichier`)
pour les sondes `_bout_en_bout` / `_cas_limites` / `_catalogue_prod` (prod : lecture
seule, SSH) ; les sondes `_noyau_*` / `_economie` tournent sur l'hôte
(`cd backend/django_core && python <fichier>`, noyau pur sans Django).
"""
import pathlib

exec(compile((pathlib.Path(__file__).parent / "_bout_en_bout.py").read_text(encoding="utf-8"),
             "_bout_en_bout.py", "exec"))
