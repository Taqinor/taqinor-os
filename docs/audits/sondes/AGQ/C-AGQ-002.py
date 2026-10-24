"""Sonde C-AGQ-002 — audit L3 du devis agricole (23/10/2026).

Observé → attendu : lead L1b : mois_critique 4, couverture [102,96,94,94,94,94,80], contrôle « conforme » → mois critique = pire mois réel

Exécution : la sonde partagée `_cas_limites.py` (même dossier) tourne dans le conteneur
django en transaction ANNULÉE (`docker cp` puis `python manage.py shell < fichier`)
pour les sondes `_bout_en_bout` / `_cas_limites` / `_catalogue_prod` (prod : lecture
seule, SSH) ; les sondes `_noyau_*` / `_economie` tournent sur l'hôte
(`cd backend/django_core && python <fichier>`, noyau pur sans Django).
"""
import pathlib

exec(compile((pathlib.Path(__file__).parent / "_cas_limites.py").read_text(encoding="utf-8"),
             "_cas_limites.py", "exec"))
