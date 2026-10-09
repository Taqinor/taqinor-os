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

## 2. Verdicts des lanes (10 agents frais, 182 tâches, 198 commits lus, 160 tests lus, 11 sondes)

| Lane | ok | partiel | faux | Écarts (gravité) |
|---|---|---|---|---|
| L1-CATALOGUE | 14 | 3 | 0 | ASTK229 S2 · ASTK231 S3 · ASTK233 S4 |
| L2-PRIX | 9 | 1 | 0 | ASTK12 S3 |
| L3-MVT-VALO | 17 | 3 | 0 | **ASTK39 S1** · ASTK205 S3 · ASTK209 S3 |
| L4-RESA-COUTURES | 18 | 0 | 0 | — |
| L5-BCF-RECEPTION | 12 | 3 | 0 | ASTK58 S3 · ASTK63 S3 · ASTK192 S4 |
| L6-FACF-PAIEMENTS-CONTRATS | 21 | 3 | 0 | ASTK163 S3 · ASTK165 S3 · ASTK166 S3 |
| L7-FOURNISSEURS-PORTAIL | 20 | 1 | 0 | ASTK226 S3 |
| L8-TENANT-ROLES | 20 | 1 | 0 | ASTK6 S2 |
| L9-WMS | 11 | 4 | 1 | **ASTK221 S2 (faux)** · ASTK196 S3 · ASTK200 S3 · ASTK216 S3 · ASTK222 S3 |
| L10-ECRANS-GARDES-DECISIONS | 17 | 3 | 0 | ASTK15 S3 · ASTK53 S3 · ASTK232 S3 |
| **Total** | **159** | **22** | **1** | 1 S1 · 3 S2 · 17 S3 · 2 S4 |

Aucun « non-fait » ni « régression » : tout ce qui est coché est présent à HEAD et non revert. Les 23 écarts
sont des livraisons partielles ou un test factice, tous relus par l'orchestrateur à HEAD (fichier:ligne
ci-dessous) ; les 4 bloquants ont été rejoués ou sondés en direct (§3).

**Bloquants (S1-S2).**
- **ASTK39 — S1 (critères 4, 6).** Comptage cyclique (installations) : `views/comptage.py:98-101`
  snapshote `quantite_theorique = produit.quantite_stock` à l'AJOUT de la ligne, `serializers.py:1830` la
  garde en lecture seule, `terminer` applique écart = compté − théorique(ajout) au stock LIVE. Le chemin
  session d'inventaire (stock) est livré (`test_astk_ecart_inventaire_regle`) ; la tâche se déclare
  « partiel 07/10 » mais est cochée, sans tâche de suite chez le propriétaire chantiers.
- **ASTK229 — S2 (critères 4, 5).** `KitsStock.jsx:135-136` lit `data?.revisions ?? []` ; l'API
  (`views/kit.py:119-127`) renvoie un tableau nu (le contrat `kits_stock.json` le dit) → « Aucune
  révision » toujours. Sonde L1 (rollback) : 200, liste nue, pas de clé `revisions`.
- **ASTK221 — S2, faux (critères 5, 6).** La liste des dépôts de consignation imbrique
  `DeclarationConsommationSerializer` (`views/negoce.py:35-37`, sans `facture_id`/`facture_reference`) ;
  seule la réponse du POST `declarer` (`:207`) les porte → après F5, `ConsignationsPage.jsx:44-49`
  affiche « Facturée » sans référence ; le test injectait la réponse du POST dans la liste.
- **ASTK6 — S2 (critères 4, 5).** `creer_vague_depuis_besoins` (`services_wms.py:285-286`) écrit
  `installation_id` / `bon_commande_id` tels que reçus : un chantier ou BCF d'une autre société est
  accepté (201), un id absent viole la FK (500) — réponse différente de l'id absent, contrairement au
  Then. Sonde en direct §3.

