# `apps/agent/contract_samples/` — les contrats PACT10 de l'agent et de l'assistant

Même doctrine que `apps/ventes/contract_samples/README.md` : chaque fichier porte `endpoint`, `pourquoi`, `exemple` (un objet) et, quand il déclare la carte de sa route, `forme_serveur`.

| Fichier | Ce qu'il apparie |
| --- | --- |
| `logs_confirmer.json` (AUDV27, AANA18) | POST agent/logs/confirmer/ : journal d'une action IA CONFIRMÉE, preuve HMAC du relais |
| `assistant_evenement.json` (AIC1) | POST agent/evenements/ (relais serveur) + PATCH agent/evenements/<pk>/note/ (note et commentaire du commercial) ; vue produite par AIC6 |
| `assistant_export.json` (AIC2) | GET agent/evenements/export/ : export ANONYMISÉ pour le tri nocturne, règles dans la clé `anonymisation` ; vue produite par AIC11 |
| `assistant_stats.json` (AIC2) | GET agent/evenements/stats/ : statistiques de l'assistant, prix par million de tokens dans `prix_mtok` ; vue produite par AIC12 |
| `assistant_reponse.json` (COP1) | POST /api/fastapi/sql-agent/query (relais FastAPI, aucune vue Django) : `cartes` = toutes les sorties structurées du tour, typées par `AgentAction.carte` ; + la réponse de `/sql-agent/confirm` (`carte`, `suite`), l'historique rejoué et la forme de `contexte.diagnostic`. Lu par les tests des DEUX moitiés |
