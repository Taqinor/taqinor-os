# `apps/agent/contract_samples/` — les contrats PACT10 de l'agent et de l'assistant

Même doctrine que `apps/ventes/contract_samples/README.md` : chaque fichier porte `endpoint`, `pourquoi`, `exemple` (un objet) et, quand il déclare la carte de sa route, `forme_serveur`.

| Fichier | Ce qu'il apparie |
| --- | --- |
| `logs_confirmer.json` (AUDV27, AANA18) | POST agent/logs/confirmer/ : journal d'une action IA CONFIRMÉE, preuve HMAC du relais |
| `assistant_evenement.json` (AIC1) | POST agent/evenements/ (relais serveur) + PATCH agent/evenements/<pk>/note/ (note et commentaire du commercial) ; vue produite par AIC6 |
