# Vérifie ASEC — contre-visite de clôture du groupe sécurité (X1), 01/11/2026

Commande `vérifie ASEC` (METHODE §C.4.2, skill audit §5), lancée par `loop audit` (troisième itération). Après les
contre-visites ACHT (PR #1180, mergée) et AMOT (PR #1185), `audit_registre.py --du` liste quatre groupes dus en clôture :
ASEC 54/54, AANA 51/51, AGNR 47/48, ATOT 35/35. Ils passent par nombre de tâches cochées décroissant : ASEC d'abord. La
contre-visite précédente, du 11/10 (`docs/audits/2026-10-11-sécurité-verifie.md`), était à mi-parcours (94 %).

Pour chaque tâche de l'échantillon, on rapproche le texte, les commits, le test nommé et le code de `main` avec les
7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par une sonde jouée en
transaction annulée, à deux comptes ou deux rôles. Les écarts confirmés deviennent des tâches v3 dans le plan du
propriétaire des fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `ba577e26a` (PR #1179), re-fetch en début d'itération. Branche de claim : `verifie-asec-cloture`
  (commit vide, poussé).
- **Registre.** X1 `sécurité`, groupe ASEC, dossier `docs/audits/2026-10-07-securite.md`, 54/54 cochées.
- **Inventaire.** 53 tâches ASEC `[x]` dans les plans actifs, réparties sur 13 fichiers (19 dans `PLAN_AUDIT_SECURITE.md`),
  plus une au registre de `docs/done_task.md`.
- **Échantillon (graine = SHA `ba577e26ad`, déterministe).** Il compte **31 tâches** :
  - les 24 tâches cochées portant S1 ou P0 : ASEC2, 3, 4, 6, 7, 9, 11, 13, 19, 21, 22, 24, 26-30, 32-35, 37, 41, 42 ;
  - 25 % du reste, soit 7 sur 29, tirées par `random.Random(int(sha, 16)).sample` sur les ids triés : ASEC10, 15, 25,
    38, 43, 47, 48.
- **Pile des sondes.** Conteneur jetable `sonde-verifie-asec` (image `erp-agentique-django_core`, code de `main` copié par
  `git archive`). Docker Desktop, arrêté en cours de run, a été relancé. La base Postgres partagée a été attendue
  jusqu'à `pg_isready`. Sondes en transaction annulée : 0 mail, 0 tâche Celery, base inchangée.

## 1. Vérificateurs (8 agents frais, opus, effort élevé, lecture seule, même répertoire)

Une fin de session a interrompu les 8 agents ; ils ont été repris où ils s'étaient arrêtés.

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **24** | ASEC3, 4, 6, 7, 10, 11, 13, 15, 22, 24, 25, 26, 27, 28, 30, 32, 33, 34, 35, 41, 42, 43, 47, 48 |
| partiel | **6** | ASEC2 (S1), ASEC29 (S1), ASEC9 (S3), ASEC37 (S3), ASEC38 (S3), ASEC21 (S4 ×2) |
| faux | **1** | ASEC19 : le test de la garde n'est découvert par aucun job de CI |
| non-fait / régression / déjà-présent | 0 | — |

Changements postérieurs jugés voulus, donc pas des régressions :
- un id d'une autre société ou inexistant répond 404 au lieu de 400 (fuzz du 24/10, `IdInconnu404Mixin`) ;
- un refus qui dépend de l'état répond 409 (ERR-ENF11) ;
- le mandat de paiement est parqué (AFAC19) ;
- `classer-apres-vente` est retiré (ADOC39) ;
- le verrou de connexion par couple compte + IP est en cache et compte 10 échecs consécutifs (D-ASEC-4) ;
- la bascule de la production en `settings.prod` a été faite le 10/10 sur ordre du fondateur.

## 2. Sondes (2 REPRO)

| Sonde | Tâche | Observé (code de `main`, transaction annulée) |
|---|---|---|
| `docs/audits/sondes/ASEC/C-ASEC-VER-002.py` | ASEC2 | Commercial responsable : crée un rôle étroit **201**, l'attribue à un Commercial **200**, l'élargit à `paie_gerer`, `parametres_modifier`, `compta_valider` **200**, réinitialise le mot de passe du compte **200** |
| `docs/audits/sondes/ASEC/C-ASEC-VER-003.py` | ASEC29 | Commercial sans `encaisser` : `enregistrer-paiement` **403**, mais `paiement-avec-retenue` **201** (facture « payee ») et `retour-client` **201** (avoir créé) |

C-ASEC-VER-001 appartient à la contre-visite du 11/10 ; la numérotation continue à -002.

## 3. Écarts retenus

| Constat | Tâche | Écart de | Crit. | Grav. | Emplacement | Observé → attendu | Sonde |
|---|---|---|---|---|---|---|---|
| C-ASEC-VER-002 | ASEC55 | ASEC2 | C5 | S1 | `apps/roles/views.py::RoleViewSet.perform_update` | garde « pas plus large que l'acteur » seulement à l'attribution → aussi à la création et à la modification d'un rôle, une seule fonction | `docs/audits/sondes/ASEC/C-ASEC-VER-002.py` |
| C-ASEC-VER-003 | ASEC56 | ASEC29 | C5 | S1 | `apps/ventes/views/paiement.py::PaiementViewSet.paiement_avec_retenue` | 11 portes d'argent au droit d'écriture des ventes (Admin Ventes et Responsable passent) → `encaisser` partout (D-ASEC-VER-1) | `docs/audits/sondes/ASEC/C-ASEC-VER-003.py` |
| C-ASEC-VER-004 | ASEC57 | ASEC19 | C10 | S2 | `scripts/ci_shard.py::TOP_LEVEL_MODULES` | 6 des 11 modules du paquet racine `tests/` jamais joués, dont deux gardes de sécurité (champs posés par le serveur, portail) → découverte de tout le paquet | STATIQUE (fonction pure, `discover_units`) |
| C-ASEC-VER-005 | ASEC58 | ASEC37 | C5 | S3 | `apps/ged/services.py::zipper_documents` | ZIP, opérations PDF et portail lisent la clé de stockage brute → la lecture gardée de l'aperçu | STATIQUE |
| C-ASEC-VER-006 | ASEC59 | ASEC38 | C5 | S3 | `apps/ged/views.py::DocumentViewSet` | verrou, legal hold, archivage, revue, délier, lien public sans ACL → 403 comme `purger` | STATIQUE |
| C-ASEC-VER-007 | ASEC60 | ASEC9 | C5 | S3 | `apps/roles/serializers.py::RoleSerializer.validate` | codes non octroyables contrôlés sur le NOM du rôle (contournable en le renommant) → sur son identité système | STATIQUE |
| C-ASEC-VER-008 | ASEC61 | critique | C8 | S3 | `backend/fastapi_ia/app/services/sql_agent_service.py` | `cout_unitaire` des mouvements de stock lisible par l'agent SQL → colonne de coût interdite | STATIQUE |
| C-ASEC-VER-009 | ASEC62 | critique | C5 | S3 | `apps/ventes/views/remise_encaissement.py::RemiseEncaissementViewSet.get_permissions` | bordereau de remise d'espèces ouvert à tout rôle → `encaisser` | STATIQUE |

**Constats S1-S2 : 3** (2 S1, 1 S2). Les deux S1 sont reproduits par sonde. Le S2 est prouvé par une fonction pure (la
découverte des tests de CI) : il n'a besoin d'aucune base. ASEC63 clôt les sections (elle couvre aussi ASEC64) : c'est l'acceptation en direct,
à deux comptes, jamais confiée à une lane.

Routage :

| Propriétaire | Plan | Tâches |
|---|---|---|
| sécurité | `PLAN_AUDIT_SECURITE.md` | ASEC55, 60, 63 |
| facturation | `PLAN_AUDIT_FACTURATION.md` | ASEC56, 62, 64 |
| deploy | `PLAN_AUDIT_DEPLOY.md` | ASEC57 |
| documents | `PLAN_AUDIT_DOCUMENTS.md` | ASEC58, 59 |
| analyse | `PLAN_AUDIT_ANALYSE.md` | ASEC61 |

ASEC64 masque à l'écran les gestes d'argent sans `encaisser` (`@after: ASEC56, ASEC62`). Aucun écran ne lit encore ce droit, et la moitié serveur passe d'abord.

Choix de construction à connaître :
- les portes passent à `PeutEncaisser` seul, comme ASEC29 : le Commercial, qui porte `encaisser` par défaut, garde ces gestes ;
- l'aperçu d'import de relevé prend le même droit que sa validation ;
- ASEC62 met la remise d'espèces sous `encaisser` : les techniciens ne déclarent plus de remise, ce qui change le flux PACT46 ;
- ASEC60 refuse à tous le renommage d'un rôle système.

**Décision du fondateur (01/11/2026, D-ASEC-VER-1 = tout).** Tout geste qui touche une créance ou un paiement exige
`encaisser`, y compris le lien de paiement en ligne, les pénalités de retard et l'attestation RAS reçue.

## 4. Seconde lentille et critique de complétude

- **Seconde lentille sur les 2 S1** (opus, effort élevé, contexte frais, voies différentes des sondes).
  - **C-ASEC-VER-002 maintenu S1, et plus large que la sonde :**
    - tout rôle personnalisé déjà porté, même créé par un Directeur, est élargissable par tout acteur de palier
      responsable sans périmètre (Commercial responsable, Technicien responsable, Responsable) ;
    - l'effet est immédiat pour tous ses porteurs, sans attribution ;
    - créer un rôle large d'emblée réussit aussi, mais l'attribution l'arrête.
  - **C-ASEC-VER-003 maintenu S1, sans rôle personnalisé :**
    - les rôles semés Admin Ventes et Responsable, sans `encaisser`, voient « Retour client » et « Import relevé
      bancaire » à l'écran ;
    - `paiement-avec-retenue` n'a pas d'écran et n'est atteignable que par l'API ;
    - `releve_commit` crée de vrais paiements.
- **Critique de complétude (1 appel Fable, effort élevé).**
  - Rattaché à C-ASEC-VER-003 : neuf portes jumelles (rejet, annulation, réaffectation, libération de retenue, lien de
    paiement créé ou révoqué, pénalités, attestation RAS, `releve_dry_run`).
  - Rattaché à C-ASEC-VER-002 : la jumelle à la création (`perform_create`).
  - Rattaché à C-ASEC-VER-004 : `test_asec51_portail_defaut`, second module de sécurité jamais joué.
  - Nouveaux, déposés : `cout_unitaire` lu par l'agent SQL (ASEC61), bordereau de remise ouvert à tout rôle (ASEC62).
  - Spot-check d'ASEC4 (verrou de connexion), ASEC42 (agent SQL) et ASEC13 (inscription) : mécanismes en place, hors
    ASEC61.

## 5. Optionnel (non déposé)

- **ASEC2.** Le test « directeur protégé » n'asserte pas le code `rang_cible` (justifié par l'ordre des gardes).
- **ASEC4.** Le compte est résolu par `username__iexact().first()` alors que l'authentification est sensible à la casse.
  Le défaut est antérieur, et l'attaquant ne peut pas créer seul la collision.
- **ASEC6, ASEC7, ASEC30, ASEC32, ASEC33.** Quelques cas non rejoués : création avec un `activity_type` étranger, rejeu
  HTTP de l'entité, PATCH de suppléant, quantités de B non relues. Le même mécanisme est prouvé ailleurs.
- **ASEC10.** Un non-admin peut retirer des codes NON élevés d'un rôle admin personnalisé.
- **ASEC15.** Le test vit sous `apps/identity/tests/` et non au chemin déclaré (S4). Tant que `RELAIS_API_SECRET` n'est
  pas posé, un Worker Cloudflare tiers peut forger `X-Forwarded-For` (D-ADEP-103 : état accepté jusqu'à la bascule, que
  Reda peut confirmer en lecture seule).
- **ASEC21.**
  - La contre-épreuve sur le SHA d'avant correctif n'a pas été rejouée (`base_verdict` null).
  - La spec `frontend/e2e/acceptation/asec.spec.js` a été retirée de `main` (7f692d9d98).
  - L'enregistrement `2026-10-29-f9ef5544f` n'a ni trace ni capture.
  - ASEC63 exige les trois.
- **ASEC24, ASEC35.** Défense en profondeur absente dans `lire_image_toiture` et `create_devis_pour_ticket`. Aucune
  écriture client n'y mène.
- **ASEC25.** La preuve en direct de l'auditeur n'a pas été jouée.
- **ASEC37.** `customfields._validate_fichier_value` accepte un `{file_key}` sans borne de société, mais aucun lecteur
  serveur n'a été trouvé.
- **ASEC41.** `ExperimentSerializer.status` est inscriptible. Le bandit ne produit que des propositions : aucune
  activation Meta (règle #3 tenue sur toutes les portes).
- **ASEC56, à router chez devis.** L'action agent `ventes.facture.enregistrer_paiement` déclare `required_permission='ventes_valider'` au lieu de `encaisser` (`apps/ventes/agent_actions.py`, propriétaire devis, S4). L'action est proposée puis échoue en 403.
- **ASEC42.** `_moteur_test()` saute silencieusement l'exécution en base si la connexion échoue.
- **Critique de complétude.**
  - SCIM `POST Groups` accepte un `roleId` arbitraire (l'IdP est de confiance par conception).
  - `export_ras_tva` fournisseur est en `IsResponsableOrAdmin`.
  - La désactivation de la 2FA se fait par mot de passe OU TOTP sous une session volée.

## 6. Couverture et non-couvert

- **Couvert.**
  - 31 tâches sur 54 cochées, soit toutes les S1/P0 et 25 % du reste : commits, tests nommés, code de `main`, décisions
    D-ASEC-*.
  - Exécutions des vérificateurs :
    - `check_fk_scoping.py` : 462 FK, 0 dans l'allowlist ;
    - `check_ip_primitive.py` ;
    - tests nginx (4/4) ;
    - `check_acceptation.py` ;
    - matrice des rôles semés.
  - Deux sondes jouées par l'orchestrateur.
- **Non couvert.**
  - Les 23 autres tâches cochées.
  - Les tests Django (base requise ; la CI de `main` est verte sur `ba577e26a`).
  - Aucune preuve en direct à l'écran (ASEC63 ouverte).
  - Aucune lecture de la production : l'existence de lignes GED historiques à clé étrangère reste inconnue. Si l'une
    existe, ASEC58 monte en S1.
- **Statut du registre.** Après ce dépôt : 54 cochées sur 64 constructibles (84 %), ASEC55 à ASEC64 ajoutées.
  Contre-visite de clôture **avec 3 écarts S1-S2** : statut calculé `audité`, le cycle n'est pas sorti.

## 7. Coût

- 8 vérificateurs opus (effort élevé) : ≈ 1,5 M de jetons.
- 1 seconde lentille opus : ≈ 0,17 M.
- 1 critique Fable (effort élevé) : ≈ 0,19 M. Elle a étendu C-ASEC-VER-003 de 3 à 11 portes et ajouté deux trous déposés
  (ASEC61, ASEC62).
- 1 rédacteur opus : 10 tâches v3.
- H0 S0 O10 F1 · jetons sous-agents ≈ 2,2 M

<!-- verifie | groupe: ASEC | pct: 100 | ecarts_s1_s2: 3 -->
