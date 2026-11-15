# Vérifie ATST — contre-visite de clôture du parcours PF7 « preuves de test », 15/11/2026

Contre-visite de clôture du groupe ATST, due à 95 % (`audit_registre.py --du` : 97 %, 38 tâches cochées sur 39
constructibles). Elle relit les 20 tâches cochées depuis la contre-visite de mi-parcours du 13/11, et la fermeture de son
unique écart (ATST57). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `8fc408bf6`. Branche de claim : `verifie-1511`.
- **Registre.** PF7 `preuves-de-test`, groupe ATST : 38 tâches cochées sur 39 constructibles (97 %). ATST55, la tâche de
  rejeu, reste ouverte. ATST23, ATST54 et ATST56 sont `[BLOCKED]`, en attente de leur preuve en direct.
- **Échantillon.** Les **20 tâches cochées depuis le 13/11** sont toutes relues : ATST13, 21, 22, 27, 30, 41 à 53, 57 et 58.
- **Méthode.**
  - Lecture des commits, du code sur `origin/main` et des tests nommés.
  - Gardes hôte (ATST41-53) : les 14 modules `scripts/tests` sont joués sur le dépôt, et leur branchement est contrôlé dans
    `scripts/ci_guards.py`.
  - **30 mutants joués** dans une copie `git archive` hors dépôt.
  - Vitest d'ATST27 joué, avec son mutant joué dans une copie.
  - Aucune pile, aucun test Django lancé, aucune production consultée.

## 1. Vérificateurs (2 lots, opus, effort élevé, frais, même répertoire, et l'orchestrateur pour les gardes)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **19** | ATST21, 22, 27, 30, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 57, 58 |
| ok avec jumeau oublié | **1** | ATST13 (le serveur est correct ; son miroir front n'est pas réaligné, §4) |
| non-fait / faux / régression / déjà-présent | **0** | — |

## 2. Tests nommés

- **ATST13.** Correctif produit livré.
  - `authentication/models.py::_role_grants_write` saute tout code absent de `codes_du_registre()`. Si le registre manque,
    elle lève `ImproperlyConfigured`, jamais un repli permissif (D-ATST-1).
  - Le test appelle le vrai `_role_grants_write` et le vrai `is_responsable`, sans mock.
  - Trois mutants ont été rejoués en Python pur avec le vrai registre : retirer le saut, prendre `PERMISSION_MODULE` pour
    registre, ne pas passer `toutes_permissions`. Chacun rougit une assertion du test.
  - Les jumeaux serveur (`IsResponsableOrAdmin`, `EcritureRefuseeLectureSeule`, `records/serializers.py`) passent tous par
    ce calcul.
- **ATST21.** `VarianteConfigEndpointTests` prend ses rôles dans `CANONICAL_SYSTEM_ROLES` et relit `variante_pct` après le
  403.
  - Le mutant de la tâche (tuple de rôles) a disparu avec ADRG11. Il avait été joué rouge le 13/11 sur `22d5ce51e`.
  - Mutant équivalent sur la garde `parametres_modifier` actuelle : raisonné rouge.
- **ATST22.** La classe HTML n'est pas taguée et rend le vrai `build_html`. Le mutant (retrait de la levée de
  `masquer_economies`) a été joué rouge sur runner le 13/11.
- **ATST27.** Le test vitest monte le générateur vierge, ajoute une ligne, puis vérifie que la garde de sortie est armée et
  que le brouillon est écrit.
  - Sans mutant : `npx vitest run src/pages/ventes/DevisGenerator.agnrBrouillonConditions.test.jsx`, 5 tests sur 5 verts.
  - Mutant joué dans une copie (`|| lignesSaisies` retiré de `formulaireNonVierge`) : 2 rouges, dont ATST27, et 3 témoins
    verts.
  - Le fichier tourne dans `frontend-vitest-shard`.
- **ATST30.** Les specs AGR318, CIQ334 et CIQ346 comparent les `data-figure` de la page `/proposition` FR et AR au JSON
  `/data/`, relu par requête : une source indépendante, pas le DOM.
  - L'assertion `total_ttc ∈ identitesComparees` interdit une comparaison vide.
  - `test.skip(!WEB_URL)` est remplacé par une assertion.
  - Le job `e2e-shard` (shard 2, `ci.yml`) sert apps/web et exporte `WEB_URL` à chaque fusion, sous `bash -e`, et alimente
    le check requis `e2e`.
  - Avant le correctif, les specs échouaient réellement (run 43639836368). Le rejeu PASS est consigné dans l'enregistrement
    d'acceptation du 14/11.
- **ATST57** (écart du 13/11). L'assertion « Aucun commentaire écrit sur place » sur le lead de A ferme l'écart C-ATST-VER1-001.
  - Le texte n'a qu'une source en production.
  - Mutant `company_id=visite.pk` : raisonné rouge.
- **ATST58.** La cellule du P.U. d'une ligne à quantité 14 est lue sur le document premium et sur le une-page.
  - Le mutant `_cellule_prix_remise(pu_ht, pu_ht)` est raisonné rouge.
  - Aucune autre ligne ne vaut 1 100,00.
