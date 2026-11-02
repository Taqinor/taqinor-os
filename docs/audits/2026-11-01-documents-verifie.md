# Vérifie ADOC — troisième contre-visite de clôture du groupe documents (J6), 01/11/2026

La commande `vérifie ADOC` (METHODE §C.4.2, skill audit §5) a été lancée pendant `loop audit`. Le
groupe compte 114 tâches cochées sur 115 (99 %, `audit_registre.py status` ; reste ADOC170, acceptation `[BLOCKED]`), et toutes
les tâches ÉCART de la contre-visite précédente (`docs/audits/2026-10-11-documents-verifie.md`, ADOC177-ADOC183) sont
cochées. `audit_registre.py --du` ne la liste pas : sa règle ne recompte pas un groupe déjà passé à ≥ 95 %. Elle a donc
été jouée sans attendre la règle.

Pour chaque tâche de l'échantillon, on rapproche le texte, les commits, le test nommé et le code de `main` avec les 7
critères de `docs/claude-memory/lecons-construction-qjr5.md`. Les écarts confirmés deviennent des tâches v3 dans le plan du
propriétaire des fichiers. La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `56d5b623a` (PR #1197). Le conteneur de sondes partagé `erp-agentique-django_core-1` monte le
  checkout principal, lui aussi à `56d5b623a`.
- **Échantillon (graine = SHA `56d5b623a`, `random.Random(int(sha, 16)).sample`) : 37 tâches.**
  - Les 4 tâches S1/P0 : ADOC1, ADOC2, ADOC36, ADOC60.
  - Les 7 tâches ÉCART du 11/10 : ADOC177-ADOC183.
  - 25 % du reste (26 sur 103) : ADOC4, 9, 14, 15, 16, 22, 24, 26, 29, 61, 66, 71, 75, 113, 114, 118, 121, 126, 134, 136,
    138, 140, 143, 144, 149, 175.
- **Incident de pile.** Pendant la contre-visite, le moteur Docker de la machine (partagé par trois sessions de
  contre-visite, ~14-17 `manage.py shell` simultanés, 1 Go de RAM libre) est tombé (API 500, puis tube absent). Reda l'a
  redémarré. Les sondes ont été rejouées une par une après le redémarrage (§2).

## 1. Vérificateurs (4 agents frais, opus, effort élevé, lecture seule, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **30** | ADOC1, 2, 4, 9, 14, 15, 16, 22, 24, 36, 60, 61, 66, 71, 75, 113, 114, 118, 121, 126, 134, 136, 138, 140, 143, 144, 175, 178, 179, 181 |
| partiel | **7** | ADOC26, ADOC29, ADOC149, ADOC177, ADOC180, ADOC182, ADOC183 |
| non-fait / faux / régression / déjà-présent | 0 | — |

ADOC14 est « ok » sur ses propres clauses ; l'appelant de `approve_demande` qu'il a oublié (la boîte centrale des
approbations) est déposé comme constat distinct (C-ADOC-VER-011).

Changements postérieurs jugés voulus, donc pas des régressions :
- ENF7 / ERR-ENF11-FUZZ-GED : doublons, archivage d'un document en corbeille et refus d'état en 409 (ADOC14, ADOC22, ADOC26) ;
- ENF11 : identifiants étrangers ou inconnus en 404 au corps identique (ADOC1, ADOC118) ;
- ADOC39 : la moitié « sauvegarde Office » d'ADOC175 a disparu avec la route (D-ADOC39).

## 2. Sondes

Rejouées une par une par `scripts/sonde.py` (créneau partagé), en transaction annulée, base inchangée à chaque fois.

| Sonde | Tâche | Verdict | Observé (code de `main`) |
|---|---|---|---|
| `docs/audits/sondes/ADOC/C-ADOC-VER-013.py` | ADOC14 (appelant) | REPRO | boîte centrale, approbateur de l'étape 1 (collaborateur ordinaire) : `decider` → 200 ; demande **approuve**, document **approuve**, `etape_courante=0`, étapes `['en_cours', 'en_attente']` |
| `docs/audits/sondes/ADOC/C-ADOC-VER-030.py` | ADOC177 | REPRO | `televerser` « CIN.pdf » → 201 ; demande CIN **en_attente** ; « cin.PDF » et « Attestation CNSS.pdf » ne soldent pas non plus ; checklist « manquant » |
| `docs/audits/sondes/ADOC/C-ADOC-VER-020.py` | ADOC180 | REPRO | guide republié : 2 versions, description en base inchangée, le mot ajouté (« forage ») introuvable |
| `docs/audits/sondes/ADOC/C-ADOC-VER-021.py` | ADOC26 | REPRO | alias `compta.2026` accepté (200, en base) ; `extraire_alias` → '' ; 0 document créé |
| `docs/audits/sondes/ADOC/C-ADOC-VER-031.py` | ADOC29 | REPRO | purge avec MinIO en panne : aucune exception, document supprimé de la base |
| `docs/audits/sondes/ADOC/C-ADOC-VER-005.py` | ADOC179 (rejeu) | non rejouée | arrêt du processus par manque de mémoire (code 137) pendant la surcharge de la machine ; ADOC179 repose sur la lecture du code et son test nommé |

C-ADOC-VER-010 (ADOC183) et C-ADOC-VER-040 (ADOC182) sont des constats S3 statiques ; ADOC182 a été rejoué hors base par
`analyser()` sur des copies des arbres de `7e325e0ae` et de `56d5b623a`.

## 3. Écarts retenus

| Constat | Tâche | Écart de | Crit. | Grav. | Emplacement | Observé → attendu |
|---|---|---|---|---|---|---|
| C-ADOC-VER-011 | ADOC185 | ADOC14 (appelant oublié) | C7 | **S2** | `backend/django_core/apps/reporting/approbations.py::_decider_approbation_core` | la boîte centrale appelle `approve_demande` : l'approbateur de l'étape 1 approuve définitivement → passer par `avancer_chaine_approbation_ged` (unitaire, en masse, push) |
| C-ADOC-VER-030 | ADOC188 | ADOC177 | C7 | **S2** | `backend/django_core/apps/ged/services.py::matcher_depot_demandes` | `slugify` colle l'extension au dernier mot (« cinpdf ») : un dépôt nommé par son fichier ne solde jamais sa demande → mots découpés sur `[^a-z0-9]+` |
| C-ADOC-VER-010 | ADOC184 | ADOC183 | C13 | S3 | `frontend/src/providers/SessionProvider.jsx::SessionProvider` | reconnexion après expiration sans `fetchMe()` : compte portail → appel « message d'accueil » 403 + bienvenue ERP → même chemin que la connexion, transition testée |
| C-ADOC-VER-020 | ADOC186 | ADOC180 | C10 | S3 | `backend/django_core/apps/ged/management/commands/publier_documents_meryem.py` | description écrite seulement à la création ; test qui écrit en base → republier met à jour et réindexe, test par la commande |
| C-ADOC-VER-021 | ADOC187 | ADOC26 | C4 | S3 | `backend/django_core/apps/ged/services.py::extraire_alias_email` | alias à point accepté par l'écran, jamais routé → un seul motif partagé |
| C-ADOC-VER-031 | ADOC189 | ADOC29 | C7 | S3 | `backend/django_core/apps/records/storage.py::delete_attachment` | échec MinIO avalé : document détruit, binaire resté ; test qui simule la fonction testée → l'échec remonte et annule, seul `delete_object` simulé |
| C-ADOC-VER-040 | ADOC190 | ADOC182 | C10 | S3 | `scripts/check_liste_page1.py::analyser` | helpers `rows(r)` (locaux ou importés) non vus ; exemption sur tout le corps de fonction ; repro CoffresPage de la tâche reste vert → rc 1 nommant les sites |

**Constats S1-S2 : 2** (0 S1, 2 S2), tous deux reproduits par sonde.

Routage (`check_ownership.py --owner-of`) :

| Propriétaire | Plan | Tâches |
|---|---|---|
| documents | `PLAN_AUDIT_DOCUMENTS.md` | ADOC186, ADOC187, ADOC188 |
| analyse | `PLAN_AUDIT_ANALYSE.md` | ADOC185 |
| deploy | `PLAN_AUDIT_DEPLOY.md` | ADOC184, ADOC190 |
| documents + securite | `PLAN_AUDIT_TRANSVERSE.md` `(@atomique: documents, securite)` | ADOC189 |

Aucune décision du fondateur n'est requise.

## 4. Seconde lentille et critique

Aucun constat S1 : pas de seconde lentille ni de critique Fable (METHODE §C.4.2, skill audit §5). Les deux S2 sont
prouvés par sonde ; le rédacteur (opus, effort élevé, contexte frais) a relu chaque mécanisme dans le code avant d'écrire les
tâches, et a élargi deux constats :
- **ADOC188** : « Attestation_CNSS.pdf » donne `attestation_cnsspdf` (le souligné est gardé), d'où le découpage sur
  `[^a-z0-9]+` plutôt que le seul retrait de l'extension.
- **ADOC190** : le helper `rows` de GedSearch est importé de `search.js`, pas local.

## 5. Optionnel (non déposé)

- **ADOC4.** `fusionner_pdf` avec une `cible` ne compare pas le coffre de la cible à celui des sources : un admin pourrait
  fusionner des documents d'un coffre dans un document hors coffre. Hors des clauses d'ADOC4 (non sondé) ; à porter au
  prochain audit du groupe.
- **ADOC149.** NTPRT23, 26 et 31 restent comptés livrés dans `docs/done_task.md` (registre `NTPRT=26`) alors qu'ADOC149
  a retiré ces surfaces (S4, comptable).
- **ADOC118.** Une demande prise en charge sans ticket n'a aucune action d'écran pour en rattacher un (l'API le permet).
- **ADOC143.** Rapprocher sur une facture annulée lèverait `FactureNonEncaissable` non intercepté (500 probable, non prouvé).
- **ADOC126 (adjacent).** La création d'un ticket SAV au portail ne filtre pas les chantiers annulés.
- **ADOC24 (adjacent).** `creer_document_lien` n'indexe pas le document lien pour la recherche plein texte.
- **ADOC175 / ADOC75 / ADOC1.** Clauses de test plus étroites que la tâche (201 après signature non asserté ; pas de bout en
  bout « facture générée ⇒ document en GED » ; un espion à côté de la relecture en base).

## 6. Couverture et non-couvert

- **Couvert.** 37 des 114 tâches cochées : commits, tests nommés, code de `main`, décisions D-ADOC-*.
- **Non couvert.** Les 77 autres tâches cochées ; aucune lecture en production ; aucune suite de tests rejouée (les verdicts
  sur les tests viennent de leur lecture).

<!-- verifie | groupe: ADOC | pct: 99 | ecarts_s1_s2: 2 -->
