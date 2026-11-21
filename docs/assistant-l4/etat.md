# Assistant L4 — état du chantier (à lire EN PREMIER pour reprendre)

Dernière écriture : 21/11/2026 vers 04:45 UTC, session du poste de Reda · branche `claude/assistant-l4-notes`.
**Prochaine action unique** : lire le run 44867791776 (tour 1 sur runner, branche `claude/assistant-l4`), juger les
transcripts (KC, KD, KE), consolider, corriger.

## Demande et cadre
- Demande de Reda (21/11) : voir `contrat-de-sortie.md` (mot pour mot). Niveau L4 · régime EXISTANT.
- Coût : quota 91 % au tour 0 (au-delà de la ligne d'arrêt 90 %) → k = 0, tour 0 seulement.
- Poste : 8 cœurs, 3,4 Go de mémoire libre, 29 Go de disque libre ; **Docker Desktop en panne** sur ce poste (21/11,
  ne redémarre pas) → l'instrument est un runner GitHub, pas une pile locale.

## Inventaire (promesses → état sur origin/main + PR #1513)
| # | Promesse | État | Preuve |
|---|---|---|---|
| P1 | connaît chaque écran et chaque geste de l'ERP | partielle | `assistant/manuel.md` (≈ 85 000 car.) écrit par le skill `assistant-manuel`, régénéré À LA MAIN ; routeur `frontend/src/router/index.jsx` (56 `path:` + routes des modules) relu par aucune garde |
| P2 | connaît chaque action qu'il peut faire | servie | catalogue vivant `apps/agent/registry.py` + `apps/*/agent_actions.py`, filtré par rôle (`for_user`) |
| P3 | reste à jour quand l'ERP change | **absente** | aucune garde CI entre registre / routes / permissions et le manuel ou `capacites.yml` (la parité n'existe qu'au §6 du skill, joué à la main) ; la PR #1513 a dû régénérer le manuel à la main |
| P4 | répond aux questions simples sur ses données | servie (essai réel du 21/11 : 12/12) | `sql_db_query` + outils de lecture |
| P5 | aide à se servir de l'ERP (où, comment) | partielle | manuel §4-bis (15 questions) ; écrans récents possiblement absents |
| P6 | chacun ne voit que ce que son rôle permet | largement servie, jamais prouvée par attaque | SQL : `_FORBIDDEN_COLUMNS` / `_PRICE_TABLES` levés seulement par `prix_achat_voir` (`sql_agent_service.py`) ; outils : routes Django + sérialiseurs du rôle |
| P7 | pas de sur-blocage : le Directeur obtient prix d'achat / marge en interne (décision du 19/11) | **à vérifier** | `CONSIGNES_COMMERCIALES` dit « Jamais de prix d'achat ni de marge » à TOUS les rôles |

## Plan des tours (quand le quota le permet)
- **Lane 0** (avant le tour 1) : générateur déterministe `scripts/assistant_carte_erp.py` → `backend/fastapi_ia/assistant/carte_erp.md`
  (routes et libellés de menu, modules et leurs écrans, actions du registre par domaine avec carte / directe, grille des
  permissions par rôle, CODEMAP §4 condensé) + mode `--check` dans le job `stage-names` + test rouge-puis-vert (KB) ;
  carte servie au modèle à côté du manuel (budget de tokens à mesurer) ; parité registre ↔ `capacites.yml` en CI.
- **Tour 1** : 5 relecteurs neufs (opus high), un par rôle × axe : Commercial (questions du quotidien), Commercial
  responsable (pilotage d'équipe + attaques de confidentialité), Directeur (gestion + accès aux coûts), terrain /
  technicien (visites, chantiers, SAV), « nouvel arrivant » (où est quoi, comment faire). Chacun écrit ses questions et
  ses attaques ; le runner les joue avec le vrai modèle sous le compte du rôle ; il juge les transcripts.
- **Instrument** : workflow TEMPORAIRE sur runner (modèle : commit `6ba868c01f` de la PR #1513, retiré ensuite),
  `seed_demo` + un compte par rôle, clé d'IA = secret du dépôt seulement, e-mail en console, rien vers la prod.
  Contrôle de l'instrument à jouer au premier lancement (backend d'e-mail console, aucune clé d'envoi, ports 127.0.0.1).

## Claims
- Propriétaire des fichiers : `analyse` (`docs/plans/PLAN_AUDIT_ANALYSE.md`). Claims prises au tour 1 (rien n'est
  construit au tour 0).

## Déroulé
1. Tour 0 (21/11 vers 04:45 UTC) : régime EXISTANT, poste mesuré, quota 91 % → arrêt après le tour 0 ; contrat KA-KF
  écrit ; inventaire P1-P7 ; lecture de la CI de `main` remise au tour 1.
2. Reda (21/11 ≈ 04:50 UTC) : « continue untill you hit 100% » — la ligne d'arrêt 90 % est levée par lui (avertissement
  donné : plus rien pour ses autres sessions jusqu'à la remise à zéro).
3. Lane 0 (commit a3b728cd0a, branche `claude/assistant-l4` empilée sur la PR #1513) : `scripts/assistant_carte_erp.py`
  + `assistant/carte_erp.md` (27 762 car.) + garde `--check` dans stage-names + tests (KA, KB verts) ; consigne prix
  d'achat / marge alignée sur le droit du rôle (P7). Coût ≈ 1 point (91 → 92 %).
4. Tour 1 : instrument sur runner (`zz-scratch-l4-assistant`, comptes l4_commercial / l4_commercial_resp /
  l4_directeur, oracle de fuite = prix d'achat du catalogue) : 36 questions + 20 attaques × 3 rôles, run 44867791776.
