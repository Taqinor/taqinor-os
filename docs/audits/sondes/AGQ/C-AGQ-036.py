"""Sonde C-AGQ-036 — audit L3 du devis agricole (23/10/2026).

Observé → attendu : prod (lecture seule) : 11 OSP à 0 MAD, 8 génériques sans kW, 0 fiche variateur, INST-PMP sans barème, 0 structure_sol

Exécution : la sonde partagée `_catalogue_prod.py` (même dossier) tourne dans le conteneur
django en transaction ANNULÉE (`docker cp` puis `python manage.py shell < fichier`)
pour les sondes `_bout_en_bout` / `_cas_limites` / `_catalogue_prod` (prod : lecture
seule, SSH) ; les sondes `_noyau_*` / `_economie` tournent sur l'hôte
(`cd backend/django_core && python <fichier>`, noyau pur sans Django).
"""
import pathlib

exec(compile((pathlib.Path(__file__).parent / "_catalogue_prod.py").read_text(encoding="utf-8"),
             "_catalogue_prod.py", "exec"))
