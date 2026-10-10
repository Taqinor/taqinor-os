# Vérifie ADOC — contre-visite de clôture du groupe documents (J6), 09/10/2026

Commande « vérifie ADOC » (METHODE §C.4.2, skill audit §5). Le groupe compte **101 tâches cochées sur 104**, soit 97 % :
la contre-visite de **clôture** (≥ 95 %) est due. Pour chaque tâche de l'échantillon, on rapproche le texte de la tâche, le ou
les commits et le test rouge nommé, en appliquant les 7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Les tests
nommés sont rejoués, et chaque écart S2 est prouvé par une sonde exécutée en transaction annulée. Les écarts confirmés sont
déposés en tâches v3 dans le plan du propriétaire.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien écrit en production. La seule action sur la prod est une
lecture, faite par l'orchestrateur et annoncée dans le chat.

## 0. Préconditions

- **SHA.** `origin/main` = `1a186a82c` (PR #921). Branche de claim : `verifie-adoc` (commit vide `67e174b96`, poussé).
- **Registre.** J6 `documents`, statut `audité`, groupe ADOC, dossier `docs/audits/2026-10-05-documents.md` (PR #806). Plans
  alimentés : DOCUMENTS 83, DEVIS 5, DEPLOY 5, CHANTIERS 5, TRANSVERSE 2, WEB_PLAN 2, CALEPINAGE 1, FACTURATION 1.
- **Inventaire (déterministe).** 104 tâches ADOC, dont 101 `[x]`. Les 3 restantes :
  - ADOC170 : acceptation live du groupe, `[BLOCKED]` ;
  - ADOC39 et ADOC149 : GATED, en attente d'une décision fondateur.

  Un seul enregistrement d'acceptation existe : `docs/audits/acceptation/2026-10-07-adoc171/`, qui ne couvre que le suivi public.
  Son constat principal a été déposé en ADOC172 (chantiers), cochée depuis.
- **Échantillon (graine = SHA `1a186a82c`).** Toutes les P0 et S1 (ADOC1, ADOC2, ADOC60, ADOC36), plus 25 % du reste
  (24 tirées sur 97). Total : **28 tâches**.
- **Pile locale.** La checkout principale est sur `main` = `1a186a82c`, avec le code Django monté en direct. Le `migrate` de
  `erp_db` a appliqué 26 migrations en attente avant les sondes. La base de test isolée `test_verifadoc` a été clonée de
  `test_erp_db` puis migrée par `--keepdb`. La base partagée n'a pas été touchée : deux runs d'autres sessions étaient actifs.

## 1. Vérificateurs (7 agents frais, opus, effort élevé, lecture seule, même répertoire)

| Lot | Tâches | ok | partiel | autre |
|---|---|---|---|---|
| 1 | ADOC1, ADOC2, ADOC36, ADOC12 | 3 | ADOC12 | — |
| 2 | ADOC60, ADOC67, ADOC68, ADOC69 | 3 | ADOC68 | — |
| 3 | ADOC61, ADOC62, ADOC70, ADOC73 | 3 | — | ADOC62 déjà-présent |
| 4 | ADOC18, ADOC30, ADOC34, ADOC63 | 3 | ADOC18 | ADOC63 : écart réfuté en prod (§3) |
| 5 | ADOC37, ADOC115, ADOC119, ADOC123 | 3 | ADOC37 | — |
| 6 | ADOC127, ADOC133, ADOC137, ADOC138 | 4 | — | — |
| 7 | ADOC143, ADOC145, ADOC147, ADOC148 | 3 | ADOC148 | — |
| **Total** | **28** | **22** | **5** | **1 déjà-présent** |

Les points saillants des tâches jugées ok :

- **Les trois P0 tiennent sur `main`.**
  - ADOC1 : les FK GED sont bornées à la société par `SameCompanyFKSerializerMixin`, et le lien de dépôt passe par
    `services.create_depot_public`.
  - ADOC2 : une suppression renvoie 409, et des receivers `pre_delete` protègent l'archivage légal et le legal hold.
  - ADOC60 : le PV, le BL FR/AR et le dossier de remise lisent `chantier.bom`, avec repli sur `option_lines` × N. Le rendu
    WeasyPrint réel est testé.
- **ADOC62 n'a ajouté que des tests.** Le comportement était déjà livré par ACAL236 (`deposer_et_fusionner`, ancêtre
  vérifié par `git merge-base --is-ancestor`).
- **ADOC70 a un écart de texte, sans écart de code.** Le texte dit `source_type 'documents.attestation'`, le code écrit
  `documents.attestation.<type>`. Ce choix est volontaire : les deux types d'attestation d'un même chantier ne se versionnent
  pas l'un sur l'autre. Aucun consommateur ne lit la chaîne exacte (grep). C'est le texte qui a vieilli, pas le code : aucune
  tâche ouverte.

## 2. Tests nommés rejoués

- **Front (vitest, checkout principale à `1a186a82c`).** 7 fichiers, 64 tests, tous verts :
  - `GedNavigator`, `GedSearch`, `NumeriserPage`, `ApprobationPage.adoc` ;
  - `PublicSignaturePage`, `InstallationDetail.adoc` ;
  - `PortailMotDePasse`, `PortailClientEquipe`.
- **apps/web (vitest).** `tests/suiviOtpADOC.test.ts` : 5 tests, verts.
- **Gardes (lot 7).**
  - `scripts/check_portail_surfaces.py` : exit 0, « 3 surface(s) GATED ».
  - `python -m unittest scripts.tests.test_check_portail_surfaces` : 9 tests OK.
  - `check_ecrans_atteignables.py` : OK.
  - `check_dockerfile_context.mjs` : pass 1, fail 0.
- **Django.** 21 modules `test_adoc_*` des tâches échantillonnées (79 tests), lancés sur `test_verifadoc`. Résultat : §2-bis.

## 2-bis. Résultat Django

Rejeu local abandonné. La base clonée `test_verifadoc` était très en retard : après 70 minutes, `--keepdb` n'avait appliqué que
1 299 migrations sur 2 232, et aucun test n'avait démarré. Le run a été arrêté et la base supprimée.

Ces 21 modules restent couverts par le job `backend-tests` de la CI de `main` à `1a186a82c`, qui est vert : le run « CI » du
commit est en succès, et la merge queue l'exige. Les écarts de ce dossier ne viennent pas de tests rouges. Ils portent sur des
clauses que ces tests verts n'exercent pas, et sont prouvés par les sondes du §3.

Fraîcheur : `git diff 1a186a82c..origin/main` (`42b857649`) ne touche ni `apps/ged`, ni `apps/portail`, ni `apps/documents`.

## 3. Sondes (orchestrateur, pile locale, transaction annulée, mail en mémoire, Celery coupé, HTTP sortant bloqué)

Le prélude commun est `docs/audits/sondes/ADOC/_prelude.py`. Pour rejouer une sonde :

```
cat _prelude.py C-ADOC-VER-00N.py | docker exec -i -w /app <django> python manage.py shell
```

| Sonde | Tâche | Verdict | Sortie |
|---|---|---|---|
| `C-ADOC-VER-001.py` | ADOC37 | **REPRO** | emp2 ne voit pas D (`documents_visible_to_user` → False). Pourtant `/signataires-demande/` renvoie 200 `fuite_jeton= True fuite_lien= True`. La page publique du signataire, appelée en anonyme avec ce jeton, répond 200 `document_nom: SALAIRE-EMP1-CONFIDENTIEL.pdf`. `/demandes-signature/` et `/champs-signature/` ne fuient pas. |
| `C-ADOC-VER-002.py` | ADOC12 | **REPRO** | Dépôt de « facture.pdf » : checklist `manquant` → `present`, demande CIN `soldee`. Même résultat avec « certificat medecine.pdf ». |
| `C-ADOC-VER-003.py` | ADOC68 | **REPRO** | Demande `en_attente` puis POST `nouvelle-version/` : **201**, versions 1 → 2. |
| (lecture prod) | ADOC63 | **RÉFUTÉ** | En prod, `PUBLIC_BASE_URL=''` et `CSRF_TRUSTED_ORIGINS[0]` vaut `https://api.taqinor.ma`. `url_publique_signature(…, mode='signataire')` renvoie donc `https://api.taqinor.ma/ged/signataire/…`, et `curl` sur cette route répond 200. Le repli vers `taqinor.ma` décrit par le vérificateur ne se produit pas avec la configuration actuelle. Il reste latent (dépend de la config), voir §5. |

Les trois sondes ont toutes fini sur `ROLLED BACK`, avec `mails 0` et `celery []`.

## 4. Écarts retenus → `docs/plans/PLAN_AUDIT_DOCUMENTS.md`, section « ADOC — ÉCARTS vérifie 2026-10-09 · format v3 »

| Tâche | Écart de | Gravité | Cause | Preuve |
|---|---|---|---|---|
| ADOC173 | ADOC37 | S2 | L6-jumeau (la garde ignore les modèles à FK `demande`) | sonde VER-001 |
| ADOC174 | ADOC12 | S2 | clause-manquante (sous-chaîne + repli « demande unique ») | sonde VER-002 |
| ADOC175 | ADOC68 | S2 | régression-ultérieure : ADOC18, construite après ADOC68, ajoute un `add_version` non gardé | sonde VER-003 |
| ADOC176 | ADOC18, ADOC68 | S3 | L5-test-affaibli (`store_attachment` mocké, faux PDF jamais aplati, quota non testé) | lecture des tests |

**Aucun S1. Pas de critique Fable**, puisqu'elle n'est due que si des S1 subsistent (METHODE §C.4.2).

## 5. Optionnel (hors correction ou spec, non déposé)

- **ADOC63.** Le lien de signature sans requête (relance Celery, signataire suivant) dépend de `CSRF_TRUSTED_ORIGINS[0]` quand
  `PUBLIC_BASE_URL` est vide. Il est correct en prod aujourd'hui. Poser `PUBLIC_BASE_URL` dans l'`.env` du serveur le rendrait
  explicite (geste fondateur, aucune tâche).
- **ADOC148.** La carte « Tickets SAV ouverts » compte des `sav.Ticket`, alors que la liste « Mes demandes SAV » lit des
  `DemandeTicketPortail`. Rattacher ce compteur à cette liste relève d'une interprétation, pas du texte de la tâche (qui ne
  compare que devis et factures).
