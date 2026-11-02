# Vérifie ASTK — deuxième contre-visite de clôture du groupe stock (J3), 01/11/2026

Commande `vérifie ASTK` (METHODE §C.4.2, skill audit §5). Elle est lancée par la session d'orchestration du `loop audit`
du 01/11. Le groupe compte **199 tâches cochées sur 199** constructibles. Toutes les tâches ÉCART de la contre-visite du
10/10 (`docs/audits/2026-10-10-stock-verifie.md`, ASTK244-249 et ASTK251-253) sont cochées ; ASTK250 reste GATED
(D-ASTK-VER-1). `audit_registre.py --du` ne la liste pas, car sa règle ignore la contre-visite qui suit le drainage des
écarts. Le groupe ne sort du cycle qu'après deux contre-visites consécutives sans écart S1-S2 : celle-ci est donc due.

Pour chaque tâche de l'échantillon, on rapproche le texte, le ou les commits, le test nommé et le code de `main`. La
grille est celle des 7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par
une sonde exécutée en transaction annulée. Les écarts confirmés sont déposés en tâches v3 dans le plan du propriétaire.

La contre-visite n'a rien construit. Elle n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** Échantillon et vérificateurs : `origin/main` = `56d5b623a` (PR #1197). À la rédaction, `origin/main` =
  `70db6e071`. Les vérificateurs ont contrôlé qu'aucun fichier cité dans leurs verdicts n'a changé entre les deux.
  Branche : `verifie-astk-0111`.
- **Inventaire (déterministe).** 199 tâches ASTK `[x]` dans les plans actifs. Script de tirage :
  - P0/S1 : regex `gravité S1` / `Priorité : P0` ;
  - plus toutes les ÉCART du 10/10 ;
  - plus 25 % du reste par `random.Random(int(sha, 16)).sample` sur les ids triés, plafonné à 48.
- **Échantillon (graine = `56d5b623a`), 48 tâches.**
  - **Imposées (40)** : ASTK1-9, 32, 33, 37-43, 59, 60, 81-83, 98, 108, 109, 120, 129, 135, 140, 239, 244-249, 251-253.
  - **Tirées (8)** : ASTK11, 22, 55, 85, 100, 198, 211, 223.
  - **Par fichier** : STOCK 39, CHANTIERS 3, FACTURATION 2, DEPLOY 1, ANALYSE 1, DEVIS 1, TRANSVERSE 1.
- **Pile des sondes.** Conteneur partagé `erp-agentique-django_core-1` (il monte le checkout principal, à `56d5b623a`
  puis `c6ab9b58e`, deux SHA de `main`). Une sonde à la fois, par le verrou commun à deux places. Chaque sonde tourne en
  transaction annulée ; base inchangée à chaque rejeu.
- **Incident.** Le moteur Docker de la machine est tombé pendant la contre-visite (API 500, VM WSL arrêtée, RAM libre
  ≈ 1 Go). Il est revenu après un redémarrage par le fondateur. Les sondes coupées pendant la panne ont été rejouées ;
  une panne n'est jamais comptée comme verdict.

## 1. Vérificateurs (4 agents frais, opus, effort élevé, lecture seule, même répertoire, 12 tâches chacun)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **44** | dont texte vieilli (refus 400 → 409 d'ERR-ENF11, ou ligne de plan restée « partiel/BLOCKED ») : ASTK1, 22, 39, 59, 82, 85, 100, 135, 248 |
| déjà-présent | **1** | ASTK211 (ancienne `[BLOCKED: hors périmètre]` : les deux chemins J3 existent, SPL288 et SPL87) |
| partiel | **2** | ASTK11 (S2, L6), ASTK239 (S3, L7) |
| régression | **1** | ASTK198 (S2, L4) |
| non-fait / faux | 0 | — |

**Les écarts du 10/10 tiennent sur `main` :**
- ASTK244, une vente = une sortie : sonde VER-001 rejouée, 10 sorties / stock 20 ;
- ASTK245, rapprochement sur la quantité entrée : VER-002 rejouée, `exception` ;
- ASTK246, acomptes et avoirs : VER-003 rejouée, 403 ;
- ASTK248, quarantaine au scanner : VER-004 rejouée, 409, stock 15 ;
- ASTK249, ASTK251-253 : par lecture et test nommé.

