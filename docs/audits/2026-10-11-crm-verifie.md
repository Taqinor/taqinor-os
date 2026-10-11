# Vérifie ACRM — contre-visite mi-parcours du groupe crm (D1), 11/10/2026

Commande `vérifie ACRM` (METHODE §C.4.2, skill audit §5), déclenchée par `audit_registre.py --du` : le groupe compte
**59 tâches cochées sur 68** constructibles (**86 %**) ; la contre-visite de **mi-parcours** (≥ 50 %) est due, première du
groupe. 7ᵉ de la boucle (ordre par nombre de tâches cochées décroissant) après ASAV, AFAC, ACHT, AMOT, APAR, ADEV.

La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit (lecture seule, sans pile).

## 0. Préconditions

- **SHA.** `origin/main` = `70660b1ce` (re-fetch en début d'itération). Branche de claim : `verifie-acrm`.
- **Registre.** D1 `crm`, groupe ACRM, tâches réparties `PLAN_AUDIT_TRANSVERSE.md` (48), `PLAN_AUDIT_LEAD.md` (6),
  `PLAN_AUDIT_DEPLOY.md` (5, gardes).
- **Décisions gravées.** D-ACRM-5/6 : lead en opposition exclu des audiences pub ; empreinte hachée après effacement ;
  rappel demandé lève l'opposition ; routes sans écran retirées ; salles de vente + apporteurs/deals parqués.
- **Inventaire (déterministe).** 68 tâches ACRM, 59 `[x]`.
- **Échantillon (graine = SHA `70660b1ce`).** 0 P0/S1 cochée + 25 % du reste (15 sur 59). Total : **15 tâches**.

## 1. Vérificateurs (15 agents frais, opus, effort élevé, lecture seule, même répertoire)

Un vérificateur frais par tâche (jamais l'auteur), un seul workflow fan-out.

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **14** | ACRM7, 9, 16, 18, 21, 26, 35, 40, 41, 45, 48, 53, 56, 61 |
| partiel | **1** | ACRM49 (S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

**Constats S1-S2 : 0.** Pas de critique Fable (réservée aux écarts S1).

Points saillants des tâches jugées ok (portée, opposition, RGPD) :

- **ACRM7 / ACRM9 (portée des objets secondaires et des lectures enfants).** Les actions de détail et les viewsets enfants
  bornent leur queryset à la PORTÉE du rôle (pas seulement la société) via `scope_queryset` / `leads_en_portee` ; un objet
  hors portée est traité comme absent (404, pas de divulgation d'identité). Tests comportementaux HTTP + DB à deux rôles.
- **ACRM16 / ACRM18 (opposition & plafond de réveil).** Un lead `ne_plus_contacter` est exclu des réveils saisonniers sur
  les deux portes (mono-lead + lot), AVANT la troncature au plafond ; deux passages ne re-sélectionnent plus les mêmes ids.
- **ACRM21 (RBAC par action déclarée).** Le repli brut `IsAdminRole` est remplacé par `declared_action_permissions` ;
  consolidation/export répondent selon leur décorateur. Tests comportementaux à plusieurs rôles.

## 2. Tests nommés

- Les 14 tâches jugées ok ont un test nommé **présent et comportemental** (assert sur l'état serveur / DB, à deux rôles).
  Les mentions de leçons (2/3/4/6) relevées par des vérificateurs sont des notes de contexte sans divergence — verdict ok.
  Non rejoués localement (lecture seule, sans pile) : raisonnés par lecture ; vert de la CI de `70660b1ce`.

## 3. Sondes

Aucune sonde déposée : l'unique écart (ACRM49) est S3 (faux-négatif d'une garde CI, sans effet client/argent). Les clauses
RGPD/portée/opposition des tâches échantillonnées ont été jugées tenues par lecture du code de production.

## 4. Écarts retenus

| Tâche | Constat | Écart de | Grav. | Cause | Suite |
|---|---|---|---|---|---|
| ACRM69 | C-ACRM-VER-001 | ACRM49 | S3 | faux-négatif : `crm/clients/segments` (route `@action` sans appelant, catégorie « retirée » D-ACRM-6) non signalée car `check_api_contract.compatible` laisse un `<pk>` détail avaler le littéral `segments` ; test-du-test d'ACRM49 entérine le masquage — mine la garde d'ACRM68 | tâche v3 déposée (`PLAN_AUDIT_DEPLOY.md`, propriétaire deploy) |

**Constats S1-S2 : 0.**

## 5. Optionnel (non déposé)

- Les notes de leçons sur les tâches ok (ACRM7/9/45/53/56) sont des observations des vérificateurs sans divergence
  comportementale ; non déposées.
- Le RETRAIT de la route `crm/clients/segments` elle-même relève d'ACRM64/ACRM67 (TRANSVERSE, ouvertes) ; ACRM69 ne corrige
  que le trou de détection de la garde.

## 6. Couverture et non-couvert

- **Couvert.** 15 tâches sur 59 cochées (0 P0/S1 au groupe + 25 %). Commits, tests nommés, code de production, décisions.
- **Non couvert.** Les 44 autres tâches cochées ; aucun aller-retour en direct (lecture seule, sans pile).
- **Statut du registre.** Après ce dépôt : 59/68 cochées (86 %), contre-visite mi-parcours **sans écart S1-S2** (1 écart S3
  déposé en tâche). La clôture (≥ 95 %) et la sortie du cycle restent dues plus tard.

## 7. Coût

- 15 vérificateurs opus (effort élevé) : **≈ 1,22 M de jetons**, 281 appels d'outil, ≈ 29 min. Aucun appel Fable.
- Orchestrateur : échantillon déterministe, triage des 15 verdicts, vérification du faux-négatif ACRM49 (route `segments`
  vs ACRM68), rédaction.

<!-- verifie | groupe: ACRM | pct: 86 | ecarts_s1_s2: 0 -->