- **ADOC143.** Depuis AFAC9, `rapprocher` (vue interne) ne rattrape pas `FactureNonEncaissable`. Rapprocher un paiement
  INITIÉ dont la facture est annulée répond 500. Le paiement reste INITIÉ et aucune donnée n'est perdue. Candidat S3, non sondé.
- **ADOC62.** `deposer_et_fusionner` n'exclut pas la corbeille : un dossier technique mis en corbeille puis régénéré reçoit
  sa version sur un document invisible.
- **ADOC70.** Une re-signature refusée (hold, signature en attente) écrase quand même `custom_data.empreinte_signature`.
- **ADOC60.** Le jumeau `quote_engine/extra_docs.py::_chantier_composants` lit toujours `option_lines` sans × N. Il est hors
  périmètre (règle #4) et reste signalé comme au dossier du 05/10.
- **ADOC127.** Fenêtre de concurrence entre une acceptation interne et une acceptation portail : le statut n'est pas lu sous
  `select_for_update`.

## 6. Couverture et non-couvert

- **Couvert.** 28 tâches sur 101 cochées (toutes les P0 et S1, plus 25 % tirées). Tous les commits ont été lus, tous les tests
  nommés ont été lus et rejoués, et 3 sondes ont été exécutées.
- **Non couvert.**
  - Les 73 autres tâches cochées (hors échantillon).
  - L'acceptation live du groupe : ADOC170 reste `[BLOCKED]` et n'a jamais été jouée. Les preuves en direct (L7) des tâches
    portail et signature ne sont donc pas rejouées ici : elles reviennent à l'orchestrateur du plan-run qui débloquera ADOC170
    (CLAUDE.md, étape 3-bis).
- **Statut du registre.** Il reste `audité` dans le registre et ne passe pas `vérifié`, à cause des 3 écarts S2. Le groupe
  ressort de la règle de sortie (METHODE §C.4.3) quand ADOC173-176 sont construites et qu'un second `vérifie` revient sans écart
  S1-S2.

## 7. Coût

- 7 vérificateurs opus : environ 1,09 M de jetons au total.
- Orchestrateur : sondes, lecture prod, rejeu des tests, rédaction.
- Aucun appel Fable.
