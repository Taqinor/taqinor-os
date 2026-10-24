"""Sonde C-AGQ-015 — audit L3 du devis agricole (23/10/2026).

Observé → attendu : carte économie avec lignes vides : retour 0 ans publiable → lignes transmises, investissement ≤ 0 non publiable

Exécution : la sonde partagée `_economie.py` (même dossier) tourne dans le conteneur
django en transaction ANNULÉE (`docker cp` puis `python manage.py shell < fichier`)
pour les sondes `_bout_en_bout` / `_cas_limites` / `_catalogue_prod` (prod : lecture
seule, SSH) ; les sondes `_noyau_*` / `_economie` tournent sur l'hôte
(`cd backend/django_core && python <fichier>`, noyau pur sans Django).
"""
import pathlib

exec(compile((pathlib.Path(__file__).parent / "_economie.py").read_text(encoding="utf-8"),
             "_economie.py", "exec"))
