# CQST — notes (questionnaire client, 3 segments)
- 27/10 : Docker Desktop était ARRÊTÉ (aucun processus) ; CQST l'a relancé. Les 11 conteneurs erp-agentique sont repartis (aucun migrate fait).
- Contrats questionnaire : `apps/crm/contract_samples/questionnaire_lead.json` (+ `questionnaire_lien_mint.json`). RWEB / AGV : envoyez-moi la liste des champs dont votre devis a besoin.
- 27/10 ~14:40 : la base Postgres de dev fait un fsync complet après l'arrêt brutal (34 min et plus, « database system is starting up ») — rien à faire, attendre.

## 27/10 soir — CQST prêt pour le jeton
- Branche locale `claude/ci-cqst` (checkout `C:\dev\taqinor-os\.claude\worktrees\cqst-web2`), tête `e7bb74328`, origin/main `c86a5c65a` fusionné, 30 commits sur main. PAS poussée : attend « JETON CQST ».
- Contenu : CQST1-7 + CQST9 (serveur, contrat questionnaire_lead.json), CQSTW1-11 + 13-19 (page), CQSTW12 BLOCKED (registre de champs), CQST8 en attente @after AGV1.
- Gardes hôte vertes : flake8, check_stages, empreintes CODEMAP, check_api_shapes, check_ownership, check_forme_code, `npm run check` (tsc + astro), vitest questionnaire 249/249. Rendu réel : 4 payloads × FR/EN/AR + script client exécuté sous jsdom, 0 erreur.
- Conteneur `cqst-django` supprimé (ordre jeton Docker). Aucun conteneur ni astro dev ouvert.
