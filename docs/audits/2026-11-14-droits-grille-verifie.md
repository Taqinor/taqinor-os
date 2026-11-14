# Vérifie ADRG — contre-visite de clôture du parcours PF4 « droits de la grille », 14/11/2026

<!-- verifie | groupe: ADRG | pct: 96 | ecarts_s1_s2: 1 -->

Contre-visite de clôture du groupe ADRG (audit de parcours PF4 du 10/11, dossier `2026-11-10-parcours-PF4.md`), due à 95 %
(`audit_registre.py --du` : 56 tâches cochées sur 58 constructibles). Elle suit la contre-visite de mi-parcours du 13/11
(`2026-11-13-droits-grille-verifie.md`). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `d683286669`. Branche de claim : `verifie-adrg-1411`.
- **Registre.** PF4 `droits-grille`, groupe ADRG, 56 tâches cochées sur 58 constructibles (96 %). Restent ouvertes ADRG77 et
  la tâche d'acceptation ADRG105.
- **Échantillon : 47 tâches, toutes relues.** Presque toutes ouvrent ou ferment un droit sur l'argent, des données
  personnelles, une autre société ou les comptes ; le tirage aurait donc couvert le groupe entier.
  - Les 32 tâches cochées depuis le 13/11 : ADRG2, 16, 17, 18, 19, 23, 24, 31, 32, 34, 35, 36, 39, 61, 62, 64, 66, 76, 82,
    84, 85, 86, 87, 88, 89, 96, 97, 101, 102, 104, 109 et 122.
  - Les 15 tâches marquées « code livré, preuve en direct due » : les tâches d'écart du 13/11 ADRG106, 107 et 108, et les
    tâches ADRG110 à 121, déposées le 13/11.
- **Méthode.**
  - Lecture des commits (`git log --grep`), du code sur `origin/main` et des tests nommés.
  - Rôles recalculés en Python pur sur le registre `CANONICAL_SYSTEM_ROLES` / `PERMISSION_MODULE`.
  - Jumeaux cherchés par grep des routes, des wrappers d'API et des codes de droit.
  - Sondes hôte rejouées.
  - Aucune pile, aucun test Django ou vitest lancé, aucune production consultée.

## 1. Vérificateurs (5 lots, opus, effort élevé, frais)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **30** | ADRG2, 16, 17, 31, 32, 34, 61, 62, 64, 66, 82, 87, 88, 89, 96, 97, 101, 106, 107, 108, 109, 110, 111, 112, 113, 116, 117, 118, 120, 122 |
| partiel | **16** | ADRG18, 19, 23, 24, 35, 36, 39, 76, 84, 85, 86, 102, 114, 115, 119, 121 |
| déjà-présent | **1** | ADRG104 (livré avant la tâche par `b2be6a1`, ERR-ACC-SIDEBAR-CO2-403) |
| non-fait / faux / régression | **0** | — |

**Le « fini quand ».** Les 16 « partiel » l'atteignent tous sur le geste et le rôle qu'il nomme.

**La cause des « partiel ».** Il leur manque presque toujours un jumeau : un autre bouton du même écran, ou une autre
route du même geste. Il est resté ouvert alors que le serveur exige désormais le code. ADRG114 est à part : son prédicat
d'écran n'est pas la règle serveur, mais l'écart ne touche que les comptes hérités.

**Le seul écart de fond.** Le jumeau d'ADRG76 : la remise d'un extrait de jeu stock par un envoi programmé (§4,
C-ADRG-VER2-200).

**Contre-visite des tâches d'écart du 13/11 (§C.4.6).** Elles étaient toutes S3 :

| Écart du 13/11 | Tâche | Verdict |
|---|---|---|
| C-ADRG-VER1-044 | ADRG106 | fermé |
| C-ADRG-VER1-045 | ADRG107 | fermé |
| C-ADRG-VER1-003 | ADRG108 | fermé |
| C-ADRG-VER1-010 | ADRG109 | fermé côté serveur |
| C-ADRG-VER1-009 | — | sans tâche, inchangé |

Pour ADRG109, l'option « Générer le PDF » de la barre de lot reste offerte : elle était hors du périmètre de la tâche et
fait l'objet de C-ADRG-VER2-205.

## 2. Tests nommés

Les vérificateurs ont retrouvé, fichier et nom de test, le test nommé de chacune des 47 tâches.

