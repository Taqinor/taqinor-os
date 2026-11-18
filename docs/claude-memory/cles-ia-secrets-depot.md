---
name: cles-ia-secrets-depot
description: Où vivent les vraies clés d'IA (secrets du dépôt GitHub et .env du serveur) et comment jouer un essai avec le vrai assistant sans rien demander à Reda
metadata:
  type: reference
---

Reda, 18/11/2026, à une session cloud qui lui demandait une clé : « there is a key in the ERP use it », puis
« find the keys yourself ». Il a refusé le formulaire de saisie de clé : ne plus le proposer.

**Où sont les vraies clés (vérifié le 18/11/2026).** À deux endroits seulement :
- le `.env` du serveur (`/opt/taqinor-os/.env`) ;
- les **secrets du dépôt GitHub** `CLAUDE_API_KEY` et `GROQ_API_KEY`, lisibles par un workflow
  (`${{ secrets.CLAUDE_API_KEY }}`), jamais par une session.

Elles ne sont nulle part ailleurs : ni dans le dépôt ni dans son historique, ni dans le `.env` local des postes
(valeurs d'exemple constatées le 13/11, trace `docs/audits/acceptation/AANA/traces/2026-11-13/`), ni dans
l'environnement cloud, ni dans les autres dépôts, ni dans Drive ou Gmail. Depuis une session cloud le serveur
refuse la connexion SSH et aucun poste n'est attaché.

**Comment jouer un essai avec le vrai assistant (toute session, cloud comprise).** Pousser sur sa branche un workflow
TEMPORAIRE `.github/workflows/zz-scratch-acceptation-<sujet>.yml` (déclenché par `push` sur cette branche) qui monte
Django + le service d'IA réel sur un runner avec les secrets, joue la spec d'acceptation, masque les clés dans les
journaux et recommite l'enregistrement ; puis le SUPPRIMER (« essai terminé : suppression du workflow temporaire »).
Modèle à copier : le commit `02c6bd8d48` (17/11, job `assistant` + `.github/zz-acceptation-commit.sh`).
Fournisseur de ces essais : `SQL_AGENT_PROVIDER=claude`, `SQL_AGENT_MODEL=claude-sonnet-5-5`, `SQL_AGENT_EFFORT=low`,
repli `groq`. Un essai coûte quelques centimes de crédits API.

**Ne jamais** afficher une clé (pas de `echo`, pas de `set -x` dans un pas qui la porte), ni la recopier dans un
fichier, un journal, une PR ou une réponse. Voir aussi [[tokens-ia-commerciaux]] et [[setup-missing-tools]].
