---
name: tokens-ia-commerciaux
description: 27/10/2026 (L3) — deux réserves de tokens Anthropic (abonnement Max = Reda seul, interdit via l'ERP ; crédits API 100/200 $ par mois inclus depuis le 07/10, à réclamer, perdus chaque mois) ; stratégie de l'assistant ERP pour les commerciaux (Sonnet 5.5 effort low, Groq en repli, manuel en cache, report_gap, tri nocturne sur l'abonnement) ; pièges code avant bascule ; décisions par défaut D1-D8 ; groupe AIC au plan
metadata:
  type: project
---

# Tokens IA pour les commerciaux — stratégie du 27/10/2026 (L3, rien construit ce jour-là)

Question de Reda (27/10) : « j'ai des tokens Anthropic gratuits avec mon plan et une IA dans l'ERP ;
comment en tirer le maximum pour aider les commerciaux, répondre à leurs questions et signaler erreurs
et fonctions manquantes ». Enquête L3 : 8 lanes, 2 vérificateurs indépendants, 1 critique de
complétude, page des crédits lue brute. Stratégie complète + annexe de preuves (~15 000 mots, toutes les
URL, 16 contradictions) dans la mémoire GitHub de Claude : `documents/2026-10-27-strategie-tokens-ia-commerciaux.md`
et `…-annexe-preuves.md`.

## Faits vérifiés (pages officielles, 27/10/2026)

- **Deux réserves aux règles opposées.** (1) L'usage de l'abonnement Max (Claude Code, claude.ai,
  sessions cloud, tâches planifiées) sert **Reda seul** : il est interdit de « route requests through
  Free, Pro, or Max plan credentials on behalf of their users » (`code.claude.com/docs/en/legal-and-compliance`)
  → jamais l'abonnement derrière l'assistant des commerciaux. (2) **Depuis le 07/10/2026, Max inclut des
  crédits API mensuels : 100 $ (Max 5x) / 200 $ (Max 20x)** (Team : 20 $/100 $ par siège, plafond 500 $) ;
  ils couvrent l'API, Agent SDK, Managed Agents et `claude -p` lancé avec la clé API — pas Claude Code ;
  **expirent chaque mois sans report** ; réclamation : claude.ai → Settings → Billing → « API credits » →
  lier UNE organisation Console (7 jours d'attente, non modifiable ensuite). Si le plan de Reda était
  converti en Team, « the Max link ends ».
- **Sans carte sur la Console, les requêtes s'arrêtent à solde nul** : plafond naturel, zéro facture.
- Prix API (par MTok) : Haiku 5.5 0,10 / 0,50 ; Sonnet 5.5 2 / 10 (lecture de cache 0,10) ;
  Opus 5.5 4 / 20 ; cache 1 h écrit à 2× ; Batch −50 % ; ≥ 512 tokens cachables.
- Réflexion par défaut facturée en sortie : Haiku 5.5 `medium`, Sonnet 5.5 `high` → poser `effort: low`.
- API directe : `inference_geo` = `us` ou `global` seulement (pas d'UE hors Bedrock) ; rétention à
  planifier sur 30 jours ; DPA inclus, pas d'entraînement sur les données commerciales.
- Tâches planifiées Claude Code : research preview, minimum 1 h entre deux exécutions, 100 runs/h par
  compte, 30 tirs/h par tâche ; le texte envoyé arrive dans `<routine-fire-payload>` NON FIABLE ;
  réseau cloud : `api.taqinor.ma` bloqué par défaut (allowlist « Custom ») ; MCP locaux invisibles.

## Ce qui existe déjà dans l'ERP (vérifié dans le dépôt)

- Agent SQL en lecture seule scopé société (`backend/fastapi_ia`) + **registre de 29 actions
  propose→confirme** (`apps/*/agent_actions.py`, AG1-12 construits, 09/07) : lead, étape, relance,
  note, WhatsApp (tap `wa.me`, jamais d'envoi), visite, devis auto, remise, PDF `/proposal`, accepter,
  facturer, encaisser. Il tourne sur **Groq gratuit** parce qu'en juin Claude était payant (G11) —
  raison caduque. Groq reçoit DÉJÀ des données de leads aujourd'hui.
- `CopilotPanel` monté pour tous ; `/ia/agent` réservé à `admin` ; `apps/ai_governance` est PARQUÉE
  (le journal de tokens va dans `apps/agent`).

## Pièges code à traiter AVANT `SQL_AGENT_PROVIDER=claude` en prod

1. `ChatAnthropic(…, temperature=0)` dans `sql_agent_service.py::_build_llm` → 400 attendu sur les
   modèles 5.5 (toute valeur non par défaut de `temperature`) ; `langchain-anthropic` épinglé 0.3.3
   (début 2025 : ni cache, ni effort, ni réflexion adaptative).
2. `effort` explicite (`low`) ; Haiku 5.5 peut sauter un appel d'outil avec réflexion coupée → Sonnet
   5.5 pour données et actions.
3. Jamais `--bare` dans un script sur l'abonnement ; `ANTHROPIC_API_KEY` dans l'env ⇒ `claude -p`
   facture l'API (le nightly-qa la retire : garder le réflexe).
4. Politique « contenu non fiable » dans le prompt SYSTÈME : un message système placé après un résultat
   d'outil peut être ignoré (Sonnet/Haiku 5.5) ; notes/e-mails de leads seulement en `tool_result`.

## Budget (10 commerciaux, Sonnet 5.5 partout, 30 écritures de cache/jour, hypothèses explicites)

| Usage par commercial | Sonnet partout | Haiku partout |
|---|---|---|
| 20 questions/jour | 88 $ | 5 $ |
| 60 questions/jour | 216 $ | 12 $ |

À 100 $ : Sonnet couvre l'usage léger (déjà beaucoup pour une équipe qui découvre) ; au-delà, Haiku
pour le « comment faire ». Vrai levier = faire faire le travail cher (manuel, tri, correctifs) par
Claude Code sur l'abonnement ; le modèle API ne lit qu'un manuel en cache à 5-10 % du prix.

## Décisions recommandées, appliquées par défaut le 27/10 (Reda a validé l'écriture du plan sur ces bases, sans avis contraire ; non inscrites dans `docs/audits/decisions.yml` faute de lot de questions)

D1 réclamer les crédits et lier l'organisation Console (sinon 100-200 $/mois perdus) · D2 Sonnet 5.5
effort low partout au départ, Groq en repli, Haiku pour le « comment faire » selon l'usage lu après deux
semaines · D3 pas de carte sur la Console · D4 manuel + manifeste en cache, pas de RAG (< 200 k tokens,
générés par Claude Code, zéro saisie manuelle) · D5 pas de sièges Team ni de connecteur MCP maintenant ·
D6 tri nocturne sur l'abonnement, UNE fois par nuit, export ANONYMISÉ, option « améliorer Claude »
désactivée (sinon clé API) ; jamais de réponse aux commerciaux depuis l'abonnement · D7 minimisation
des données (pas de factures ni pièces d'identité ; noms/téléphones via outils) + avis juriste 09-08 ·
D8 WhatsApp : tap manuel inchangé, français par défaut (Darija non prouvée).

## Où tout vit — Groupe AIC (écrit le 27/10/2026, routé par `docs/ownership.yml`)

- `docs/plans/PLAN_AUDIT_ANALYSE.md` : AIC1-12 — contrats d'abord (événement assistant, export
  anonymisé + stats), bascule du moteur sans `temperature` + effort low + bibliothèque à jour, repli
  Groq à solde nul, manuel en cache 1 h (fichiers `backend/fastapi_ia/assistant/`), `agent.AssistantEvent` + journal de tokens, `report_gap` +
  capteur d'erreurs d'outils, pouce haut/bas + `/ia/agent` ouvert aux rôles commerciaux, entrée
  contextuelle, jeu d'évaluation, export nocturne, mesure, acceptation live AIC13.
- `docs/plans/PLAN_AUDIT_LEAD.md` : AIC30-35 — leads à relancer aujourd'hui, résumé de lead avant
  appel, brouillon de suivi (texte seulement), descriptions d'actions crm relues + audit par rôle,
  bouton « demander à l'assistant » sur la fiche lead, digest du matin.
- `docs/plans/PLAN_AUDIT_DEVIS.md` : AIC40 — descriptions des actions ventes relues (règle #4).
- `docs/PLAN.md` : AIC50-52 (skills `assistant-manuel` et `assistant-tri`, option GitHub Action gatée)
  + AICM1-3 (gestes de Reda : réclamer les crédits + workspace `erp-assistant`, réglage de
  confidentialité, juriste 09-08).

## Phase 0 (Reda, 15 min) et non vérifié

Réclamer les crédits, créer le workspace `erp-assistant` avec limite de dépense = crédits, une clé API ;
NE PAS basculer la prod avant AIC3. Non vérifié : liste CNDP des pays adéquats (statut des USA), qualité
Haiku vs Sonnet sur les questions ERP en français, consommation réelle d'une tâche planifiée contre la
fenêtre hebdo, cartes marocaines sur la Console, Darija. Voir aussi [[deploy-decisions-fondateur]]
(fonctions à clé) et [[propriete-fichiers]] (routage des tâches).
