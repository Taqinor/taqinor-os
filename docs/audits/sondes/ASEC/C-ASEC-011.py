SONDE = {"constat": "C-ASEC-011", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : le validateur SQL de l'agent (backend/fastapi_ia, _validate_and_secure) "
                    "refuse ou réécrit UNION/UNION ALL même table, sous-requête scalaire et littéral imitant le "
                    "filtre ; exécuté, aucune ligne de l'autre société"}


def sonde(ctx):
    # Le validateur vit dans le conteneur FastAPI (erp-agentique-fastapi_ia-1), injoignable depuis le shell
    # Django où tourne ce lanceur : rien n'est rejoué ici. Preuve consignée à côté, exécutée en lecture seule.
    return ("STATIQUE — validateur SQL de l'agent dans backend/fastapi_ia (autre conteneur, non rejouable depuis "
            "le shell Django). Preuve : les 3 tests nommés d'ASEC42 (test_union_meme_table_isole, "
            "test_sous_requete_scalaire_isolee, test_litteral_mono_table_isole) exécutés le 2026-10-30 dans "
            "erp-agentique-fastapi_ia-1 (pytest absent de l'image -> `python -m unittest` des mêmes classes) : "
            "'Ran 3 tests ... OK', exit=0. Aucune base de test créée : le test ouvre la base de la pile "
            "(DB_HOST=db, moteur connecté vérifié = True), crée des tables TEMP homonymes dans une transaction "
            "ANNULÉE et compte les lignes réelles (aucune 'soc8', count = 2). Fichiers du conteneur identiques au "
            "worktree (sha256 du test 6dae7b16… et de sql_agent_service.py de55a1ea…). Sortie brute : "
            "docs/audits/acceptation/ASEC/traces/2026-10-30/C-ASEC-011-pytest.txt.")
