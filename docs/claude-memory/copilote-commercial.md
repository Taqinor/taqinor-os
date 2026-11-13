# Copilote commercial (13/11/2026)

Demande de Reda : l'assistant IA de l'ERP doit faire tout le travail quotidien de la commerciale (elle lui
parle), préparer les WhatsApp (elle n'appuie que sur Envoyer) et aider à déboguer. Enquête L3 + construction
dans la même session. Dossier : `docs/assistant-copilote.md`. Tâches : groupe AIC, AIC60 et suivantes
(`docs/plans/PLAN_AUDIT_ANALYSE.md`, renvois LEAD / DEVIS / DEPLOY).

## Ce qui gouverne toute suite
- **Deux interrupteurs, éteints pour les commerciaux au merge.** `ASSISTANT_COPILOTE` (Django : `aucun` |
  `admins` défaut | `tous`) sert ou non les actions du lot `copilote` (`AgentAction.lot`) ;
  `ASSISTANT_MOTEUR` (FastAPI : `langchain` défaut | `natif`). Un outil NEUF vu par le modèle naît dans le lot
  `copilote`, jamais hors lot (leçon du 29/10 : tests simulés verts, fournisseur réel cassé).
- **Le modèle n'écrit ni un texte client ni la réponse d'une touche.** Textes = textes validés du suivi rendus
  par le serveur. Réponse d'une touche = « carte-écho » : `crm.suivi.proposer_reponse` (lecture) → le serveur
  valide et rend `proposition` → le doigt de la commerciale poste au geste existant.
- **Toute autre écriture demandée par le modèle = proposition à confirmer dont l'aperçu NOMME l'objet**
  (`AgentAction.objets` + `GET agent/libelles/`).
- **Une carte ne vient jamais du texte du modèle** : l'écran ne lit que `cartes[]` (contrat
  `apps/agent/contract_samples/assistant_reponse.json`), catalogue fermé `registry.CARTES`.
- **Le serveur donne la date** (`prompt_copilote.entete_tour`, `zoneinfo`). Ne jamais écrire un décalage horaire
  en dur : le 13/11/2026 la base de fuseaux donnait Casablanca à +00 (et +01 en janvier et en juin).
- D-WHATSAPP et RELANCE-WA inchangées : `wa.me`, ouvrir WhatsApp ne clôt pas une touche.

## Décisions prises par défaut pendant la construction (à confirmer par Reda)
- Remise, prix de ligne et changement d'étape par l'assistant : toujours à confirmer ; « Signé » seulement par
  l'acceptation d'un devis ; plus de phrase de repli dans le brouillon de suivi (formule interdite par le Guide).
- Voix : dictée avec relecture, plus de confirmation orale (« non je ne confirme pas » confirmait).
- Conversation du moteur natif gardée 48 h au plus (Redis).

## Encore ouvert
- Essai du copilote et du moteur natif avec une vraie clé (aucune dans la session de construction), puis
  bascule des deux interrupteurs — gestes de Reda.
- Décisions du fondateur listées au §6 du dossier (plafond de dépense, seuil de remise en production, texte
  client par le modèle, avis du juriste, leads froids, destination des signalements, canal WhatsApp officiel).
- Défaut de tarification relevé : une baisse de prix de LIGNE échappe au seuil d'approbation des remises.

## Leçons de run
- Les worktrees des lanes ne partaient PAS de `main` local malgré le hook : chaque lane a dû avancer sur le
  commit des contrats (`git merge --ff-only <sha>`) — toujours donner ce repli dans la consigne.
- Sans Docker : Postgres 16 + pgvector et Redis natifs suffisent ; la base de test (≈ 2 350 migrations) se
  construit en ≈ 2 h sur 4 cœurs — la lancer en tout premier, puis la cloner par lane (`CREATE DATABASE …
  TEMPLATE`).