**Tests backend lus.** ADRG2, 16, 31, 32, 34, 35, 36, 39, 61, 62, 64, 76, 96, 97, 101, 102 et 109. Ils sont
comportementaux : appel HTTP réel, rôles d'`init_roles` ou du registre, état relu après refus.

**Faiblesses relevées, sans écart de spécification :**
- ADRG36 : la docstring promet « profil relu présent », mais les DELETE visent l'id 999999.
- ADRG62 : la fonction d'import est appelée directement, sans passer par `imports/commit/`.
- ADRG18 : les drapeaux sont injectés dans `ctx`, sans rendu de `FactureList` avec un store du registre.
- ADRG120 : `lecturesAccueil` est testée comme une fonction pure.
- ADRG96 : la réponse est 409 (`ConflitEtat`), pas le 400 du texte. C'est une décision de fix-ci (`fd9e0d0`) et le test
  est aligné.

## 3. Sondes et preuve en direct

- **Rejouées sur l'hôte sans écart (`repro: false`).** Sondes 002, 003, 005, 006, 008, 009, 010 et 014 du dossier PF4.
  - Les 006, 008, 010 et 014 n'ont pas de bloc `__main__` : elles ont été jouées par `runpy` puis `sonde(None)`.
  - Elles couvrent ADRG2, 31, 32, 34, 39, 64 et 66.
- **Non rejouables sur l'hôte.** Les sondes 001 et 053 exigent les réglages Django (`ImproperlyConfigured: REST_FRAMEWORK`).
- **Sonde 053 (ADRG96, 97) : périmée.** Elle lit `/public/portail/<jeton>/mon-releve/`. Le grep de `mon-releve` dans les
  `urls*.py` ne trouve plus rien (route retirée par APUB43) : son verdict ne prouve rien. La preuve d'ADRG96 et 97 reste
  donc les tests Django `test_aud141_jeton_acces.py` et `test_aud138_revocation.py`.
- **Sonde neuve : `docs/audits/sondes/ADRG/C-ADRG-VER2-200.py`.** Hôte, registre réel, gardes lues par ast. Jouée :
  `repro: true`.
  - Elle trouve deux rôles touchés : Commercial responsable et Responsable.
  - Ni `SavedReportSerializer.validate` ni `_rendre_saved_query` n'appellent `exiger_export_dataset`.
  - Témoin : l'extrait planifié d'ADRG76 l'appelle bien.
- **Preuve en direct.** Aucune rejouée, faute de pile. Les 15 tâches « code livré » restent `[BLOCKED : preuve en direct
  due]`, comme la tâche d'acceptation ADRG105.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ADRG-VER2-200 | ADRG76 | S2 | `apps/reporting/saved_reports_api.py::SavedReportViewSet` (`IsResponsableOrAdmin` seul) et `scheduled_reports.py::_rendre_saved_query` : un envoi programmé `query` sur une requête du jeu `stock_produits` part en XLSX par e-mail à des adresses libres, ou par lien de rapport, sans `stock_export`. Commercial responsable et Responsable sont touchés : D-ASEC-VER4-1 leur a retiré cet export. | `docs/audits/sondes/ADRG/C-ADRG-VER2-200.py` (REPRO) | ADRG123 |
