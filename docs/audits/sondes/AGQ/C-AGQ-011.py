"""Sonde C-AGQ-011 — audit L3 du devis agricole (23/10/2026).

Observé → attendu : note.pdf page 4 : clés brutes, repr dict, chemin de dépôt, « décision fondateur » imprimés → libellés client

Exécution : la sonde partagée `_bout_en_bout.py` (même dossier) tourne dans le conteneur
django en transaction ANNULÉE (`docker cp` puis `python manage.py shell < fichier`)
pour les sondes `_bout_en_bout` / `_cas_limites` / `_catalogue_prod` (prod : lecture
seule, SSH) ; les sondes `_noyau_*` / `_economie` tournent sur l'hôte
(`cd backend/django_core && python <fichier>`, noyau pur sans Django).
"""
import pathlib

exec(compile((pathlib.Path(__file__).parent / "_bout_en_bout.py").read_text(encoding="utf-8"),
             "_bout_en_bout.py", "exec"))
