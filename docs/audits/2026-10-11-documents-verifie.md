# Vérifie ADOC — seconde contre-visite de clôture du groupe documents (J6), 11/10/2026

Commande « vérifie ADOC » (METHODE §C.4.2, skill audit §7). Le groupe compte **104 tâches cochées sur 108**
constructibles (96 %) : la contre-visite de **clôture** (≥ 95 %) est due. C'est la deuxième, après celle du 09/10
(`docs/audits/2026-10-09-documents-verifie.md`), dont les écarts ADOC173-175 sont cochés depuis et ADOC176 reste ouverte.

Pour chaque tâche de l'échantillon, on rapproche le texte de la tâche, le ou les commits et le test rouge nommé, avec les
7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S2 est prouvé par une sonde exécutée en
transaction annulée. Les écarts confirmés sont déposés en tâches v3 dans le plan du propriétaire des fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien écrit en production. Les seules actions sur le
serveur sont des lectures (compte de documents GED non indexés), faites par l'orchestrateur et annoncées dans le chat.

## 0. Préconditions

- **SHA.** `origin/main` = `6f3191ad7` (PR #948). Branche de claim : `verifie-adoc` (commit vide `2b4eb1b29`, poussé).
  CI « CI » de `6f3191ad7` : verte (run 38059434594 ; jobs front relus sur 38058990905, diff `frontend` vide avec
  `6f3191ad7`). `origin/main` a avancé pendant la run (`5fddcd489`, PR #949/#950/#914 : ENF, crm) ; les lots ont relu leurs
  ancres sur ce sha, seuls ADOC22 (doublons ramenés à 409 `unique_conflict` par ENF7) en est touché.
- **Registre.** J6 `documents`, groupe ADOC, dossier `docs/audits/2026-10-05-documents.md`. 8 plans alimentés.
- **Inventaire (déterministe).** 108 tâches ADOC constructibles, 104 `[x]`. Restent : ADOC170 (acceptation, `[BLOCKED]`),
  ADOC176 (écart du 09/10, ouverte) ; ADOC39 et ADOC149 GATED hors dénominateur.
- **Échantillon (graine = SHA `6f3191ad7f9437e786a6144a7d7ebc47408da545`).** Toutes les P0 et S1 (ADOC1, ADOC2, ADOC36,
  ADOC60), plus 25 % du reste tirés par `random.Random(int(sha, 16)).sample` (25 sur 100), plus ADOC175 ajoutée d'office
  (écart du 09/10 coché depuis, à re-vérifier ; ADOC173 et ADOC174 sont sorties au tirage). Total : **30 tâches**.
- **Pile des sondes.** Conteneur jetable `sonde-verifie-adx` (image `erp-agentique-django_core`, code de `6f3191ad7` par
  `git archive`, `STAGES.py` copié), base `erp_db` de démo, 0 migration en attente. Transaction annulée ; base inchangée
  à chaque sonde (comptes avant = après).

## 1. Vérificateurs (5 agents frais, opus, effort élevé, lecture seule, même répertoire)

| Lot | Tâches | ok | partiel | autre |
|---|---|---|---|---|
| 1 | ADOC1, ADOC2, ADOC36, ADOC60, ADOC8, ADOC10 | 6 | — | — |
| 2 | ADOC11, ADOC16, ADOC18, ADOC21, ADOC22, ADOC24 | 3 | ADOC18 (déjà ADOC176), ADOC22, ADOC24 | — |
| 3 | ADOC27, ADOC38, ADOC62, ADOC68, ADOC79, ADOC111 | 4 | ADOC38 | ADOC62 déjà-présente |
| 4 | ADOC119, ADOC120, ADOC121, ADOC122, ADOC125, ADOC129 | 5 | ADOC120 | — |
| 5 | ADOC140, ADOC143, ADOC171, ADOC173, ADOC175 | 3 | ADOC171, ADOC175 | — |
| orch. | ADOC174 | — | — | **non-faite** |
| **Total** | **30** | **21** | **7** | **2** |

**ADOC174 est cochée mais jamais construite.** Le commit « Fold ADOC174 (rapprochement des dépôts GED par mots entiers) »
(73f5f61f4) ne contient que le code d'ACRM56 (`apps/crm/selectors.py` et son test) ; `apps/ged/services.py::matcher_depot_demandes`
n'a plus été touché depuis ADOC12. La sonde C-ADOC-VER-002 reproduit toujours le faux « Présente ». Cause : fold mal
étiqueté, coche posée sur le message de commit sans relire le diff (leçon 7 : aucune preuve en direct jouée).

Points saillants des tâches jugées ok :

- **Les 4 P0/S1 tiennent** (FK bornées à la société, suppression d'un dossier non vide, garde de classe, nomenclature vendue
  au PV/BL), avec leurs 30 tests nommés verts dans la CI de `6f3191ad7`.
- **ADOC173 et ADOC175** (écarts du 09/10) : sondes C-ADOC-VER-001 et -003 rejouées, plus de fuite de jeton, 409 et une seule
  version. ADOC175 laisse un jumeau (C-ADOC-VER-006, §3).
- **Texte vieilli, code juste** : ADOC22 (doublons 409 par ENF7), ADOC68 (RESTRICT au lieu de PROTECT, justifié), ADOC38 et
  ADOC79 (branchement par `ci_guards.py`), ADOC111.

## 2. Tests nommés

- **Exécutés.** `portalScope.motDePasse.test.mjs` (3/3), gardes `check_liste_page1`, `check_ip_primitive`,
  `check_api_shapes`, `check_ecrans_atteignables`, `check_dockerfile_context.mjs` et leurs tests (25 passed).
- **Lus dans les logs CI** (aucune base de test locale) : tous les tests Django nommés par l'échantillon sont « ok » au run
  38059434594 ; les vitest au run 38058990905 / 38086024960.
- Les écarts ne viennent pas de tests rouges : ils portent sur des chemins que ces tests n'exercent pas, prouvés au §3.

## 3. Sondes et lectures (orchestrateur)

Sondes versionnées sous `docs/audits/sondes/ADOC/` ; VER-001 à 003 (format du 09/10) rejouées avec `_prelude.py`.

| Sonde | Écart de | Verdict | Sortie |
|---|---|---|---|
| `C-ADOC-VER-001.py` | ADOC173 | corrigé | listes 200, `fuite_jeton= False` sur les 3 routes |
| `C-ADOC-VER-002.py` | ADOC174 | **REPRO** | « facture.pdf » et « certificat medecine.pdf » : checklist 'manquant' → 'present', demande CIN soldée |
| `C-ADOC-VER-003.py` | ADOC175 | corrigé | « nouvelle-version pendant signature en_attente -> 409 versions après 1 » |
| `C-ADOC-VER-005.py` | ADOC22 | **REPRO** | « executer -> 500 ; demande.statut=approuvee » (document en corbeille, action archiver) |
| `C-ADOC-VER-006.py` | ADOC175 (jumeau) | **REPRO** | « regénération acceptée : meme_doc=True cree=False … versions = 2 » pendant une signature en attente |

Lecture prod (lecture seule, 10/10) : `Document` 15, `search_vector` NULL 14 ; le seul créé depuis le 06/10 (« Guide — Le
devis de pompage solaire en 10 gestes », publié par le deploy) est non indexé.

## 4. Écarts retenus

| Tâche | Constat | Écart de | Grav. | Cause | Preuve | Fichier de plan |
|---|---|---|---|---|---|---|
| ADOC177 | C-ADOC-VER-002 | ADOC174 | **S2** | non-fait : fold mal étiqueté | sonde VER-002 | `PLAN_AUDIT_DOCUMENTS.md` |
| ADOC178 | C-ADOC-VER-006 | ADOC175 | **S2** | L6-jumeau : `generer_document` sans garde de signature | sonde VER-006 | `PLAN_AUDIT_DOCUMENTS.md` |
| ADOC179 | C-ADOC-VER-005 | ADOC22 | S3 | clause-manquante : corbeille non ignorée à l'archivage | sonde VER-005 | `PLAN_AUDIT_DOCUMENTS.md` |
| ADOC180 | C-ADOC-VER-007 | ADOC24 | S3 | L6-jumeau : `versionner_si_modifie` n'indexe pas | lecture prod | `PLAN_AUDIT_DOCUMENTS.md` |
| ADOC181 | C-ADOC-VER-007 | ADOC24 | S3 | clause-manquante : « mesurer d'abord » jamais joué, 14/15 non indexés | lecture prod | `PLAN_AUDIT_DOCUMENTS.md` |
| ADOC182 | C-ADOC-VER-008 | ADOC38 | S3 | clause-manquante : helper `unpage` hors garde | repro lot 3 | `PLAN_AUDIT_DEPLOY.md` |
| ADOC183 | C-ADOC-VER-009 | ADOC120 | S3 | clause-manquante : décision sur l'utilisateur provisoire de la connexion | lecture | `PLAN_AUDIT_DEPLOY.md` |

**Constats S1-S2 : 2** (C-ADOC-VER-002 et -006), tous deux reproduits par sonde. Aucun S1 : pas de critique Fable.

Sans tâche : ADOC18 (déjà ADOC176, ouverte) ; ADOC171 (étapes 2a/3b jamais rejouées depuis ADOC172 — l'acceptation unique
du groupe est ADOC170, `[BLOCKED]`, dont l'enregistrement devra les couvrir) ; ADOC62 (déjà-présente, ACAL236).

**Routage.** `apps/ged/**` → documents. `scripts/check_liste_page1.py` (`scripts/**`) et
`frontend/src/components/MessageAccueilModal.jsx` (repli `frontend/src/components/**`) → deploy, où vivent ADOC38 et ADOC120.

## 5. Optionnel (hors correction ou spec, non déposé)

- **À sonder (lot 5, hors lot)** : `portail/views.py::rapprocher` n'attrape que `AcompteAvantDelaiLegal` ; depuis AFAC9,
  `enregistrer_paiement` lève aussi `FactureNonEncaissable` (sous-classe de `ValueError`, non traduite par
  `_exception_client`) ⇒ 500 probable sur une facture brouillon/annulée/payée ; rollback correct. Et un paiement portail
  INITIÉ rapproché sur une facture déjà soldée passe PAYE sans ligne `Paiement` (trop-perçu non tracé). Non exécutés :
  à sonder par la prochaine visite facturation.
- ADOC8 : `_servir_document_a_signer` pose `nosniff` sans CSP `sandbox` ; `versionner_si_modifie` fait passer le mime de
  l'appelant avant le mime détecté.
- ADOC1 : gardes de notification sans test ; superutilisateur sans société ⇒ 500 à la création d'un lien de dépôt.
- ADOC68 : `figer_pdf_signe` écrase `hash_contenu` ; deux demandes sur un même document ; `deposer_et_fusionner`
  (calepinage) sans garde de signature.
- ADOC120 : test-du-test de `WelcomeMoment` (deux gardes, en retirer une ne fait rien échouer).
- ADOC173 : budget de lignes dépassé (8 nettes au lieu de ≤ 4) ; oracle de la garde limité aux FK nommées `demande`.
- ADOC24 : seuls 4 des ~20 appels redondants à `update_search_vector` retirés.

## 6. Couverture et non-couvert

- **Couvert.** 30 tâches sur 104 cochées (toutes les P0/S1, 25 % tirées, ADOC175). Commits et tests nommés ; 5 sondes jouées
  par l'orchestrateur ; une lecture prod.
- **Non couvert.**
  - Les 74 autres tâches cochées — dont toute autre coche posée sur un fold mal étiqueté : la cause d'ADOC174 n'est pas
    propre à ADOC (une garde « le diff d'un commit `Fold <ID>` touche les `Files:` de la tâche » relève d'AMET, non déposée).
  - Preuves en direct (L7) : toutes les tâches de l'échantillon sont dans la dette gelée `docs/audits/acceptation/ADOC/_dette.yml`
    ou couvertes par l'enregistrement d'ADOC175 ; ADOC170 reste `[BLOCKED]`.
  - Écart ADOC183 lu sur le code, non rejoué (pas de `node_modules` dans la worktree, pas de navigateur sur la pile).
- **Statut du registre.** Après ce dépôt : 104/115 constructibles (90 %), dernière contre-visite avec 2 écarts S2 ⇒ calculé
  `audité`. Il ne passe pas `vérifié` tant qu'ADOC177-178 ne sont pas construites et qu'une contre-visite ne revient pas sans
  S1-S2.

## 7. Coût

- 5 vérificateurs opus (effort élevé) : environ 1,09 M de jetons. Aucun appel Fable.
- Orchestrateur : échantillon, conteneur et 5 sondes, lecture prod, rédaction.

<!-- verifie | groupe: ADOC | pct: 96 | ecarts_s1_s2: 2 -->