| C-ADRG-VER2-201 | ADRG102 | S3 | `apps/reporting/models.py::SavedReport.resoudre_cible` résout le tableau ou la requête cible sur toute la société, sans la règle de visibilité. Un responsable peut programmer le tableau PERSONNEL d'un collègue, dont il reçoit le titre et la mise en page ; les données sont jouées avec les droits du propriétaire du rapport. | STATIQUE (lecture) | ADRG124 |
| C-ADRG-VER2-202 | ADRG119 | S3 | `frontend/src/pages/Rapports.jsx::Component` : la carte Service suit `installation_voir` sans le palier responsable de sa route ; les cartes ventes et stock ne sont pas gardées. Technicien responsable et Admin RH reçoivent des 403. | STATIQUE (lecture) | ADRG125 |
| C-ADRG-VER2-203 | ADRG17 | S3 | `apps/ventes/vente_facturation.py::_facture_etat` pose `'pdf': ecrit` sans `ventes_pdf`, alors qu'ADRG10 a ajouté ce code aux deux routes PDF. Seul un rôle personnalisé décoché est touché. | STATIQUE (lecture) | ADRG126 |
| C-ADRG-VER2-204 | ADRG19 | S3 | `DevisRow` : « Copier le lien de la proposition » et « Copier l'aperçu interne » ne sont pas gardés (`share-link` exige l'écriture ventes) ; « Bon de commande (PDF) » non plus (la route exige `ventes_pdf`). Viewer et Utilisateur reçoivent un 403. | STATIQUE (lecture) | ADRG127 |
| C-ADRG-VER2-205 | ADRG18, ADRG109 | S3 | « Aperçu du PDF » de la ligne facture n'est gardé que par `f.fichier_pdf` (route `ventes_pdf`). La barre de lot offre « Relancer », « Envoyer par email » et « Générer le PDF » à tous ; la route `bulk` exige l'écriture ventes. | STATIQUE (lecture) | ADRG128 |
| C-ADRG-VER2-206 | ADRG24 | S3 | « Exporter » de la table catalogue (`StockList`) et « Exporter (Excel) » des consignations s'affichent sans `stock_export`, que leurs routes exigent. Six rôles livrés reçoivent un 403. | STATIQUE (lecture) | ADRG129 |
| C-ADRG-VER2-207 | ADRG35, ADRG36 | S3 | `QuaisPage` : import ASN (`stock_mouvement`), « Ajouter le quai » et « Activer/Désactiver » (administrateur) non gardés. `PickingPage` : « Générer les comptages » (administrateur) non gardé. | STATIQUE (lecture) | ADRG130 |
| C-ADRG-VER2-208 | ADRG36 | S3 | « Supprimer » un profil saisonnier suit `stock_modifier`, alors que la route exige `stock_supprimer` ou le palier administrateur. « Soumettre pour validation » d'un dossier fournisseur suit `stock_modifier`, alors que la route exige `valider_dossier_fournisseur`. | STATIQUE (lecture) | ADRG131 |
| C-ADRG-VER2-209 | ADRG39, ADRG115 | S3 | `SavParametresPage::CategoriesEquipementSection` : « Ajouter » et « Enregistrer » ne sont pas gardés, alors que la route exige `equipement_gerer`. Le panneau feuille de maintenance d'un ticket est monté sans `sav_gerer`, ce qui donne un 403 quand `worksheets_maintenance_actifs` est activé. | STATIQUE (lecture) | ADRG132 |
| C-ADRG-VER2-210 | ADRG86 | S3 | « Rejeter » et « Approuver l'étape » d'un plan d'approbation suivent `isManager` seul ; la route exige `approuver_demande_achat`. | STATIQUE (lecture) | ADRG133 |
| C-ADRG-VER2-211 | ADRG113 | S3 | `InterventionsPage` lit `crm/assignable-users/` au montage sans `useCanListAssignableUsers`. Technicien et Technicien responsable reçoivent un 403. | STATIQUE (lecture) | ADRG134 |
| C-ADRG-VER2-212 | ADRG23, ADRG85 | S3 | « Restaurer » une version GED n'est pas gardé (`ged_gerer`). `RetentionPage` : « Nouvelle politique », « Supprimer » une politique, « Approuver » et « Exécuter » une disposition ne sont pas gardés (`ged_gouvernance`). | STATIQUE (lecture) | ADRG135 |
| C-ADRG-VER2-213 | ADRG84 | S3 | « Aperçu » et « Aperçu du rendu » des modèles brandés sont offerts sans `parametres_modifier`, que `preview` exige ; message « Aperçu impossible ». | STATIQUE (lecture) | ADRG136 |
| C-ADRG-VER2-214 | ADRG121 | S3 | Quatre gestes d'écriture de `IdentityRail` restent offerts au Viewer : « Relance le », « Passer en <segment> », « Mettre à jour la fiche client », « Examiner » puis « Fusionner ». | STATIQUE (lecture) | ADRG137 |
| C-ADRG-VER2-215 | ADRG114 | S3 | `useCanListUsers` autorise le palier administrateur ou `users_gerer` ; la liste `/users/` suit `IsAdminOrResponsableTier`. Seul un compte hérité responsable est touché, et aucun rôle livré. | STATIQUE (lecture) | sans tâche : aucun rôle livré, défaut antérieur à la tâche, crochet partagé |