**Autres preuves exécutées :**
- `check_fk_scoping.py` : OK, 462 FK ;
- `scripts.tests.test_check_fk_scoping` : 24 tests OK ;
- table AST de la garde ASTK129 : `oublies []`, `perimes []`.

## 2. Sondes

| Sonde | Tâche | Verdict | Observé (code de `main`, transaction annulée) |
|---|---|---|---|
| `C-ASTK-VER-001.py` (10/10) | ASTK244 | réfuté | « livrer-partiel=200 sorties après livraison=4 après facture=10 après Installé=10 stock=20 (attendu 10 / 20) » |
| `C-ASTK-VER-002.py` (10/10) | ASTK245 | réfuté | « quantite_appliquee=10 … statut_controle='exception' » |
| `C-ASTK-VER-003.py` (10/10) | ASTK246 | réfuté | Commercial : 403 « Permission « achats_payer » ou « prix_achat_voir » requise » sur la liste et `ouverts/` |
| `C-ASTK-VER-004.py` (10/10) | ASTK248 | réfuté | « scanner sortie 12 -> 409 … 10 unité(s) en quarantaine, 5 disponible(s) hors quarantaine ; stock 15 » |
| `C-ASTK-VER-101.py` | ASTK11 | **REPRO** | rôle Commercial, `can_view_buy_prices=False` : `cles_montant=[]` mais `motif_ecart='Rapprochement 3 voies hors tolérance : facturé 1 234,56 HT pour 0,00 HT reçus au prix du BCF (écart +1 234,56 HT …)'` sur les 4 URL (stock et achats, liste et détail), 200 |
| `C-ASTK-VER-102.py` | ASTK1, 8, 22, 32 | réfuté | garde ASTK8 : 88 serializers, non bornés `[]` ; produit de B = id absent, corps identiques ; création : 1 mouvement « Stock initial » de 7 ; PATCH `quantite_stock` ignoré ; PATCH `statut=recu` ignoré (relu brouillon) |
| `C-ASTK-VER-201.py` | ASTK59, 60 | réfuté | réception de 12 sur 10 : 201, 2ᵉ brouillon 409 ; confirmation : stock 10, `quantite_appliquee` 10, provision 600, facture 600 HT ; annulation : stock 5, reçu 0 |
| `C-ASTK-VER-302.py` | jumeau d'ASTK11 (signalé par le rédacteur) | **REPRO** | Commercial : `checklist-cloture` 200, facture en exception servie avec `montant_ttc` 1481.47 et le `motif_ecart` chiffré (`AchatsParametresViewSet` en `IsAnyRole`) |
| `C-ASTK-VER-301.py` | ASTK198 | **REPRO** | « document_reference(declaration)='BROUILLON-684' ; facture emise … reference='FAC-202611-0001' ; releve.document_reference='BROUILLON-684' ; liste.facture_reference='BROUILLON-684' liste.facture_id=None » |

La sonde VER-102 a été corrigée par l'orchestrateur avant son verdict, sans changer son attendu : le corps comparé
contenait le `request_id`, et la création de produit était tentée par un rôle sans ce droit.

## 3. Écarts retenus (déposés dans `docs/plans/PLAN_AUDIT_STOCK.md`, section « ASTK — ÉCARTS vérifie 2026-11-01 »)

