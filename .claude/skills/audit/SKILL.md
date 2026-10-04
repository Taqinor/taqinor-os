---
name: audit
description: Commande d'audit TAQINOR OS v2 (méthode docs/audits/METHODE.md, registre partagé docs/audits/unites.yml). Invoquer quand Reda tape « audit first », « audit next », « continue audit », « loop audit », « audit status », « audit <mot> » (totaux, facturation, calepinage, acquisition, lead, crm, sécurité, pdf, moteur, chantiers, stock, documents, parametres, générateur, devis, deploy, sav, analyse, performance — ou un mot v1 leads, fiche, cadence, clients, visites, ged, portail), avec option L1/L2/L3 ou « contre-visite », ou « vérifie <GROUPE> ». Audite UNE unité (go-deep calibré, preuve exécutée obligatoire), route chaque tâche vers le fichier de plan du PROPRIÉTAIRE des fichiers (docs/plans/PLAN_AUDIT_<UNITE>.md ou PLAN_AUDIT_TRANSVERSE.md), met à jour le registre et livre UNE PR docs-only. Ne construit jamais rien.
---

# Audit — commande opérationnelle

**Lire `docs/audits/METHODE.md` avant tout run** (critères C1-C14, phases, formats, routage, claim).
Ce fichier n'en est que le mode d'emploi ; en cas de doute, METHODE.md fait foi. Le registre
`docs/audits/unites.yml` est la source de vérité partagée entre postes : on le lit TOUJOURS sur
`origin/main` après `git fetch origin --prune`.