- **Gardes ATST41 à ATST53.** Les 14 modules de test sont verts sur le dépôt : 185 tests, aucun saut sur l'hôte (Django y est importable ; en CI, sans Django, seul le test de comparaison
    directe d'ATST51 se saute, la table figée prenant le relais).
  - Tous sont lancés par `scripts/ci_guards.py`, dans `stage-names` ou dans `backend-lint-fast`, dont dépend le check requis
    `backend-lint`.
  - Les tests appellent les vrais `main()` et `check_file` sur des arbres fautifs.
  - Plus aucune boucle recopiée (ATST43), et plus de littéraux tautologiques pour l'allowlist (ATST48).

## 3. Sondes et preuve en direct

- **Mutants des gardes, 30 joués, 30 rouges.** Ils ont été joués sur une copie `git archive HEAD` (base verte vérifiée par
  module), pas dans le dépôt.

  | Tâche | Mutant(s) joué(s), tous rouges |
  |---|---|
  | ATST41 | `if not ok and key not in exempt` → `False` |
  | ATST42 | `jobs_non_verts` → `[]` |
  | ATST43 | trois mutants : `_function_saves_var`, `if offenders`, balayage vidé |
  | ATST44 | `_find_method_in_class` |
  | ATST45 | trois mutants : `non_signes`, `perimes`, `{"skipTest","skip"}` → `{"skip"}` |
  | ATST46 | chacun des quatre `_verifier_*` retiré, plus `if echecs` |
  | ATST47 | `if offenders`, balayage vidé, `_autorise` → `True` |
  | ATST48 | `if offenders`, balayage vidé, raison propre |
  | ATST49 | `if offenders`, `sites = []` |
  | ATST50 | `if offenders`, balayage vidé |
  | ATST51 | `.strip("-_")` → `.strip("-")`, rougi par la table figée qui contient `Co_` |
  | ATST52 | `offending` → `[]`, échec de `git ls-files` ignoré |
  | ATST53 | cliquet retiré, `scan_backend` → `[]`, `codes_hors_registre` → `[]` |

- **Sondes du dossier PF7.** Aucune ne couvre les tâches de cette contre-visite. Aucune nouvelle sonde : aucun écart S1-S2.
- **Preuve en direct.**
  - Les tâches cochées par rejeu sur runner le 13/11 et le 14/11 sont couvertes par les enregistrements de
    `docs/audits/acceptation/ATST/`.
  - Les autres sont des tâches de test ou de garde, sans écran.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ATST-VER2-200 | ATST13 | S3 | `frontend/src/hooks/useHasPermission.js::estResponsable` compte encore tout code non `_voir` : un rôle à `custom_object.<code>.gerer` (accepté par `CodePermission`, hors registre) est « responsable » au front, pas au serveur ⇒ « Mes équipes » ou le parc appelle une route `IsResponsableOrAdmin` et reçoit 403 ; le serveur fait foi | STATIQUE | ATST59 |

Aucun écart S1 ni S2, ni nouveau ni antérieur ouvert : C-ATST-VER1-001 (S3) est fermé par ATST57.

## 5. Optionnel (non déposé)

- **ATST57, ATST58, ATST30.** Les mutants demandés « joués, sortie collée au commit » sont seulement raisonnés au commit.
  Le raisonnement sur le code réel confirme chaque rougeur (S4 de procédure).
- **ATST30, jeton.** Les specs C&I ouvrent `/proposition` avec le jeton PUBLIC, alors que la tâche demandait le jeton
  interne (sans trace d'ouverture). Les montants n'en dépendent pas.
  - La partie AR ne vérifie pas que la langue a basculé (`lang`/`dir`).
  - Le rapport Playwright du shard 2 est réécrit par la seconde invocation.
- **ATST54.** Il reste `[BLOCKED : preuve en direct due]` alors que son câblage est sur `main` et que le run 43642891367
  en est la preuve. C'est un écart de tenue du plan, pas du code.
- **ATST13.** Le test lit `is_responsable` et non une requête HTTP sur une route gardée.
  - 25 codes manquent à `PERMISSION_MODULE`, alors que la tâche en annonçait 24.

## 6. Couverture et sortie de cycle

- **Couvert.**
  - Les 20 tâches cochées depuis le 13/11 : texte, commits, tests nommés, branchement CI, jumeaux.
  - 30 mutants de gardes joués ; le mutant vitest d'ATST27 joué ; les mutants d'ATST13 rejoués en Python pur.
  - La fermeture de C-ATST-VER1-001.
- **Non couvert.**
  - Aucun test Django lancé : les mutants d'ATST21 (forme actuelle), ATST57 et ATST58 sont raisonnés, non joués (ni pile
    Django ni WeasyPrint sur l'hôte).
  - Les e2e d'ATST30 n'ont pas été rejoués, et le mutant `ChainePrix` n'a pas été joué. La preuve vient des traces CI
    commitées, pas d'une relecture directe des journaux GitHub.
  - Aucun rejeu navigateur.
  - La tâche ouverte ATST55 et les trois tâches bloquées.
- **Statut.** Zéro écart S1-S2, nouveau ou antérieur. Un écart S3 est déposé (ATST59). C'est le premier `vérifie` à zéro
  S1-S2 depuis la construction : avec celui du 13/11, ce sont deux contre-visites consécutives à zéro S1-S2.

## 7. Coût

- 2 vérificateurs (opus, effort élevé) et l'orchestrateur pour les gardes et la rédaction ; jetons sous-agents ≈ 0,39 M ;
  aucun appel Fable.

<!-- verifie | groupe: ATST | pct: 97 | ecarts_s1_s2: 0 -->
