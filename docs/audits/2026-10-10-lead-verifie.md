# Vérifie ALEA — contre-visite de clôture du groupe lead (J1a), 10/10/2026

Commande « vérifie ALEA » (METHODE §C.4.2, skill audit §5). Le groupe compte **40 tâches cochées sur 41**, soit 97 % : la
contre-visite de **clôture** (≥ 95 %) est due. Pour chaque tâche de l'échantillon, on rapproche le texte de la tâche, le ou
les commits et le test nommé, en appliquant les 7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Les écarts
confirmés sont déposés en tâches v3 dans le plan du propriétaire de leurs fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `5ea32b58b` (PR #934). Branche de claim : `verifie-alea` (commit vide `33dc0a178`, posé sur
  `5ea32b58b`).
- **Registre.** J1a `lead`, statut `audité`, groupe ALEA, dossier `docs/audits/2026-10-07-lead.md` (PR #845). Tâches ALEA
  par plan : LEAD 22, TRANSVERSE 10, DEPLOY 4, CALEPINAGE 3, GENERATEUR 1, WEB_PLAN 1.
- **Inventaire (déterministe).** 41 tâches ALEA, dont 40 `[x]`. La seule restante est ALEA26, l'acceptation live du
  groupe, ouverte. `audit_registre.py --du` : « ALEA (J1a lead) : 97 % cochées (40/41) — vérifie dû, clôture ».
- **Échantillon (graine = SHA `5ea32b58b`).** Aucune tâche P0 ou S1 cochée. 25 % du reste : **10 tâches** sur 40 —
  ALEA4, ALEA5, ALEA16, ALEA19, ALEA21, ALEA28, ALEA39, ALEA40, ALEA42, ALEA44.
- **Pile locale.** Le partage de disque de Docker Desktop était cassé : le conteneur Django partagé ne lisait plus le code.
  Un conteneur jetable `sonde-verifie` a été créé depuis l'image `erp-agentique-django_core`, avec le code de `main` copié
  dedans, sur la base de démo `erp_db`, sans migration en attente. Aucune sonde ALEA n'y a été jouée (§3).

## 1. Vérificateurs (2 agents frais, opus, effort élevé, lecture seule, même répertoire)

| Lot | Tâches | ok | partiel | autre |
|---|---|---|---|---|
| 1 | ALEA4, ALEA5, ALEA16, ALEA19, ALEA21 | 4 | ALEA4 | — |
| 2 | ALEA28, ALEA39, ALEA40, ALEA42, ALEA44 | 5 | — | — |
| **Total** | **10** | **9** | **1** | — |

Commits lus : ALEA4 `c5413c7`, ALEA5 `eef54b2`, ALEA16 `de17904`, ALEA19 `1a90342`, ALEA21 `d703086`, ALEA28 `42bdfd7df`,
ALEA39 `9540a840a`, ALEA40 `4f81b325e`, ALEA42 `674402963`, ALEA44 `5a551dbfa`.

Les points saillants :

- **ALEA4 a un code juste.** Après un envoi réussi d'une section du questionnaire public, la page fusionne ce que le client
  a envoyé dans son « vu » (`init.prefill`), après le test `result.ok`. Mais le lien entre la page et cette fusion n'est
  gardé que par une expression régulière sur le source de la page (test 3 de
  `apps/web/tests/questionnaireVuApresEnvoi.test.ts`). Une fusion faite avant de lire la réponse, ou après un refus du
  serveur, laisserait ce test vert (leçon 5).
- **ALEA21** a placé son test dans un fichier `.test.js` au lieu du `.mjs` nommé par la tâche ; le vérificateur juge
  l'écart justifié. Aucune tâche.
- **ALEA42 et ALEA44** ont été rejouées par le vérificateur du lot 2 (§2).

## 2. Tests nommés

- **Aucun test Django ni vitest n'a été rejoué par le vérificateur du lot 1.** Il a lu les commits et les tests nommés.
- **Exécuté (lot 2).** Les tests d'ALEA42 : 23 passés. Ceux d'ALEA44 : 27 passés, et sa garde est verte.
- **CI de `main` à `5ea32b58b`.** Les runs « CI » (push et merge_group) sont en succès (`gh run list`). Le run planifié
  « Release verify (full suite) » du même commit est en échec ; il n'a pas été examiné ici (§5).

## 3. Sondes

Aucune sonde. La seule tâche partielle est un écart S3 de test (ALEA4), dont le code est juste : il n'y a aucun
comportement fautif à reproduire. Aucun écart S1-S2, donc ni sonde obligatoire ni critique Fable.

## 4. Écarts retenus

Constat : C-ALEA-VER-001 (ALEA4). Fichier du propriétaire, vérifié par `check_ownership.py --owner-of` :
`apps/web/tests/questionnaireVuApresEnvoi.test.ts` et `apps/web/src/pages/questionnaire/[token].astro` → `web`, donc
`docs/WEB_PLAN.md`, section « ALEA — ÉCARTS vérifie 2026-10-10 · format v3 ».

| Tâche | Écart de | Gravité | Cause | Preuve |
|---|---|---|---|---|
| ALEA46 | ALEA4 | S3 | L5-test-affaibli : câblage page → fusion gardé par expression régulière seulement | lecture du test 3 |

ALEA46 sort l'envoi d'une section et la fusion du « vu » dans une fonction de `apps/web/src/lib/questionnaire.ts` à `fetch`
injecté, que la page appelle, et la teste par son comportement (envoi refusé : pas de fusion). Elle ne touche que
`apps/web/**`.

**Aucun S1 ni S2. Pas de critique Fable** (METHODE §C.4.2).

## 5. Optionnel (hors correction ou spec, non déposé)

- **Lot 1.** `fetchLeads.rejected` ne contrôle pas de `requestId`. Le défaut existait avant ALEA (relevé par le
  vérificateur du lot 1) ; il n'est dans le texte d'aucune tâche échantillonnée.
- **ALEA16.** Le test-du-test écrit dans la tâche est inexact (« double borne », selon le vérificateur du lot 1) ; le test
  lui-même tient.
- **ALEA4.** `ALEA4` est dans `docs/WEB_PLAN.md` et ne figure pas dans la dette gelée `docs/audits/acceptation/ALEA/_dette.yml`
  (31 ids) ; sa preuve en direct (P4.4) n'est donc suivie ni par un enregistrement ni par la dette.
- **CI.** Le run planifié « Release verify (full suite) » de `5ea32b58b` est en échec ; cause non examinée.

## 6. Couverture et non-couvert

- **Couvert.** 10 tâches sur 40 cochées (25 % tirées ; aucune P0 ou S1 cochée). Tous les commits et tous les tests nommés de
  l'échantillon ont été lus ; les tests d'ALEA42 et ALEA44 ont été exécutés.
- **Non couvert.**
  - Les 30 autres tâches cochées (hors échantillon).
  - Les preuves en direct (L7) de l'échantillon ne sont pas rejouées. Elles sont dans la dette gelée du groupe
    (`docs/audits/acceptation/ALEA/_dette.yml`, 31 ids), sauf ALEA4 (§5), et reviennent à l'orchestrateur du plan-run qui
    jouera l'acceptation ALEA26 (CLAUDE.md, étape 3-bis). ALEA46 nomme son étape (P4.4).
  - Aucune nouvelle tâche `@acceptation` : ALEA26, ouverte, reste l'acceptation du groupe.
- **Statut du registre.** Aucun écart S1-S2 : c'est le premier `vérifie` du groupe sans S1-S2. La sortie du cycle
  (METHODE §C.4.3) demande un second `vérifie` consécutif sans S1-S2. Le statut `accepté` attend la couverture
  d'acceptation (ALEA26).

## 7. Coût

- 2 vérificateurs opus : environ 0,33 M de jetons au total.
- Orchestrateur : revue ; un rédacteur pour la tâche et ce dossier.
- Aucun appel Fable.

<!-- verifie pct: 97 ecarts_s1_s2: 0 -->
