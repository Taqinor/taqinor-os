# Vérifie ASTK — contre-visite post-build du groupe stock (J3), 09/10/2026

Commande « vérifie ASTK » (METHODE §C.4.3, skill audit §7). Vérification des 182 tâches ASTK cochées
sur `origin/main` : texte de tâche ↔ commit(s) ↔ test rouge nommé, sous les 7 critères de
`docs/claude-memory/lecons-construction-qjr5.md`, puis rejeu en direct du parcours sur la pile locale,
une critique Fable sur les écarts bloquants, écarts confirmés déposés en `ERR-ASTK*` dans
`docs/ERROR_PLAN.md`. Aucune construction, aucun deploy, aucune donnée de production touchée.

## 0. Préconditions

- **SHA.** `origin/main` = `f3716e3f0` (09/10/2026 02:40 UTC, PR #891). Branche de claim `audit-J3`
  (commit vide `c5ec74d2d`). Prod (`/opt/taqinor-os`, lecture seule via SSH) : même commit `f3716e3f0`,
  12 conteneurs up, `showmigrations stock achats installations` : 0 migration en attente.
- **Registre.** J3 `stock`, statut `audité`, groupe ASTK, `plans_alimentes` = PLAN_AUDIT_STOCK,
  CHANTIERS, DEPLOY, DEVIS, FACTURATION, SECURITE, ANALYSE, TRANSVERSE, DOCUMENTS (PR #820, 06/10).
- **Inventaire (déterministe, `scripts` du scratchpad).** 185 tâches ASTK dans ces 9 fichiers :
  182 `[x]`, 2 `[BLOCKED: hors périmètre]` (ASTK210 core/event_catalog — sécurité/paramètres ;
  ASTK211 docs/ownership.yml — sans propriétaire), 1 `[ ]` (ASTK239, acceptation live du groupe, jamais
  jouée par un plan-run : aucune trace sous `docs/audits/acceptation/`, aucune capture citée).
  Par fichier : STOCK 152, CHANTIERS 16, DEPLOY 4, DEVIS 3, SECURITE 2, FACTURATION 2, ANALYSE 1,
  TRANSVERSE 1, DOCUMENTS 1. Modèle de build déclaré : 117 sonnet, 65 opus.
- **Commits et PR.** Chaque tâche cochée est citée par ≥ 1 commit sur `main` ; 7 PR de merge, toutes
  vertes (checks requis + shards) : #835 (dev-audit_stock, 77 tâches), #850 (dev-all, 44), #856
  (dev-all-w2, 49), #864 (dev-all-w5, 15), #839 (4), #848 (2), #851 (1). CI de `main` à `f3716e3f0` :
  verte (CI, semgrep, bandit).
- **Gardes.** `check_parked_apps.py` : OK. `frontend/scripts/check_dockerfile_context.mjs` sur la
  checkout principale à `f3716e3f0` : vert (skipped 0, todo 0).
- **Pile locale.** Conteneurs `erp-agentique-*` (checkout `C:\dev\taqinor-os` sur `main` =
  `f3716e3f0`, code Django monté en direct), image frontend construite le 09/10 00:45 UTC, postérieure au
  dernier commit `frontend/` de `main` (582029681, 00:36 UTC) → pas de rebuild nécessaire ;
  `showmigrations --plan` : 0 migration en attente. Sociétés 2 `taqinor-demo` (demo_admin) et 6
  `taqinor-demo-full` (demo_admin_full) présentes ; société 4 `taqinor-anon` présente, jamais lue.
- **Dédoublonnage.** `docs/ERROR_PLAN.md` : 0 ligne `ERR-ASTK*` ; une ligne ERR-BC-LIVRER-PARTIEL-
  DOUBLE-SORTIE (trouvée par la garde ASTK129, cochée).

## 1. Plan des lanes (lecture seule, même répertoire, agents frais)

| Lane | Tâches | Modèle / effort | Surface |
|---|---|---|---|
| L1-CATALOGUE | 17 | sonnet / medium | produit, catégories, kits, seed, écrans catalogue |
| L2-PRIX | 10 | opus / high | prix catalogue → devis, `prix_achat`, tarifs fournisseur |
| L3-MVT-VALO | 20 | opus / high | mouvements, valorisation, inventaires, lots, emplacements |
| L4-RESA-COUTURES | 18 | opus / high | réservations chantier, coutures installations/facturation, événements |
| L5-BCF-RECEPTION | 15 | opus / high | BCF, réception, créneaux, PDF BCF |
| L6-FACF-PAIEMENTS-CONTRATS | 24 | opus / high | factures fournisseur, acomptes, paiements, consignation, contrats M0 |
| L7-FOURNISSEURS-PORTAIL | 21 | sonnet / medium | fiche fournisseur, KPI, portail à jeton, pages publiques |
| L8-TENANT-ROLES | 21 | opus / high | FK bornées société, permissions achats, journal |
| L9-WMS | 16 | sonnet / medium | casiers, picking, qualité, négoce |
| L10-ECRANS-GARDES-DECISIONS | 20 | sonnet / medium | écrans achats, gardes M3, décisions |

Brief commun : bloc de grounding de CLAUDE.md, les 7 critères, verdict par tâche
(ok / partiel / non-fait / faux / régression) avec preuve re-jouable, sondes uniquement en transaction
annulée sur la pile démo, aucune écriture dans le dépôt. Rapports complets au scratchpad
(`verif/<lane>.md`), synthèse structurée en JSON.

## 2. Verdicts des lanes

_(rempli à la fin du run — voir §2 ci-dessous)_

## 3. Run live (orchestrateur, pile locale)

_(rempli à la fin du run)_

## 4. Critique Fable

_(rempli à la fin du run)_

## 5. Écarts retenus → `docs/ERROR_PLAN.md`

_(rempli à la fin du run)_

## 6. Couverture et non-couvert

_(rempli à la fin du run)_