**S3 (tâche si effort ≤ M) — tous relus à HEAD.** ASTK12/ASTK15 (`CatalogueAchatPicker.jsx:172`
`?? 0` → « 0,00 DH » pour un rôle sans `prix_achat_voir`) · ASTK209 (`StockList.jsx:964` `parseInt`,
`CatalogueTable.jsx:125-130` accepte 7.5 → 7 posé en silence) · ASTK59-jumeau
(`services_qualite_reception.py:159` bloque `ligne.quantite` saisie, pas la quantité appliquée) · ASTK58
(jumeaux PESEE / cross-dock non traités à l'annulation) · ASTK63 (garde « coût figé » absente sur
`definir_frais_annexes_ligne_bcf`, mais l'appliquer casserait le coût débarqué DC38 — décision) · ASTK205
(SORTIE sans lot non marquée au registre, tâche auto-déclarée partielle) · ASTK226 (auteur de résolution
non posé par le serveur) · ASTK222 (référence de l'avoir RFA perdue après F5) · ASTK196/200/216 (400 des
contrats WMS non affirmés, corps d'erreur retapé) · ASTK163/165/166 (clés de contrat jamais affirmées via
APIClient) · ASTK231 (3 écrans sans test de la confirmation maison) · ASTK53 (dette de concurrence figée
sans tâche) · ASTK232 (baseline non resserrée). **S4, sans tâche :** ASTK233, ASTK192.

**Constat transversal (critère 7).** Aucune des 182 tâches n'a de preuve en direct : les DONE LOG disent
« CI = le gate » ou « docker éteint » ; `docs/audits/acceptation/` ne contient aucune trace ASTK ; ASTK239
(acceptation) est restée ouverte. Le run live ci-dessous est la première exécution du parcours.

## 3. Run live (orchestrateur, pile locale `erp-agentique`, `main` = `f3716e3f0`)

Pile déjà à `main` (code Django monté en direct, image front postérieure au dernier commit front,
0 migration en attente, `check_dockerfile_context.mjs` vert) ; sondes HTTP par le client de test Django
(JWT du compte, `HTTP_HOST=localhost`) dans une transaction ANNULÉE sur la base de démo locale ; écrans par
Playwright MCP en `demo_admin` ; aucune donnée de production touchée, aucun envoi réel. Trace brute :
scratchpad `live/RESULTATS.md` + `live/*.py` (sondes re-jouables).

| Scénario | Résultat |
|---|---|
| **P7 écrans** — 26 routes `/stock/**` (catalogue, achats, WMS, négoce) | 26 rendues, 0 `console.error`, 0 réponse ≥ 400 sur `/api/`, 0 dialogue natif, 0 error boundary (oracles qa-explorer 1-4, 8) |
| **S-E étanchéité** — GET détail de chaque route du routeur stock avec un id de la société 6 depuis la société 2 (55 routes ; 7 ont des objets en société 6 : produits, catégories, mouvements, marques, emplacements, fiches techniques, catalogue-achat) | 7/7 → 404, même `detail` que pour un id absent (corps différents par le seul `request_id`), 0 fuite, 0 403. Les 48 autres routes n'ont aucun objet en société 6 (couvertes par les tests ASTK1-9/212 en CI) |
| **S-B aller-retour produit** (C-ASTK-005) — GET → mouvement +5 par le service → PUT du payload lu sans le toucher | stock 125 conservé (plus de retour à 120) ; `PATCH quantite_stock=999` ignoré (stock 125) |
| **S-C `prix_achat`** (garde ASTK14 rejouée sur les données démo) — compte Commercial sans `prix_achat_voir` | 235 routes GET découvertes, 103 réponses JSON, **0 clé d'achat** ; contrôle positif admin : clés vues sur 17 routes |
| **S-A prix** (D-ASTK-1, ASTK140/141) — prix catalogue 1 890 → 2 079 | brouillon recalé à 2 079 ; envoyé figé à 1 890 avec note persistée dans `/historique/` (« devis envoyé conservé ») ; événement périmé (2 079 → 1 890) ignoré, brouillon reste à 2 079 |
| **S-D achat bout en bout** — BCF 10 × 100 → envoyer → réception 4 → sur-réception 10 → réception 6 → facturer → acompte → paiement | +4 puis sur-réception **plafonnée** au reste dû (stock exactement +10, réception suivante refusée « reste dû 0 », ASTK59) ; facture 4 × 100 = 480 TTC ; 2e facturation de la même réception refusée ; BCF/facturer refusé (pas de ligne « sur commande ») ; acompte créé AVANT la facture imputé (solde 180, « partiellement payée », acomptes ouverts vides, ASTK106) ; paiement du solde → `solde_du` 0, statut « payée » |
| **S-F correction après coup** | PATCH montant d'une facture payée → 400 « montants verrouillés » ; `reviser` quantité 3 < reçu 10 → 400 ; PATCH `statut=brouillon` d'un BCF envoyé → 400 (« utilisez réviser ») ; annuler une réception confirmée non facturée → stock restauré |
| **ASTK39 comptage cyclique** (S1) | stock 120 → SORTIE 20 → 100 ; ligne ajoutée avant la sortie (théorique 120), compté 100, `terminer` → AJUSTEMENT −20 posté → **stock 80** au lieu de 100 — **reproduit** |
| **ASTK6 vague de picking, chantier étranger** (S2) | voir ligne ci-dessous |

Lecture : les 9 S1 de l'audit du 06/10 rejoués ou couverts — C-ASTK-005 (S-B), 012 (sur-réception), 001/055
(S-E), 021/022 (S-A), 038 (double facturation refusée) tiennent ; C-ASTK-007 (comptage cyclique) ne tient
que sur le chemin session d'inventaire (ASTK39, écart S1 ci-dessus) ; C-ASTK-008 (valorisation), 017
(suppression produit), 028 (double sortie) : vérifiés par lecture + tests nommés (L3, L1, L4), non rejoués
à l'écran. **Réfuté :** le 403 `achats_commander` du `demo_admin` local vient du rôle « Directeur » non
réaligné parce que `init_roles` n'a pas tourné localement depuis le merge ; en prod (lecture seule, 16
rôles), seuls Commercial responsable / Commercial / Portail client manquent les codes — voulu (D-ASTK-3).
**Hors périmètre :** `/proposal` d'un devis synthétique sans onduleur → 500 (règle du moteur, ventes).