**Gravité de C-ADRG-VER2-200 : S2.** La donnée sort de l'ERP vers une adresse saisie librement. Le rôle touché s'est vu
retirer cet export par une décision du fondateur (D-ASEC-VER4-1, `appliquer_grille`), et la même extraction planifiée par
`scheduled-exports/` lui est refusée depuis ADRG76. Elle reste en S2 et non en S1 : le jeu stock ne porte ni prix d'achat
(retirés par `spec_sans_champs_gated`) ni donnée personnelle.

**Gravité des 15 autres écarts : S3.** Le serveur refuse ; seul l'écran est désaligné (bouton mort, 403 en console).
Aucune donnée n'est exposée.

## 5. Optionnel (non déposé)

**Points à trancher par le propriétaire analyse.**
- `stock_report?export=xlsx` (`apps/reporting/reports.py::stock_report`) et le genre figé `stock` d'un envoi programmé
  (`scheduled_reports.py::render_stock`) n'exigent que `reporting_export`. Faut-il les traiter comme l'export propre du
  module Rapports, ou comme un jumeau de D-ASEC-VER4-1 ?
- Un responsable peut modifier par PATCH puis exécuter l'extrait stock d'un Directeur. Ce n'est pas une remise au rôle :
  l'extrait reste exécuté au nom de son créateur, vers une destination de la société.

**Jumeaux plausibles d'ADRG113, rôles non calculés.** Ils lisent `getAssignableUsers` sans le crochet :
`SuiviGpsPage.jsx`, `RelancesSuiviPage.jsx`, `PlanifierVisiteModal.jsx` et `features/calepinage/useUtilisateursAssignables.js`.

**Désalignements écran / serveur de même nature.**
- `CategoriesStock.jsx` : « Ajouter » une marque suit `stock_modifier`, alors que la route marque est réservée à
  l'administrateur.
- `RfaPage.jsx` : « Générer l'avoir » sans `achats_payer`.
- `KitsSection.jsx` : lecture des types d'intervention sans garde.
- `GedDocumentInsights.jsx` lit `/users/` et `/roles/` au montage.

**Exports stock sans `stock_export` côté serveur.** `inventaires-annuels/<id>/export-xlsx/`, `prix-fournisseurs/export-xlsx/`
et `produits/analyse-achats/export-xlsx/`. C'est un trou ASEC50 possible, hors PF4.

**Défauts mineurs.**
- ADRG31 : la garde est `HasPermissionOrLegacy`, donc le 403 ne nomme pas le code (S4).
- ADRG62 : un Commercial peut importer une facture au statut `annulee`.
- `AvoirsPage.jsx`, `RelancesPage.jsx` et `FactureForm.jsx` n'ont pas de repli « compte hérité » dans `useHasPermission`.
- `useDroitMetier` juge le « rôle fin » sur `permissions.length` ; le serveur, sur `role_id`.

**Sondes.**
- La 053 doit lire `compte_portail_par_token`.
- Les 006, 008, 010 et 014 n'ont pas de bloc `__main__`.

## 6. Couverture et sortie de cycle

**Couvert.** Les 47 tâches, chacune lue sur :
- les commits ;
- le code servi ;
- les tests nommés ;
- les jumeaux par grep ;
- le calcul des rôles livrés.

S'y ajoutent les sondes hôte rejouables.

**Non couvert.**
- Aucun test Django ni vitest lancé : la preuve des tests reste la CI de `main`.
- Aucun rejeu navigateur ; les preuves en direct d'ADRG106-108 et 110-121 restent dues.
- Les mutants annoncés ont été raisonnés, pas joués.
- Les sondes 001 et 053 n'ont pas été rejouées : elles exigent Django.
- Les tâches BLOCKED antérieures au 13/11 n'ont pas été relues : ADRG4, 5, 11 à 13, 15, 20 à 22, 37, 38, 40, 41, 43, 46,
  47, 63, 69 à 71, 73, 75, 80 et 99.

**Statut.** Un écart S2 nouveau (C-ADRG-VER2-200, tâche ADRG123). Aucun écart S1-S2 antérieur n'attend sa tâche. Le groupe
reste « construit » et non « vérifié » : il faut une contre-visite d'ADRG123 une fois cochée, puis deux `vérifie`
consécutifs à zéro S1-S2. Quatorze tâches d'écart S3 (ADRG124 à 137) sont déposées chez leurs propriétaires.

## 7. Coût

5 vérificateurs (opus, effort élevé) et 1 rédacteur. Jetons des sous-agents ≈ 1,4 M. Aucun appel Fable.
