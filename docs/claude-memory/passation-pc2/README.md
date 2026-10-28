# Passation PC1 → PC2 — run L3 « générateurs de devis » (C&I, résidentiel, agricole)

Écrit le 28/10/2026 à 00:10 Casablanca (23:10 UTC le 27/10) par la coordinatrice PC1 (session
`local_3c349ea9`, worktree `bakery-quote-pricing-1e22b4`). Ordre du fondateur (Reda, 23:05 UTC) :
« make this pc push everything before the end of tokens, and the other pc can continue on the same
work — or even better the other computer can start now, so tonight everything is done ».

Ce dossier EST l'état complet du run : lis ce README en entier, puis `registre-pc1.md` (journal de
coordination PC1, section « STATE SNAPSHOT » en fin de fichier), `decisions-prises.txt` (décisions prises
pour le fondateur, à inclure dans le rapport du matin) et `notes/` (les constats et notes de chaque session,
dont `JETON-CI.md`, `JETON-DOCKER.md`, `REGLES-CI-FONDATEUR.md`, `CPDF-recette-rendu.md`).

## 0. Message à coller sur le PC2 (une seule fois, dans une session Claude Desktop ouverte sur `C:\dev\taqinor-os`)

```
Tu es la coordinatrice PC2 du run L3 « générateurs de devis » de TAQINOR OS. Le PC1 (autre compte Claude)
arrive au plafond hebdomadaire et te passe le relais. Fais exactement ceci :
1. `git fetch origin` puis lis en entier `docs/claude-memory/passation-pc2/README.md` sur la branche
   `origin/claude/passation-l3-devis-pc2` (`git show origin/claude/passation-l3-devis-pc2:docs/claude-memory/passation-pc2/README.md`),
   puis `registre-pc1.md`, `decisions-prises.txt` et `notes/` du même dossier. Lis aussi CLAUDE.md (règles 1-5,
   « Deploys — Claude s'arrête au merge », modèles par rôle) et docs/claude-memory/MEMORY.md.
2. Applique la section « 2. Lanes PC2 » : une session worktree par lane, créée DEPUIS la branche distante de la lane
   (source_branch = la branche indiquée), avec le brief de la lane (section 4) + les règles de la section 3.
   Maximum 8 sessions vivantes, 5 qui travaillent en même temps (le PC1 a planté l'app Claude à 20 sessions).
3. Tiens le JETON CI inter-PC (section 3.1) et le JETON DOCKER local (section 3.2). Surveille la file de merge toutes
   les 90 s (script watch_token.sh) et fais un point toutes les 10 min (wake.sh).
4. Ne demande rien au fondateur : prends l'option recommandée, note « Décision prise pour le fondateur (à revoir) »
   dans decisions-prises.txt du PC2, et continue. Le run s'arrête au merge : aucun déploiement, jamais wrangler.
5. À la fin (toutes les lanes mergées, ou plafond) : audit Fable final des PR mergées, rapport du matin en langage
   clair (sections 5 et 6), nettoyage (sessions archivées, worktrees, branches mergées, claims rendues).
```

## 1. Où en est le run (23:10 UTC)

- **21 PR mergées** depuis 02:00 UTC (liste dans `registre-pc1.md`, snapshot 22:17 : #1112, #1105, #1095, #1094, #1109,
  #1104, #1101, #1080, #1086, #1074, #1096, #1091, #1083, #1081, #1082, #1079, #1078, #1077, #1076, #1070, #1069).
- **File de merge GitHub (`main`)** à 23:00 UTC : pos 1 #1113 (PR du fondateur, api-fuzz), pos 2 #1115 CORC vague 2,
  pos 3 #1116 CPRW round 1, pos 4 #1103 RGEN. **#1114 RPDF** a été ÉJECTÉE deux fois (runs de groupe 22:17 et 22:28 :
  goldens `build_quote_data` en désaccord avec `main` — shards 0 et 5) : elle doit re-fusionner `main` APRÈS le merge de
  #1115 (CORC déplace la série horaire → les goldens bougent) puis recapturer (`UPDATE_GOLDEN=1`, Docker) et re-pousser
  sous jeton. **#1097 CQST** : rouge (stage-names, frontend-lint, frontend-static) ; correctif commité `e72130416`, push
  à venir sous jeton.