Un audit **ne construit rien** (pas de code, de migration, de deploy, d'envoi réel, de prod). Il produit :
dossier d'évaluation + tâches routées par propriétaire + registre à jour + rapport, dans UNE PR docs-only.

## 1. Déclencheurs

| Reda tape | Action |
|---|---|
| `audit first` | unité de `rang: 1` |
| `audit next` | plus petit rang au `statut: à auditer` et **non réclamé** (§3) |
| `continue audit` | claim vivant de plus petit rang (run interrompu ou autre poste) : reprendre à la première phase non close du dossier poussé sur `audit-<id>` ; aucun → `audit next` |
| `loop audit` | §6 |
| `audit status` | tableau classé des 19 unités : rang, id, mot, P×I, niveau, statut (registre) — remplacé par « en cours (audit-<id>, dernier commit <date>) » si un claim est vivant, avec « périmé » au-delà de 48 h —, groupe, plans alimentés, PR. Lecture seule. |
| `audit <mot> [précisions]` | l'unité nommée, hors ordre (les précisions priment : périmètre, `anon`, persona, décision) |
| `audit <mot> L1\|L2\|L3` | impose le niveau (sinon `niveau` du registre, relevé par l'auto-pick go-deep, annoncé en une ligne) |
| `audit <mot> contre-visite` | ré-audit par différence (METHODE §C.4.4) |
| `vérifie <GROUPE>` | §7 |

**Mots v2** (champ `declencheur`, accents facultatifs) : `totaux` X2 · `facturation` J5 · `calepinage` D3 ·
`acquisition` J0 · `lead` J1a · `crm` D1 · `sécurité` X1 · `pdf` X4 · `moteur` D2 · `chantiers` J2 ·
`stock` J3 · `documents` J6 · `parametres` X3 · `générateur` D4 · `devis` J1b · `deploy` X5 · `sav` J4 ·
`analyse` X7 · `performance` X6.

**Mots v1** (METHODE §D.4) : `leads` → `acquisition` (ou `lead leads` si dédoublonnage / attribution /
score) ; `fiche`, `cadence`, `clients`, `visites` → `lead <mot>` ; `ged`, `portail` → `documents <mot>` ;
les autres v1 ont le même nom en v2. Mot inconnu ou ambigu → `AskUserQuestion` (option recommandée
d'abord).

## 2. Procédure d'un audit (une unité)

Chaque fin de phase : commit du dossier sur la branche de claim + `git push` (c'est ce qui rend
`continue audit` possible ailleurs).

0. **Préconditions** — `git fetch origin --prune` ; `git show origin/main:docs/audits/unites.yml` ;
   si `docs/ownership.yml` existe sur main, il prime pour la propriété. Choisir l'unité (§1).
   **Claim** (§3). `python scripts/check_parked_apps.py`. Dédoublonnage : tâches ouvertes de
   `docs/PLAN2.md`, `docs/PLAN.md`, `docs/ERROR_PLAN.md`, `docs/plans/*` + `git log origin/main` ;
   groupes antérieurs dans `docs/done_task.md`. **Pile locale seulement à L2/L3** : `manage.py migrate`,
   `docker compose up -d --build frontend`, `seed_demo` (jamais `--force`), `seed_demo_company`,
   `qa_import_anonymise` à L3 ; verrou mono-écrivain et kill switch comme qa-explorer. L1 = sans pile.
1. **Charte** (METHODE §B phase 1) — avant tout constat : SHA, chemins `possede` + `perimetre_lu`,
   personas réelles, niveau justifié, jeu de données, critères retenus, étapes `P<n>.<m>`, non-objectifs.
   Questions fondateur groupées via `AskUserQuestion`.
2. **Spécification** (phase 2) — scénarios stimulus → réponse → mesure (H/M/L), table saisie →
   consommateurs, chaîne documentaire 1:N, seuils de décision, liste des détecteurs et scénarios live.
3. **Lanes** (phase 3) — une par surface indépendante, **jamais plus de 10-12** ; flotte lecture seule =
   fan-out `Workflow` même répertoire (pas de worktree) ; brief standard + **bloc de grounding verbatim**
   de `CLAUDE.md` dans chaque prompt.
4. **Exécution** (phase 4) — 4-a détecteurs (scouts haiku : commande + SHA + extrait au dossier, brut au
   scratchpad) ; 4-b lanes de jugement ; 4-c walkthrough d'une transaction réelle (L2+) ; 4-d Playwright
   par l'ORCHESTRATEUR seul (oracles qa-explorer 1-10, rejeu indépendant Chrome DevTools MCP, aucune
   capture en `anon`) ; 4-e CAAT lecture seule (+ conformance à L3).
5. **Vérification adversariale** (phase 5) — réfuteurs frais (jamais l'auteur), lentilles selon le
   niveau, **porte empirique** : chiffre client / persistance / argent / multi-société = CONFIRMÉ
   seulement sur vérification exécutée. Triage (classer → décider), jamais « corrige les N ».
6. **Conclusion** (phase 6) — rapport avec couverture chiffrée et ce qui n'a PAS été couvert ;
   non-risques avec hypothèses ; dossier `docs/audits/<AAAA-MM-JJ>-<mot>.md` (≈ 400 lignes max).
7. **Routage des tâches** (METHODE §D.3) — pour chaque tâche, propriétaire(s) de ses `Files:` (chemin
   le plus spécifique) : un seul → `docs/plans/PLAN_AUDIT_<UNITE>.md` ; plusieurs →
   `docs/plans/PLAN_AUDIT_TRANSVERSE.md` ; chemin sans propriétaire → corriger le registre dans la PR ;
   app parquée → pas de tâche. Fichier absent → le créer avec le gabarit de contrat (METHODE §D.3).
   Append-only : nouveau groupe inséré juste avant `## DONE LOG`, en-têtes `### <PREFIXE> — M0 / M1 /
   M2 / M3 / GATED`, IDs `<groupe><n>` (préfixe = champ `groupe` de l'unité auditée), jamais toucher aux
   tâches d'un autre groupe. Gardes de classe = tâches M3 (souvent dans `PLAN_AUDIT_DEPLOY.md`,
   propriétaire de `scripts/**`).
8. **Registre** — dans `docs/audits/unites.yml` : `statut: audité`, `groupe`, `plans_alimentes`, `pr`,
   `date` ; `notes` si utile ; re-score P/I si l'audit l'a justifié (dire pourquoi).
9. **PR docs-only** — `python scripts/ci_guards.py stage-names` vert ; `git fetch origin` juste avant
   le push (rebase/merge de `origin/main` si besoin, jamais de force-push) ; PR depuis `audit-<id>`,
   `gh pr merge --auto --merge --delete-branch` (merge commit) ; session auto-archive OFF. CODEMAP §10
   + `codemap_fingerprint.py --write` **seulement** si la PR édite `docs/PLAN.md`, `docs/PLAN2.md` ou
   `docs/ERROR_PLAN.md` (`docs/plans/*` et `docs/audits/*` sont hors surface plan-fingerprint). La run
   s'arrête au merge : aucun deploy.
10. **Rapport** à Reda, en français simple : constats vérifiés / réfutés / renvoyés, couverture et
    non-couvert, décisions prises, tâches par fichier de plan, coût (agents, modèle par lane), et la
    commande de build : `work on the plan audit_<unite>` (un par fichier alimenté).

## 3. Claim entre postes

- Réclamé ⇔ `origin/audit-<id>` existe ET `git merge-base --is-ancestor origin/audit-<id> origin/main`
  échoue. `git ls-remote --heads origin 'audit-*'` liste les candidats.
- Réclamer : depuis `origin/main`, branche locale `audit-<id>`, `git commit --allow-empty -m
  "audit(<id>): claim"`, `git push origin HEAD:refs/heads/audit-<id>`. Le commit vide est obligatoire
  (sinon la branche se lit comme déjà fusionnée). Push refusé → unité prise ailleurs → suivante.
- Le merge de la PR (avec `--delete-branch`) libère le claim. Seul `continue audit` reprend un claim
  vivant ; `audit next` et `loop audit` le sautent.

## 4. Routage modèle et effort (CLAUDE.md — jamais d'héritage du modèle de session)

| Rôle | `model` / effort |
|---|---|
| Orchestrateur | modèle de session (charte, triage, live, routage, registre, PR) |
| Scouts (inventaires, détecteurs, dédoublonnage) | haiku / low |
| Lanes de jugement — défaut | **sonnet / medium** |
| Lanes sur règle #4 (moteur, `/proposal`), argent, auth / multi-société, `core` sous import-linter, flux d'événements inter-apps | **opus / high** |
| Réfuteurs (contexte frais) | opus / high |
| Fable | **1-3 appels par run au total** (complétude, adjudication, revue finale ; à `vérifie` : UNE seule critique), effort high, chacun avec sa ligne DONE LOG dans le fichier de plan alimenté |

Chaque appel `Agent` porte `model:` explicite ; `CLAUDE_CODE_SUBAGENT_MODEL` reste non défini.

## 5. Constats et tâches — champs obligatoires (détail : METHODE §C)

- **Constat** `C-<GROUPE>-<NNN>` : unité, **un seul** critère C1-C14, étape, activité, déclencheur (liste
  fermée), observé / attendu, reproduction, preuve, gravité S1-S4, confiance (CONFIRMÉ = vérification
  exécutée), frères / sœurs, cause racine, correction + action corrective, effort / intérêt ; priorité
  P0-P3 fixée par l'orchestrateur ; champs du fermeur remplis à la clôture. Sans critère ⇒ OPTIONNEL.
- **Tâche** sur UNE ligne physique (forme QJR600) : verbe + fin bornée ; constat ; Given / When / Then
  avec CLAUSE PERSISTANCE et CLAUSE CLIENT ; test rouge d'abord comportemental ; test-du-test
  (mutation des lignes changées ou réversion, obligatoire P0/P1) ; source réelle non parquée, aucun mock
  interne ; tous les appelants (grep) transmettent ; jumeaux supprimés ; **listes figées** mises à jour
  (`check_naive_datetime.py`, `EntreesMoteur`) ; contrat partagé M0 (PACT10) + `@after` front → back
  (PACT11) ; déployable ; **preuve en direct jouée par l'orchestrateur du plan-run AVANT le merge** ;
  hors périmètre ; puis `Files: …` `(ROUTINE|…)` `(@after: …)` `(@lane: …)` `(@model: …)` en fin de
  ligne. Clause non applicable = `n/a` + raison, jamais omise. Chaque groupe finit par UNE tâche
  d'acceptation live du parcours.
- Tant que la garde `check_taches_cablage.py` (première tâche M3 du premier groupe v2) n'est pas sur
  `main`, l'orchestrateur relit chaque tâche exportée contre ces clauses — relecture bloquante.

## 6. `loop audit`

Lancer via le skill `loop` **sans intervalle** (mode dynamique auto-rythmé), une unité par itération :
`audit next` complet → PR auto-merge (docs-only, elle se merge seule) → itération suivante SANS attendre
le merge : la branche de claim de l'unité précédente reste vivante tant que sa PR n'est pas mergée, donc
`audit next` la saute (§3) — aucune surveillance de CI. Si la PR d'une itération précédente est rouge,
la réparer avant d'ouvrir l'unité suivante. Arrêt : plus aucune unité `à auditer` non réclamée, ou Reda
dit stop. Pas de lot : une PR par unité. En loop, une décision
fondateur non tranchée devient une tâche M1 « bloquant-fondateur » et l'audit continue. Le plafond
Fable (1-3) s'applique par itération (= par run d'unité).

## 7. `vérifie <GROUPE>`

Sur `origin/main` : retrouver dans le registre l'unité et ses `plans_alimentes`, lister les tâches
`<GROUPE>` cochées dans CES fichiers et leurs PR, la CI, l'état serveur en lecture seule
(`docs/claude-memory/prod-read-access.md`) ; une lane vérificatrice par surface (≤ 10, `model:` +
effort, grounding) compare texte de tâche ↔ commit(s) ↔ test rouge nommé (ok / partiel / non-fait /
faux / régression, avec preuve) sous les 7 critères de `docs/claude-memory/lecons-construction-qjr5.md` ;
run live du parcours (migrate + rebuild du front d'abord) ; **UNE** critique Fable sur l'ensemble des
écarts bloquants ; écarts confirmés en `ERR-<GROUPE>-*` dans `docs/ERROR_PLAN.md` après `git fetch
origin` (ce fichier EST dans la surface plan-fingerprint : CODEMAP §10 + `codemap_fingerprint.py
--write` dans le même commit). Registre : `vérifié` si zéro écart S1-S2, sinon `construit`. Sortie du
cycle : deux passages à zéro S1-S2, le second en contre-visite par différence. PR docs-only comme §2.9.

## 8. Interdits (rappel court ; liste complète METHODE §E)

Jamais de constat sans preuve exécutée sur un chiffre client / argent / persistance / multi-société ;
jamais d'agent qui vérifie son propre constat ; jamais plus de lanes pour « aller plus loin » ; jamais
une tâche dans le fichier d'un autre propriétaire ni la réécriture des tâches d'un autre groupe ; jamais
`PLAN_AUDIT_TRANSVERSE.md` en même temps qu'un plan qui possède ses fichiers ; jamais
`PLAN_AUDIT_{ACQUISITION,LEAD,CRM,DEVIS,FACTURATION,GENERATEUR,MOTEUR,CALEPINAGE}` en même temps que
`docs/plans/PLAN_CRM_VENTES.md` (contrats qui se recouvrent, à réconcilier par la session de
propriété) ; jamais la prod, jamais `seed_demo --force`, jamais d'envoi réel, jamais de deploy.
