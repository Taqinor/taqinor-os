# Vérifie ADRG — troisième contre-visite du parcours PF4 « droits de la grille », 17/11/2026

<!-- verifie | groupe: ADRG | pct: 99 | ecarts_s1_s2: 2 | faits: 118 -->

Contre-visite du groupe ADRG (audit de parcours PF4 du 10/11, dossier `2026-11-10-parcours-PF4.md`), due à 95 %
(`audit_registre.py --du` : 118 tâches cochées sur 119 constructibles). Elle suit les contre-visites du 13/11 et du 14/11
(`2026-11-14-droits-grille-verifie.md`). Son but premier : contrôler la tâche d'écart S2 du 14/11, ADRG123, et les tâches
cochées depuis par les vagues d'acceptation 4 à 8. Rien n'a été construit ni déployé, et aucune production n'a été lue.

## 0. Préconditions

- **SHA.** `origin/main` = `ee9180785` (PR #1446). Branche de claim : `verifie-adrg-1711`.
- **Registre.** PF4 `droits-grille`, groupe ADRG, 118 tâches cochées sur 119 constructibles (99 %). Restent ouvertes ADRG140
  (bloquée : aucune route ne liste les collègues au palier limité) et la tâche d'acceptation ADRG105.
- **Cochées depuis le 14/11 : 62.** Elles se répartissent en trois familles :
  - 25 tâches restées `[BLOCKED]` au 14/11 et jamais relues : ADRG4, 5, 11, 12, 13, 15, 20, 21, 22, 37, 38, 40, 41, 43, 46,
    47, 63, 69, 70, 71, 73, 75, 77, 80 et 99 ;
  - les tâches d'écart du 14/11, ADRG123 à 137 ;
  - les tâches de correction des vagues d'acceptation, ADRG138, 139 et 141 à 145, ainsi que ADRG106 à 121, cochées après
    leur preuve en direct.
- **Échantillon : 41 tâches** (tirage déterministe, graine = `ee9180785`).
  - **Imposées (33).** L'écart S2 du 14/11 (ADRG123), les 25 tâches jamais relues et les 7 tâches de correction cochées
    (ADRG138, 139, 141 à 145).
  - **Tirées (8).** 25 % des 30 autres par `random.Random(int(sha, 16)).sample` : ADRG111, 113, 118, 128, 129, 130, 133
    et 135.
- **Méthode.**
  - Lecture des commits (`git log --grep`), du code sur `origin/main` et des tests nommés.
  - Rôles recalculés en Python pur sur le registre `CANONICAL_SYSTEM_ROLES` / `PERMISSION_MODULE`.
  - Jumeaux cherchés par grep des routes, des wrappers d'API et des codes de droit.
  - Enregistrements d'acceptation `docs/audits/acceptation/ADRG/` rapprochés de chaque tâche.
  - Sondes hôte jouées.
  - Aucune pile, aucun test Django ni vitest lancé.

## 1. Vérificateurs (4 lots, opus, effort élevé, frais)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **36** | ADRG4, 5, 11, 12, 13, 15, 37, 38, 40, 41, 43, 46, 47, 63, 69, 70, 71, 73, 75, 77, 80, 99, 111, 113, 118, 128, 129, 130, 133, 135, 138, 141, 142, 143, 144, 145 |
| partiel | **5** | ADRG20, 21, 22, 123, 139 |
| non-fait / faux / régression / déjà-présent | **0** | — |

**Le « fini quand ».** Les 36 « ok » l'atteignent, avec un test nommé comportemental et un enregistrement d'acceptation
PASS. Deux exceptions de couverture :
- ADRG123 n'a pas d'enregistrement : sa preuve est « API seulement », que `check_acceptation.py` accepte.
- ADRG47 est couverte « avec écart » (enregistrement `0da6c9998`), voir §5.

**La cause des 5 « partiel ».** Un jumeau oublié (L6) ou un chemin oublié (L4) :
- ADRG123 ferme la création d'un envoi programmé `query` stock, mais ni le genre `dashboard` ni le PATCH des destinataires
  sur le rapport d'un autre propriétaire (deux écarts S2, §4).
- ADRG20, 21, 22 et 139 ont gardé l'écran et les gestes qu'ils nomment. Un autre bouton du même écran, ou une autre route
  du même menu, reste offert alors que le serveur refuse (S3).

## 2. Tests nommés

Les vérificateurs ont retrouvé, fichier et nom de test, le test nommé de chacune des 41 tâches. Les tests backend
(ADRG4, 5, 11, 15, 37, 38, 40, 43, 46, 63, 69, 70, 71, 73, 80, 99 et 123) passent par un appel HTTP réel, avec les rôles
d'`init_roles` ou du registre, et relisent l'état après le refus.

**Faiblesses relevées, sans écart de spécification :**
- ADRG13 : le test d'écran simule `useCanModifierParametres` ; la logique de palier qu'il ajoute n'y est pas exercée.
- ADRG41 : les 11 classes sont vérifiées par leurs `permission_classes`, avec un seul POST réel.
- ADRG135 et ADRG128 : « Restaurer » et la règle de la barre de lot n'ont pas de test unitaire, seulement la spec
  d'acceptation.
- ADRG4 : sur 5 routes, le Commercial responsable n'est contrôlé que par `!= 403`, pas par 204.

## 3. Sondes

| Sonde | Tâche | Verdict | Observé (hôte, `ee9180785`) |
|---|---|---|---|
| `C-ADRG-VER2-200.py` (14/11) | ADRG123 | réfutée | `repro: false` : la création et le rendu d'un envoi `query` lisent le droit d'export (`creation_lit_le_droit_export: true`, `rendu_lit_le_droit_export: true`) |
| `C-ADRG-VER3-360.py` | jumeau d'ADRG123 | **REPRO** | `validate_export_seulement_sous_query: true`, `rendu_dashboard_lit_le_droit_export: false`, `lien_public_rend_le_dashboard: true` ; rôles livrés touchés : Commercial responsable, Responsable |
| `C-ADRG-VER3-361.py` | chemin d'ADRG123 | **REPRO** | `queryset_borne_au_proprietaire: false` ; garde jouée sur `patch_recipients: false`, `patch_cible_id: true`, `creation: true` ; `rendu_relit_le_droit_du_proprietaire: true` |

L'orchestrateur a rejoué les deux sondes neuves (`repro: true` toutes deux). Il a aussi relu les lignes visées de
`apps/reporting/saved_reports_api.py` et `apps/reporting/scheduled_reports.py` :
- le viewset n'a que `TenantMixin` et `IsResponsableOrAdmin`, sans borne au propriétaire ;
- l'appel à `exiger_export_dataset` n'est fait que sous la condition `not self.partial or {'cible_id', 'target_kind'} &
  set(attrs)` ;
- au rendu, seul `_rendre_saved_query` l'appelle, et au nom de `report.owner`.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâche |
|---|---|---|---|---|---|
| C-ADRG-VER3-360 | ADRG123 | **S2** | Un envoi programmé de genre `dashboard` envoie en PDF les lignes de chaque widget à des adresses libres et par le lien de rapport de 90 jours, en ne contrôlant que la lecture. Un widget sur le jeu `stock_produits` sort ainsi de l'ERP sans `stock_export` (`saved_reports_api.py::SavedReportSerializer.validate`, `scheduled_reports.py::_rendre_dashboard`). | `C-ADRG-VER3-360.py` (REPRO) | ADRG146 |
| C-ADRG-VER3-361 | ADRG123 | **S2** | Un rôle sans `stock_export` réoriente par un PATCH `{"recipients": …}` vers son adresse l'envoi `query` stock d'un autre propriétaire (le Directeur), si la requête est partagée ou sans propriétaire. Le contrôle d'export est sauté sur ce PATCH partiel, et le rendu relit le droit du propriétaire, qui l'a. | `C-ADRG-VER3-361.py` (REPRO) | ADRG147 |
| C-ADRG-VER3-300 | ADRG113 | S3 | `SuiviGpsPage` lit `crm/assignable-users/` au montage sans `useCanListAssignableUsers` ; Technicien responsable et Admin RH reçoivent un 403. | STATIQUE (lecture) | ADRG148 |
| C-ADRG-VER3-301 | ADRG21, ADRG77 | S3 | « Exporter » de la table des chantiers (`views/ListView.jsx`) et « Exporter Excel » du parc installé ne sont pas gardés ; la route exige `installation_export`. Six rôles livrés reçoivent un 403. | STATIQUE (lecture) | ADRG149 |
| C-ADRG-VER3-340 | ADRG21 | S3 | « Ouvrir un ticket » de la fiche chantier n'est pas gardé ; `POST sav/tickets/` exige `sav_gerer`. Commercial, Viewer et Utilisateur reçoivent un 403. | STATIQUE (lecture) | ADRG150 |
| C-ADRG-VER3-342 | ADRG139 | S3 | Les entrées et routes `/planification` et `/ma-journee` ne portent aucun droit, alors que leurs lectures suivent `LectureDuModule`. Cinq rôles livrés sans code installations reçoivent un 403. | STATIQUE (lecture) | ADRG151 |
| C-ADRG-VER3-302 | ADRG20 | S3 | La liste et le kanban des leads gardent le sélecteur « Responsable », l'édition en ligne, le changement d'étape et « perdu » sans `crm_reassign` ni `crm_modifier`. Le Then d'ADRG20 les retirait. | STATIQUE (lecture) | ADRG152 |
| C-ADRG-VER3-320 | ADRG143 | S3 | Le panneau « Détails » d'un document GED lit `permissions-effectives/` au chargement et par « CSV » pour tout rôle. L'action exige `ged_gerer`, et le Viewer reçoit un 403. | STATIQUE (lecture) | ADRG153 |
| C-ADRG-VER3-341 | ADRG22 | S3 | Sur le détail d'un ticket SAV, « Fusionner », « Convertir en opportunité CRM » et « Nouveau prêt » ne sont pas gardés. Sur le calendrier, « Créer un ticket ce jour » et le glisser pour replanifier ne le sont pas non plus. Toutes ces routes exigent `sav_gerer`. | STATIQUE (lecture) | ADRG154 |

**Gravité des deux écarts S2.** La donnée sort de l'ERP vers une adresse saisie librement, alors que D-ASEC-VER4-1
(`appliquer_grille`) a retiré `stock_export` aux deux rôles touchés et qu'ADRG123 leur refuse la même extraction par la
création. Ce n'est pas un S1 : le jeu stock ne porte ni prix d'achat (retirés par `spec_sans_champs_gated`) ni donnée
personnelle, et l'écart 361 exige une requête partagée ou sans propriétaire.

**Gravité des sept autres : S3.** Le serveur refuse ; seul l'écran est désaligné (bouton mort, 403 en console). Aucune
donnée n'est exposée.

## 5. Optionnel (non déposé)

- **ADRG47, écart d'acceptation sans tâche.** `/sav/monitoring` est réservé au palier responsable ou admin depuis ASAV100
  (`frontend/src/features/sav/module.config.jsx`). Le Technicien livré, de palier normal, ne voit donc ni Abonnements, ni
  Certificats carbone, ni SLA de disponibilité, alors que le serveur accepterait ses écritures (`permission_module='sav'`).
  L'écran est plus strict que le serveur : ce n'est pas un défaut de droits, mais le « un porteur de `sav_gerer` les voit
  toujours » d'ADRG47 est faux pour ce rôle. À trancher par le propriétaire SAV : ouvrir ces sections au Technicien, ou
  les laisser au palier responsable.
- **Genre figé `stock` et `stock_report?export=xlsx`.** Ils n'exigent toujours que `reporting_export`. La question du
  14/11 (§5) reste ouverte, et aucune décision n'existe dans `decisions.yml`.
- **`OrdreAssemblage*ViewSet`** reste à `IsResponsableOrAdmin`, hors du périmètre d'ADRG41.
- **Écran plus strict que le serveur, pour des rôles personnalisés seulement.**
  - `useCanModifierParametres` (ADRG12, 13, 38) exige aussi le palier responsable.
  - Dans `ProduitForm`, « Supprimer » un prix fournisseur est réservé à l'administrateur (ADRG37).
  - « Rejeter » une disposition GED suit `peutGouverner`, alors que la route reste à `IsResponsableOrAdmin` (ADRG135).
- **Comptes hérités.** `useHasPermission` cache le geste à un compte hérité sans rôle fin, que le
  `HasPermissionOrLegacy` du serveur accepte (ADRG21, 99).
- **Lectures au montage, même classe que C-ADRG-VER3-300.** `RelancesSuiviPage.jsx`, `PlanifierVisiteModal.jsx`,
  `DelegationDialog.jsx` et `useUtilisateursAssignables.js` lisent `getAssignableUsers` sans le crochet. Elles sont moins
  exposées (ouverture d'un dialogue, écran CRM) ; seules celles du propriétaire chantiers sont reprises par ADRG148.
- **Lectures sans garde.** `Rapports.jsx` appelle `integriteInsight` sans condition, et `KitsSection` lit les types
  d'intervention sans garde.
- **ADRG133.** Le Directeur reçoit toujours un 409 sur `approuver` avant le chargement du plan, comme le montre
  l'enregistrement `df74c8d81`.
- **Taille de fichier.** `apps/crm/clients_views.py` fait 2 014 lignes. ADRG4 l'avait laissé à 1 979 ; le dépassement vient
  de commits ultérieurs.

## 6. Couverture et sortie de cycle

**Couvert.** Les 41 tâches de l'échantillon, chacune lue sur :
- ses commits ;
- le code servi ;
- son test nommé ;
- ses jumeaux, par grep ;
- les rôles livrés, recalculés ;
- son enregistrement d'acceptation.

S'y ajoutent trois sondes hôte jouées : une réfutée, deux REPRO.

**Non couvert.**
- Les 21 autres tâches cochées depuis le 14/11 : ADRG106 à 110, 112, 114 à 117, 119 à 121, 124 à 127, 131, 132, 134, 136
  et 137.
- Aucun test Django ni vitest lancé : la preuve des tests reste la CI de `main`.
- Aucun rejeu navigateur : la preuve en direct reste celle des enregistrements d'acceptation cités.

**Statut.** Deux écarts S2 nouveaux, tous deux sur le chemin qu'ADRG123 devait fermer : ADRG146 et ADRG147. Sept tâches
S3 (ADRG148 à 154) sont déposées chez leurs propriétaires. Le cycle n'est pas sorti : il faudra une contre-visite
d'ADRG146 et 147 une fois cochées, puis deux `vérifie` consécutifs à zéro S1-S2.

## 7. Coût

4 vérificateurs (opus, effort élevé, environ 0,96 M de jetons) et 1 rédacteur (opus). Aucun appel Fable : aucun S1.