- **PC1 garde jusqu'à son plafond** (≈ 02:30 UTC, quota hebdo 83 % à 23:00, ≈ 5 %/h) : les PR en vol #1103 RGEN, #1097
  CQST, #1115 CORC, #1116 CPRW, #1114 RPDF, et CPDF (fenêtre Docker en cours, PR à venir). À son arrêt, PC1 pousse une
  dernière mise à jour de ce dossier (section 7 « ÉTAT FINAL PC1 ») et rend `app:jeton-ci`.
- **PC2 prend MAINTENANT** les lanes de la section 2 (elles attendaient Docker ou le jeton : rien ne se perd, tout
  est poussé sur `origin`).

## 2. Lanes PC2 (démarrer tout de suite, dans cet ordre de priorité)

| # | Lane | Branche distante à reprendre | État au 23:10 UTC | Premier geste sur PC2 |
|---|------|------------------------------|-------------------|-----------------------|
| 1 | **CSV** script d'appel C&I (CSV1-18) | `claude/ci-csv` @ `3110893e6` | construite (rien coché : preuves en direct manquantes), Fable GO ; attendait Docker (rejeu réel ~40 min) | rejeu réel sur la pile PC2 (recette notes/csv-notes.md), CSV11 acceptation, puis PR + file sous jeton |
| 2 | **RSIZ** taille et composition résidentiel R2 (RSIZ2-11) + R3 | `claude/res-rsiz` @ `26d601ad0` | RSIZ2-4, 7-11 commités, RSIZ5 WIP (recapture golden split_dm_comp interrompue), RSIZ6 à faire ; AUCUN test contre une vraie base | finir RSIZ5/6, tâches v3 + DONE LOG, Docker : 8 devis re-rendus + 7 modules de tests, Fable, PR |
| 3 | **AGC** client agricole (PDF 3 pages, web) | `claude/agr-agc` @ `61faa0a7b` | 13 tâches faites (8 commits), round 2 construit, tests R2 non joués, vérif R3 non rendue | tests Django R2 + rendu pompage réel ; AGC14 (contrat `depense_declaree`) ; recapture `agricole__*` APRÈS #1114 ; Fable ; PR |
| 4 | **AGV** vendeur agricole | `claude/agr-agv` @ `7b545201b` | AGV1-11, 13, 14 faites, 211 tests OK (7 modules), migration crm 0144 ; rendu du parcours réel différé | re-fusionner main (0144 à re-chaîner si prise), gardes, goldens générateur agricoles (TZ=UTC, `-t agricole`), PR ; rendu réel après merge |
| 5 | **CPRS** devis web serveur (3 segments) | `claude/ci-cprs` @ `eb9da2c81` | CPRS1-11 cochés, 182 tests OK, acceptation CPRS10 enregistrée | lignes DONE LOG CPRS9-11 + Fable, merge main, contrôles, PR + file sous jeton (pas de Docker) |
| 6 | **RWEB** site, tunnel, page devis résidentiel | `claude/res-rweb` @ `4852b2839` | RWEB1-7, 9, 11-23, 25, 26 cochés ; tsc/astro build/vitest verts ; RWEB24 ouvert | merge main (fichiers ≥ 2 000 l. sans croissance), `astro build`, PR ; régression CSS impression #1104 à examiner |
| 7 | **CEC v4** CEC18 (nan/inf refusés, 400 nommé), S3 | `claude/ci-cec-v4` @ `b7f0bb76a` | prête, Fable PUSHABLE | fusion `main` (DONE LOG : garder les deux côtés), contrôles, PR ; round 11 après merge |
| 8 | **CCAT** rounds 2+3 (table « prêt pour devis » C&I+agricole, fiche Deye, migration stock 0175) | `claude/ci-ccat-r3` @ `c54b9c0b0` | CCAT8-15, 102, 103 construits, critique Fable r2+r3 NON rendue | relancer la critique Fable, renuméroter 0175 si `main` a avancé, CODEMAP → `codemap_fingerprint.py --write`, PR ; CCAT16 après RSIZ |
| 9 | **CE2E** recette finale de bout en bout | repartir de `origin/main` (la branche `claude/beautiful-shannon-68c69b` = main, rien construit) | jamais démarrée | en DERNIER, quand tout est mergé : 10 profils C&I (boulangerie lead 1637) + 4 résidentiels + 2 pompage ; preuves en direct RHOR8, AMOT64, CLD9, CLD13 |