| Tâche | Écart de | Grav. | Cause | Preuve |
|---|---|---|---|---|
| ASTK255 | ASTK11 | **S2** | L6, jumeau oublié : le texte `motif_ecart` du rapprochement 3 voies porte les montants d'achat et reste servi sans `prix_achat_voir` (4 URL factures fournisseur) ; même cause sur `checklist-cloture`, qui sert aussi `montant_ttc` | sondes VER-101, VER-302 |
| ASTK256 | ASTK198 | **S2** | L4 : ATOT27 a rendu provisoire la référence d'une facture brouillon. La déclaration de consignation garde « BROUILLON-<id> » après l'émission. Le relevé remis au client imprime un numéro qui n'existe plus, et `facture_id` est perdu au rechargement | sonde VER-301 |
| non déposée | ASTK239 | S3 | L7 : acceptation du groupe cochée avec un enregistrement de 8 étapes. P1 et P4.5 ne sont pas joués, la dette d'écran ne rétrécit pas, et les gestes « Preuve en direct » d'ASTK244, 248, 249 et 251 ne sont couverts nulle part | lecture (`check_acceptation.py` OK mais aveugle à ces ids) |

**Constats S1-S2 : 2** (3 sondes REPRO, VER-101 et VER-302 étant une même cause). Aucun S1 : pas de seconde lentille ni de critique Fable (METHODE §C.4.2).

**Écart S3 non déposé.** Le correctif de l'acceptation ASTK239 touche `frontend/e2e/acceptation/astk.spec.js`, qui
appartient au propriétaire deploy, et une tâche `@acceptation` n'est jouée que par l'orchestrateur d'un plan-run. Il est
signalé à la session d'orchestration du `loop audit` plutôt que déposé dans le plan stock. Il faudra soit compléter la spec
(P1, P4.5, gestes d'ASTK244, 248, 249, 251) avec un nouvel enregistrement, soit décocher ASTK239 (METHODE §C.4.1).

## 4. Optionnel (hors correction ou spec, non déposé)

- **ASTK43.** ERR-ASTK63 (895724d17) a réintroduit deux appels directs à `average_cost_with_source` dans
  `stock/services.py::definir_frais_annexes_ligne_bcf`. Ils servent seulement au texte du chatter et n'ont aucun effet sur
  la valorisation.
- **ASTK39.** Une ligne de comptage tournant renvoyée par l'API avec la valeur pré-remplie garde le snapshot de
  génération. Aucun écran n'envoie ce PATCH.
- **Reliquats du 10/10.** Les lecteurs de `ligne.quantite` sont toujours là dans `services_catch_weight.py`.
- **Quarantaine.** La consommation terrain F11 (`installations/field_capture.py::validate_consommation`) sort le stock
  sans lire la quarantaine. C'est une question métier voisine de D-ASTK-VER-1, non sondée.
- **Factures fournisseur.** Le tri `ordering=montant_ttc` reste ouvert sans `prix_achat_voir` : on peut classer les
  factures sans voir leurs montants.
- **ASTK83.** Le dialogue compte les produits non archivés, alors que le serveur refuse aussi pour des produits archivés.
- **ASTK120/98.** L'idempotence est clé sur (référence, produit) : deux lignes du même produit dans une réception, non
  sondé.

## 6. Couverture et non-couvert

- **Couvert.** 48 tâches sur 199 cochées. Commits et tests nommés lus. Neuf sondes jouées sur le code de `main` : 3 REPRO,
  6 réfutées (dont les quatre du 10/10).
- **Non couvert.**
  - Les 151 autres tâches cochées.
  - Aucun test Django ni vitest exécuté par les vérificateurs (pile en panne pendant leur lecture). Leur vert est celui
    de la CI de `main`.
  - Aucun rejeu à l'écran (écart S3 d'acceptation non déposé, §3).
- **Statut du registre.** Après ce dépôt : 199 cochées sur 201 constructibles (ASTK255-256 ajoutées), contre-visite avec
  **2 écarts S1-S2**. Le cycle n'est pas sorti : il faut deux contre-visites consécutives à zéro S1-S2 après ASTK255-256.

## 7. Coût

- 4 vérificateurs opus (effort élevé) : environ 0,93 M de jetons.
- 1 rédacteur opus : 2 tâches v3.
- Orchestrateur : tirage déterministe, rejeu sériel de 9 sondes (dont 1 corrigée, 1 écrite), triage, rédaction.
- H0 S0 O5 F0

<!-- verifie | groupe: ASTK | pct: 100 | ecarts_s1_s2: 2 -->