## 4. Critique Fable

_(rempli à la fin du run)_

## 5. Écarts retenus → `docs/ERROR_PLAN.md`

_(rempli à la fin du run)_

## 6. Couverture et non-couvert

**Couvert.** 182/182 tâches cochées relues contre leur texte, leur(s) commit(s) et leur test nommé
(198 commits lus, 160 tests lus, 11 sondes rollback par les lanes) ; les 23 écarts relus à HEAD par
l'orchestrateur (fichier:ligne) ; 26 écrans stock joués ; 6 scénarios S-A→S-F + ASTK39 + 7 routes S-E
rejoués en direct ; prod lue (commit, migrations, 16 rôles) ; une critique Fable (§4).

**Non couvert — à faire avant un passage « vérifié ».**
- Les tests nommés n'ont pas été ré-exécutés localement (lecture seule, pas de DB de test) : leur vert
  est celui de la CI des 7 PR (toutes vertes) et de `main` — pas une exécution de ce run.
- Preuve en direct des écrans WMS/négoce (P6 : vague → prélèvement → unité scellée → expédition ; rappel
  → lot bloqué ; consignation → facture ; créneau fournisseur → planning ; kiosque) : écrans rendus, flux
  NON joués ; portail fournisseur à jeton et kiosque non joués ; PDF BCF (devise, TVA 10 %) non ouverts.
- Rejeu à l'écran de C-ASTK-008 (valorisation à date), 017 (suppression produit), 028 (double sortie
  facture directe + « Installé ») : vérifiés par lecture + tests nommés, non rejoués.
- Sonde live ASTK6 (vague de picking, chantier étranger) non aboutie : deux tentatives gelées sur la pile
  locale (processus idle après le middleware identity, hors base de données) — écart tenu par la lecture
  du code à HEAD (`services_wms.py:282-283`).
- S-E : 48 routes stock sans objet en société 6 dans la base de démo (couvertes par les tests ASTK1-9 /
  212 en CI, non sondées ici) ; `apps/achats` non balayé par la sonde S-E (routeur `apps.stock.urls`
  seulement ; achats est couvert par `test_astk_fk_achats`).
- Contre-vérification des 11 verdicts « ok » de la lane L8 lus sans leur diff (état à HEAD seulement).
- Pile locale : `init_roles` jamais relancé après le merge (rôle « Directeur » démo sans les 4 codes
  achats/catalogue) — réaligné dans la transaction annulée des sondes S-D, comme le fait le déploiement.