Les blocs d'état complets (FAIT / RESTE / CONTRÔLES / ATTENTES / FICHIERS / PIÈGES, rédigés par chaque session) sont
dans **`blocs-sessions.md`** de ce dossier — à lire avant de briefer chaque lane.

Les sessions PC1 de ces lanes ont reçu l'ordre de pousser puis de NE PLUS TOUCHER leur branche. Une branche = une
machine. Si un bloc de la section 4 manque pour une lane, lis la branche elle-même (`git log origin/<branche>`) : le
dernier commit « WIP sauvegarde PC1 » décrit l'état.

**Hors lanes, à faire par la coordinatrice PC2 quand les lanes sont mergées :** audit Fable final (depuis #1104 :
#1094 — vérifier que `investissement_hors_om` reçoit bien un calcul gardé par `regles_au_moins(devis, 3)` et non
`calcul_corrige` brut ; #1095, #1105, #1112, #1103, #1114, #1115, #1116, et toutes les PR PC2) ; contrôle ligne à ligne du
devis boulangerie (lead 1637 : `categorie=boulangerie` à poser, PDF /proposal) — demander à Reda d'être connecté à l'ERP
dans le navigateur, jamais de saisie d'identifiants par Claude ; PR docs de clôture (guide §4 : la recette de rendu
passe par `builder.generate_premium_devis_pdf` → `registre_renderers()`, voir `notes/CPDF-recette-rendu.md` ;
`docs/claude-memory/ci-decisions-2610.md` : 30° par défaut toit plat, inclinaison modifiable ; garanties Deye 5 ans /
Dyness DL5.0C 7 ans / Powerbox 10 ans ; liste des décisions) ; `.claude/settings.json` du projet : autoriser
`Bash(gh run cancel *)` (accordé par Reda pour toutes les sessions).

## 3. Règles du run (toutes en vigueur sur PC2)

### 3.1 JETON CI inter-PC — une seule CI dans toute la flotte, sur les DEUX machines
Ordre du fondateur (27/10 16:25) : « maximum is one CI per session … no 2 CI at the same time ». Détail dans
`notes/JETON-CI.md` et `notes/REGLES-CI-FONDATEUR.md`. Entre PC1 et PC2 le jeton est une **claim partagée** :
`python scripts/plan_claims.py list` montre `app:jeton-ci` et son propriétaire (PC1 = `<hostname PC1>/coord-pc1`,
pris 23:05 UTC, bail 6 h). PC2 le prend (`python scripts/plan_claims.py claim app:jeton-ci --owner <hostname>/coord-pc2
--branch main`) quand UNE de ces conditions est vraie : (a) `list` le montre PÉRIMÉ ou absent ; (b) la section 7 de ce
README dit « jeton rendu » ; (c) la file de merge ne contient plus aucune PR PC1 (#1103, #1097, #1115, #1116, #1114,
CPDF) et aucun run `merge_group` PC1 n'est en cours depuis 30 min. Tant que PC1 le tient, PC2 construit, teste sur sa
pile Docker, prépare ses PR (poussées « légères » : la CI PR des branches `claude/*` saute les jobs lourds — CI-UNE,
#1109) mais ne met RIEN en file.

Avec le jeton : UNE PR en file à la fois (toutes les PR touchent le DONE LOG de `docs/plans/PLAN_AUDIT_DEVIS.md` →
deux entrées se chevauchent → UNMERGEABLE) + UNE PRÉPA (la suivante poussée, auto-merge armé, elle entre seule quand la
première est mergée). Une éjection = le drapeau auto-merge disparaît et la PR sort de la file alors que ses checks PR
restent verts (les goldens ne surgissent que dans le run de groupe) : re-fusionner `main`, corriger, UN push, re-armer
`gh pr merge <n> --auto --merge`. `watch_token.sh <pr> [min] [sha rouge connu]` détecte MERGED / RED / UNMERGEABLE /
EJECTED ; `wake.sh 10` fait le point toutes les 10 min (file via GraphQL — `autoMergeRequest` vaut null dès qu'une PR
est DANS la file). `gh run cancel` est autorisé par Reda dans toutes les sessions (runs doublons seulement).

### 3.2 JETON DOCKER — local à chaque machine
`notes/JETON-DOCKER.md` : un seul usage lourd de la pile locale à la fois (harnais `test-backend.ps1`, `docker compose
run … manage.py …`, recapture `UPDATE_GOLDEN=1`) ; sans jeton, tests purs seulement ; conteneurs `run-…` tués dès
qu'inutiles ; jamais `restart`/`down` de la pile ni redémarrage de la base de dev. PC2 a sa propre pile : premier
détenteur recommandé CSV (rejeu ~40 min), puis RSIZ, AGC, AGV.

### 3.3 Goldens
`golden/moteur/build_quote_data/` (104 + 21 legacy) bougent avec toute nouvelle clé de la table de libellés i18n
(#1114 RPDF) et avec la série horaire (#1115 CORC). Ordre : laisser atterrir #1115 puis #1114 ; ensuite CPDF, AGC
(`agricole__*`), RSIZ recapturent UNE fois chacun, sur un `main` à jour, dans leur fenêtre Docker. `agricole__*` → AGC ;
résidentiel → RPDF (PC1) ; C&I → CPDF (PC1).

### 3.4 Machine
≤ 8 sessions vivantes, ≤ 5 en travail ; dans `~/.claude/settings.json` : `"disabledMcpjsonServers": ["serena",
"chrome-devtools"]` (chaque session lançait 3 serveurs MCP node — c'est ce qui a saturé PC1) ; un seul `vite`/`astro
dev` par session, fermé après usage ; une seule critique Fable en vol par session ; garde toutes les 10 min : RAM libre
< 5 Go → arrêter le tour des deux sessions les plus récentes hors jeton.

### 3.5 Décisions et fondateur
Ne jamais attendre Reda : option recommandée + ligne « Décision prise pour le fondateur (à revoir) » dans
`decisions-prises.txt` (celui du PC2 : même format, à joindre au rapport). Sa dernière décision l'emporte. Décisions
déjà prises aujourd'hui : voir `decisions-prises.txt` (30° toit plat par défaut, inclinaison modifiable ; garanties
Deye 5 / Dyness DL5.0C 7 / Powerbox 10 ; provision onduleur au prix payé, niveau 3 ; parallèle d'hybrides = même
modèle ; D-AGM-1/2/3 ; catalogue : aucun article structure_sol, taux INST-PMP absent, pas de pompe à courbe
monophasée, pompes OSP sans prix → 0/10 devis agricoles auto chiffrables). Protection des devis envoyés : corrections
du 27/10+ gardées par `regles_au_moins(devis, 3)` (REGLES_CORRIGEES_2710 = 3), jamais par `calcul_corrige`.
`Produit.prix_achat` jamais côté client. Règle #4 : `/proposal` seul chemin PDF client.

## 4. Blocs d'état des sessions PC1

Collectés à 23:35 UTC : **`blocs-sessions.md`** (9 lanes cédées + l'état des 6 lanes PC1). Voir aussi
`notes/<session>-*.md`. Les pushes de CSV et RWEB ont été refusés par le garde-fou de leurs sessions ; la coordinatrice
PC1 a poussé ces deux branches elle-même sur ordre du fondateur (vérifié par `git ls-remote`).

## 5. Rapport du matin attendu par Reda (langage clair, en français)
Combien de PR mergées et ce que chacune change pour un devis (C&I, résidentiel, agricole) ; ce qui reste ouvert et
pourquoi ; les décisions prises pour lui (`decisions-prises.txt` PC1 + PC2) ; les manques du catalogue (données
fondateur, jamais inventées) ; l'état du devis boulangerie (lead 1637) ; le nettoyage fait. Déploiement = Reda
(`scripts/deploy-prod.ps1`, 2 min ; l'auto-deploy du serveur suit aussi chaque merge).

## 6. Nettoyage de fin (PC2, et PC1 pour ce qui est chez lui)
Archiver les sessions terminées ; `git worktree prune` + suppression des worktrees `agent-*`/`lane-*` morts ; branches
distantes mergées supprimées ; `python scripts/plan_claims.py release app:jeton-ci --owner <soi>` ; keep-awake rendu.
PC1 a aussi : le checkout principal `C:\dev\taqinor-os` à remettre sur `origin/main` quand il est propre (jamais
touché par PC2).

## 7. ÉTAT FINAL PC1

**00:30 UTC — la coordinatrice PC1 s'arrête (plafond Fable 92 %, ordre du fondateur « give to the other session »).** Les sessions PC1 encore vivantes (RPDF #1114, RGEN #1103, CQST #1097, CPRW #1119 puis round 3 sur claude/cprw-r3) ont reçu l'ordre d'être AUTONOMES jusqu'au merge de leur PR (éjection → merge main, correctif, UN push, re-armer) puis de laisser 3 lignes dans le dossier partagé et de s'arrêter ; CPDF est cédée au PC2 (claude/cpdf). Le PC2 prend le jeton CI dès maintenant (claim rendue ci-dessous) : la file de merge sérialise de toute façon ; il surveille aussi ces 4 PR PC1 et les re-arme si leur session PC1 est tombée au plafond (quota all-models 89 % à 00:25).

Écrit le 28/10/2026 00:27 UTC par la coordinatrice PC1 (arrêt : plafond hebdomadaire).

**PR mergées depuis 23:10 UTC :**
  - #1118 00:03 UTC — Propriété : docs/openapi-schema.yml déclaré surface append-only (instantané régé
  - #1116 23:37 UTC — CPRW2-14 — devis web C&I : rien d'interne ni d'incertain côté client, bandeau « 
  - #1115 00:09 UTC — CORC vague 2 : pose estimée = pose chiffrée, prestation sans article, brouillons
  - #1113 00:03 UTC — api-fuzz-full 19e passe — tous les constats du run 40556418249 (hors beacon rése
  - #1111 00:03 UTC — plan(AIC) : assistant IA des commerciaux sur les crédits API du plan Max — 25 tâ

**PR PC1 encore ouvertes (à reprendre par PC2 — chacune : si éjectée, fusionner main UNE fois, corriger, UN push, `gh pr merge <n> --auto --merge`) :**
  - #1114 OPEN CLEAN auto-merge=false claude/res-rpdf-r1 @ 089f6956e
  - #1097 OPEN CLEAN auto-merge=false claude/ci-cqst @ 410477a29
  - #1103 OPEN CLEAN auto-merge=false claude/res-rgen @ 4d80f2003
  - #1115 MERGED UNKNOWN auto-merge=false claude/ci-corc-v2 @ 7a02b1912
  - #1116 MERGED UNKNOWN auto-merge=false claude/cprw-r1 @ c27b73d2a
  - #1113 MERGED UNKNOWN auto-merge=false claude/api-fuzz-drain-22 @ f3a9a1f95
  - CPDF : branche claude/cpdf @ bd7e165ae (PR à créer après #1114 ; recapture goldens C&I après #1115 + #1114 ; recette notes/CPDF-recette-rendu.md).

**File de merge à l'arrêt :**
  - pos 1 #1103 AWAITING_CHECKS — RGEN — vendeur résidentiel : écran = devis auto = PDF (taille demandée
  - pos 2 #1119 AWAITING_CHECKS — CPRW15-24 — devis web C&I : garanties et échéancier servis, services, 
  - pos 3 #1097 AWAITING_CHECKS — CQST vague 1 : questionnaire client — ce qui manque = règle du devis a
  - pos 4 #1117 UNMERGEABLE — Attribution des leads par le responsable d'équipe (écran Entrée / flèc

**Jeton CI : rendu** (`plan_claims.py release app:jeton-ci`) à 28/10/2026 00:27 UTC — PC2 peut le prendre (`claim app:jeton-ci --owner <hostname>/coord-pc2 --branch main`).
Les sessions PC1 restantes (RPDF, CORC, RGEN, CQST, CPRW, CPDF) sont arrêtées ; leur dernier état est dans blocs-sessions.md (section « Lanes PC1 ») et dans les PR elles-mêmes.

**00:55 UTC (addendum) :** #1103 RGEN, #1119 CPRW round 2 et #1097 CQST sont MERGÉES (~00:51) → 26 PR mergées sur le run. Reste en vol côté PC1 : #1114 RPDF (seule en file) et le round 3 de CPRW (claude/cprw-r3, PR à venir, jeton pré-accordé). Les sessions RGEN et CQST écrivent leur note finale et s'arrêtent.

**01:22 UTC (addendum) :** #1122 CPRW round 3 (CPRW25-29) MERGÉE à 01:21 → 27 PR mergées sur le run ; la lane CPRW est complète (#1104, #1116, #1119, #1122). Il ne reste côté PC1 que #1114 RPDF (rounds 1-3), en correction après son éjection de 00:57 (trois tests : digests publics, rendu « comme avant », formats de montants EN) — RPDF refusionne main, repousse UNE fois et re-arme ; si sa session tombe au plafond, le PC2 reprend claude/res-rpdf-r1.
